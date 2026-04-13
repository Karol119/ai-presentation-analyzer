"""
Orquestador principal del análisis de presentaciones.
Solo delega: no imprime, no selecciona archivos, no hace I/O de ningún tipo.
Devuelve un dict estructurado que la GUI, la CLI o los tests pueden consumir.
"""
from pathlib import Path

from app.core.logic.text_extractor       import extraer_datos_pptx
from app.core.logic.slide_classifier     import clasificar_diapositiva
from app.core.logic.metrics.icd          import calcular_icd_presentacion
from app.core.logic.metrics.word_count   import calcular_wps_presentacion
from app.core.logic.metrics.header_structure import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread import calcular_nts
from app.core.logic.presentation_score   import calcular_score_global, calcular_score_slide
from app.infrastructure.ollama.diagnostic_service import generar_diagnostico_metrico
from app.infrastructure.ollama.ollama_service     import verificar_conexion, clasificar_tipo_diapositiva
from app.infrastructure.ollama.coherencia_service import verificar_coherencia_titulo
from app.infrastructure.ollama.narrativa_service  import verificar_hilo_narrativo

# Tipos de slide que no se analizan (portada, índice, etc.)
_TIPOS_OMITIDOS = {"portada", "indice", "referencias", "cierre", "sin_contenido"}


def analizar_presentacion(ruta: str) -> dict:
    """
    Ejecuta el pipeline completo de análisis sobre un archivo .pptx.

    Parámetros
    ----------
    ruta : str
        Ruta absoluta o relativa al archivo .pptx.

    Retorna
    -------
    dict con la estructura:
    {
        "nombre":       str,
        "score_global": dict,        # resultado de calcular_score_global
        "slides": [
            {
                "slide_number": int,
                "tipo":         str,
                "omitida":      bool,
                "score":        dict,   # resultado de calcular_score_slide
                "metricas_raw": {       # resultados individuales por métrica
                    "icd": dict,
                    "wps": dict,
                    "hss": dict,
                    "nts": dict,
                },
                "feedback": {           # None si slide omitida o sin LLM
                    "icd":           str | None,
                    "wps":           str | None,
                    "hss":           str | None,
                    "nts":           str | None,
                    "preguntas":     list[str],
                    "datos_curiosos": list[str],
                } | None,
            },
            ...
        ]
    }
    """
    llm_ok = verificar_conexion()
    datos  = extraer_datos_pptx(ruta)

    # ── 1. Clasificación ──────────────────────────────────────────────────────
    for s in datos["slides"]:
        s["clasificacion"] = clasificar_diapositiva(
            s,
            llm_fn=clasificar_tipo_diapositiva if llm_ok else None,
        )

    slides_contenido = [
        s for s in datos["slides"]
        if not s.get("clasificacion", {}).get("excluir", False)
    ]

    # ── 2. Métricas ───────────────────────────────────────────────────────────
    res_icd = calcular_icd_presentacion(slides_contenido)
    res_wps = calcular_wps_presentacion(slides_contenido)
    res_hss = calcular_hss_presentacion(
        slides_contenido,
        llm_fn=verificar_coherencia_titulo if llm_ok else None,
    )
    res_nts = calcular_nts(
        slides_contenido,
        llm_fn=verificar_hilo_narrativo if llm_ok else None,
    )

    score_global = calcular_score_global(res_icd, res_wps, res_hss, res_nts)

    # ── 3. Construcción de resultados por slide ───────────────────────────────
    slides_resultado = []

    for idx, s in enumerate(slides_contenido):
        n    = s["slide_number"]
        clas = s.get("clasificacion", {})
        tipo = clas.get("tipo", "contenido")

        if tipo in _TIPOS_OMITIDOS:
            slides_resultado.append({
                "slide_number": n,
                "tipo":         tipo,
                "omitida":      True,
                "score":        None,
                "metricas_raw": None,
                "feedback":     None,
            })
            continue

        # Resultados individuales de cada motor
        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == n), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == n), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == n), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == n), {})

        ss = calcular_score_slide(mi, mw, mh, mn)

        # Feedback LLM solo cuando la slide necesita recomendación
        feedback = None
        if ss["necesita_recomendacion"] and llm_ok:
            slide_prev_texto = (
                " ".join(slides_contenido[idx - 1].get("content", []))
                if idx > 0 else None
            )
            slide_next_texto = (
                " ".join(slides_contenido[idx + 1].get("content", []))
                if idx < len(slides_contenido) - 1 else None
            )
            feedback = generar_diagnostico_metrico(
                slide_data = s,
                metricas   = ss["metricas"],
                slide_prev = slide_prev_texto,
                slide_next = slide_next_texto,
            )

        slides_resultado.append({
            "slide_number": n,
            "tipo":         tipo,
            "omitida":      False,
            "score":        ss,
            "metricas_raw": {"icd": mi, "wps": mw, "hss": mh, "nts": mn},
            "feedback":     feedback,
        })

    return {
        "nombre":       Path(ruta).name,
        "score_global": score_global,
        "slides":       slides_resultado,
    }