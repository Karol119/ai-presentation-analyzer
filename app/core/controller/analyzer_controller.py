from app.core.logic.text_extractor    import extraer_datos_pptx
from app.core.logic.slide_classifier  import clasificar_diapositiva
from app.core.logic.metrics.icd       import calcular_icd_presentacion
from app.infrastructure.ollama.ollama_service import (
    clasificar_tipo_diapositiva,
    verificar_conexion
)


def analizar_presentacion(ruta_pptx, usar_llm=True):
    """
    Orquesta el análisis completo:
        1. Extracción y zonificación del texto
        2. Clasificación de cada diapositiva
        3. Cálculo del ICD para las diapositivas de contenido

    Returns:
        {
            "filename":              str,
            "total_slides":          int,
            "llm_disponible":        bool,
            "resumen_clasificacion": dict,
            "icd":                   dict,   ← nuevo
            "slides":                list
        }
    """
    # ── Paso 1: verificar LLM ─────────────────────────────────────────────────
    llm_fn = None
    llm_disponible = False

    if usar_llm:
        llm_disponible = verificar_conexion()
        if llm_disponible:
            llm_fn = clasificar_tipo_diapositiva
            print("[analyzer] Ollama disponible")
        else:
            print("[analyzer] Ollama no disponible — solo reglas")

    # ── Paso 2: extracción ────────────────────────────────────────────────────
    print(f"[analyzer] Extrayendo: {ruta_pptx}")
    datos = extraer_datos_pptx(ruta_pptx)
    print(f"[analyzer] {datos['total_slides']} diapositivas")

    # ── Paso 3: clasificación ─────────────────────────────────────────────────
    conteo = {"contenido": 0, "excluidas": 0, "por_llm": 0, "inciertas": 0}

    for slide in datos["slides"]:
        clasificacion = clasificar_diapositiva(slide, llm_fn=llm_fn)
        slide["clasificacion"] = clasificacion

        if clasificacion["excluir"]:
            conteo["excluidas"] += 1
        else:
            conteo["contenido"] += 1

        if clasificacion["metodo"] == "llm":
            conteo["por_llm"] += 1

        if clasificacion["confianza"] < 0.70:
            conteo["inciertas"] += 1

        print(f"  [{slide['slide_number']:02d}] {clasificacion['tipo']:<14} "
              f"conf:{clasificacion['confianza']:.2f}  {clasificacion['metodo']}")

    # ── Paso 4: cálculo ICD ───────────────────────────────────────────────────
    slides_contenido = obtener_slides_contenido(datos)
    resultado_icd    = calcular_icd_presentacion(slides_contenido)

    _log_icd(resultado_icd)

    # ── Resultado final ───────────────────────────────────────────────────────
    datos["llm_disponible"]        = llm_disponible
    datos["resumen_clasificacion"] = conteo
    datos["icd"]                   = resultado_icd

    return datos


def obtener_slides_contenido(resultado):
    return [s for s in resultado["slides"] if not s["clasificacion"]["excluir"]]


def _log_icd(resultado_icd):
    if resultado_icd["icd_promedio"] is None:
        print("[analyzer] Sin diapositivas con texto suficiente para ICD")
        return

    print(f"\n[ICD] Promedio: {resultado_icd['icd_promedio']} "
          f"({resultado_icd['zona_promedio']})  "
          f"min:{resultado_icd['icd_minimo']}  "
          f"max:{resultado_icd['icd_maximo']}")

    for r in resultado_icd["resultados"]:
        if r["calculable"]:
            print(f"  [{r['slide_number']:02d}] ICD:{r['icd']:<5} "
                  f"zona:{r['zona']:<14} "
                  f"CF:{r['cf']:.2f} DLN:{r['dln']:.2f} "
                  f"FSZ:{r['fsz']:.1f} DL:{r['dl']:.1f}%")
        else:
            print(f"  [{r['slide_number']:02d}] sin texto suficiente")