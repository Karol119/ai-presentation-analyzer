# app/core/controller/analyzer_controller.py
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
from app.infrastructure.ollama.ollama_service import verificar_conexion, clasificar_tipo_diapositiva, iniciar_ollama_background
from app.infrastructure.ollama.coherencia_service import verificar_coherencia_titulo
from app.infrastructure.ollama.narrativa_service  import verificar_hilo_narrativo
from app.infrastructure.ollama.restructure_service import reestructurar_slide

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
    # ── 0. ENCENDIDO AUTOMÁTICO DE OLLAMA ─────────────────────────────────────
    # Esto encenderá el motor si estaba apagado, o pasará de largo si ya estaba activo.
    llm_ok = iniciar_ollama_background()
    
    if not llm_ok:
        print("Advertencia: No se pudo iniciar el LLM. El análisis se hará sin IA.")
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
                "restructura":  None,   # ← consistencia con el resto
            })
            continue

        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == n), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == n), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == n), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == n), {})

        ss = calcular_score_slide(mi, mw, mh, mn)

        # ── Contexto NTS: se calcula UNA sola vez y lo usan ambos servicios ──────
        # ANTES estaba duplicado dentro de cada if, aquí se define siempre
        slide_prev_texto = (
            " ".join(slides_contenido[idx - 1].get("content", []))
            if idx > 0 else None
        )
        slide_next_texto = (
            " ".join(slides_contenido[idx + 1].get("content", []))
            if idx < len(slides_contenido) - 1 else None
        )

        feedback    = None
        restructura = None   # ← valor por defecto explícito

        if ss["necesita_recomendacion"] and llm_ok:
            feedback = generar_diagnostico_metrico(
                slide_data = s,
                metricas   = ss["metricas"],
                slide_prev = slide_prev_texto,
                slide_next = slide_next_texto,
            )
            restructura = reestructurar_slide(
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
            "restructura":  restructura,   # ← aquí estaba el bug principal
        })

    return {
        "nombre":       Path(ruta).name,
        "score_global": score_global,
        "slides":       slides_resultado,
    }
    
    
def exportar_resultado_json(resultado: dict) -> dict:
    """
    Transforma el resultado de analizar_presentacion() a un dict
    limpio y serializable, listo para JSON o para la GUI.

    Estructura de salida:
    {
        "presentacion": {
            "nombre":       str,
            "score_global": float,
            "zona_global":  str,
            "desglose": {
                "icd": float,
                "wps": float,
                "hss": float,
                "nts": float
            }
        },
        "diapositivas": [
            {
                "numero":   int,
                "tipo":     str,
                "omitida":  bool,

                // Solo si omitida=False:
                "score":    float,
                "zona":     str,
                "metricas": {
                    "icd": { "valor": float, "zona": str,  "aprobada": bool },
                    "wps": { "palabras": int,               "aprobada": bool },
                    "hss": { "coherencia": str,             "aprobada": bool },
                    "nts": { "estado": str,                 "aprobada": bool }
                },
                "aspectos_a_mejorar": ["icd", "wps", ...],

                "feedback": {
                    "icd":           str | null,
                    "wps":           str | null,
                    "hss":           str | null,
                    "nts":           str | null,
                    "preguntas":     [str, ...],
                    "datos_curiosos": [str, ...]
                } | null,

                "reestructura": {
                    "exito":    bool,
                    "intentos": int,
                    "diapositivas": [
                        {
                            "titulo":    str,
                            "contenido": [str, ...]
                        },
                        ...
                    ],
                    "metricas_pendientes": [str, ...]
                } | null
            },
            ...
        ]
    }
    """
    sg = resultado["score_global"]

    salida = {
        "presentacion": {
            "nombre":       resultado["nombre"],
            "score_global": sg["score_global"],
            "zona_global":  sg["zona_global"],
            "desglose": {
                "icd": sg["scores_metrica"]["icd"],
                "wps": sg["scores_metrica"]["wps"],
                "hss": sg["scores_metrica"]["hss"],
                "nts": sg["scores_metrica"]["nts"],
            },
        },
        "diapositivas": [],
    }

    for slide in resultado["slides"]:
        n = slide["slide_number"]

        # ── Slide omitida (portada, índice, etc.) ─────────────────────────
        if slide["omitida"]:
            salida["diapositivas"].append({
                "numero":  n,
                "tipo":    slide["tipo"],
                "omitida": True,
            })
            continue

        ss  = slide["score"]
        raw = slide["metricas_raw"]

        # ── Métricas individuales normalizadas ────────────────────────────
        metricas_limpias = {
            "icd": {
                "valor":    raw["icd"].get("icd"),
                "zona":     raw["icd"].get("zona"),
                "aprobada": "icd" not in ss["aspectos_mejorar"],
            },
            "wps": {
                "palabras": raw["wps"].get("palabras"),
                "aprobada": "wps" not in ss["aspectos_mejorar"],
            },
            "hss": {
                "coherencia": raw["hss"].get("coherencia"),
                "aprobada":   "hss" not in ss["aspectos_mejorar"],
            },
            "nts": {
                "estado":   raw["nts"].get("estado"),
                "aprobada": "nts" not in ss["aspectos_mejorar"],
            },
        }

        # ── Feedback ──────────────────────────────────────────────────────
        fb = slide["feedback"]
        feedback_limpio = None
        if fb:
            feedback_limpio = {
                "icd":           fb.get("icd"),
                "wps":           fb.get("wps"),
                "hss":           fb.get("hss"),
                "nts":           fb.get("nts"),
                "preguntas":     fb.get("preguntas", []),
                "datos_curiosos": fb.get("datos_curiosos", []),
            }

        # ── Reestructura ──────────────────────────────────────────────────
        re = slide["restructura"]
        restructura_limpia = None
        if re:
            restructura_limpia = {
                "exito":    re["exito"],
                "intentos": re["intentos"],
                "diapositivas": [
                    {
                        "titulo":    d["titulo"],
                        "contenido": d["contenido"],
                    }
                    for d in re["diapositivas"]
                ],
                "metricas_pendientes": re.get("metricas_fallidas_final", []),
            }

        salida["diapositivas"].append({
            "numero":             n,
            "tipo":               slide["tipo"],
            "omitida":            False,
            "score":              ss["score"],
            "zona":               ss["zona"],
            "metricas":           metricas_limpias,
            "aspectos_a_mejorar": ss["aspectos_mejorar"],
            "feedback":           feedback_limpio,
            "reestructura":       restructura_limpia,
        })

    return salida