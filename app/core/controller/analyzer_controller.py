# app/core/controller/analyzer_controller.py
from app.core.logic.text_extractor                import extraer_datos_pptx
from app.core.logic.slide_classifier              import clasificar_diapositiva
from app.core.logic.metrics.icd                    import calcular_icd_presentacion
from app.core.logic.metrics.word_count             import calcular_wps_presentacion
from app.core.logic.metrics.header_structure       import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread       import calcular_nts
from app.core.logic.presentation_score             import calcular_score_global, calcular_score_slide
from app.infrastructure.ollama.ollama_service      import clasificar_tipo_diapositiva, verificar_conexion
from app.infrastructure.ollama.coherencia_service  import verificar_coherencia_titulo
from app.infrastructure.ollama.recommendation_service import (
    generar_recomendacion_slide,
    generar_resumen_presentacion
)


def analizar_presentacion(ruta_pptx, usar_llm=True, generar_recomendaciones=True):
    """
    Pipeline completo:
        1. Extracción
        2. Clasificación
        3. ICD, WPS, HSS, NTS
        4. Score global
        5. Recomendaciones por slide (solo las que lo necesitan)
        6. Resumen ejecutivo

    Args:
        ruta_pptx:              ruta al archivo .pptx
        usar_llm:               usar Ollama para clasificación y coherencia
        generar_recomendaciones: llamar a la API para recomendaciones
    """
    llm_fn     = None
    llm_coh_fn = None
    llm_disponible = False

    if usar_llm:
        llm_disponible = verificar_conexion()
        if llm_disponible:
            llm_fn     = clasificar_tipo_diapositiva
            llm_coh_fn = verificar_coherencia_titulo
            print("[analyzer] Ollama disponible")
        else:
            print("[analyzer] Ollama no disponible — solo reglas")

    # ── 1 + 2: Extracción y clasificación ────────────────────────────────────
    print(f"[analyzer] Extrayendo: {ruta_pptx}")
    datos = extraer_datos_pptx(ruta_pptx)
    print(f"[analyzer] {datos['total_slides']} diapositivas")

    conteo = {"contenido": 0, "excluidas": 0, "por_llm": 0, "inciertas": 0}
    for slide in datos["slides"]:
        clf = clasificar_diapositiva(slide, llm_fn=llm_fn)
        slide["clasificacion"] = clf
        if clf["excluir"]:            conteo["excluidas"] += 1
        else:                          conteo["contenido"] += 1
        if clf["metodo"] == "llm":    conteo["por_llm"] += 1
        if clf["confianza"] < 0.70:   conteo["inciertas"] += 1

    slides_contenido = [s for s in datos["slides"] if not s["clasificacion"]["excluir"]]

    # ── 3: Métricas ───────────────────────────────────────────────────────────
    print("[analyzer] Calculando métricas...")
    r_icd = calcular_icd_presentacion(slides_contenido)
    r_wps = calcular_wps_presentacion(slides_contenido)
    r_hss = calcular_hss_presentacion(slides_contenido, llm_fn=llm_coh_fn)
    r_nts = calcular_nts(slides_contenido)

    # ── 4: Score global ───────────────────────────────────────────────────────
    score_global = calcular_score_global(r_icd, r_wps, r_hss, r_nts)

    # Score por slide
    icd_map = {r["slide_number"]: r for r in r_icd.get("resultados", [])}
    wps_map = {r["slide_number"]: r for r in r_wps.get("resultados", [])}
    hss_map = {r["slide_number"]: r for r in r_hss.get("resultados", [])}
    nts_map = {r["slide_number"]: r for r in r_nts.get("resultados", [])}

    scores_slides = []
    for slide in slides_contenido:
        num = slide["slide_number"]
        ss = calcular_score_slide(
            icd_map.get(num), wps_map.get(num),
            hss_map.get(num), nts_map.get(num)
        )
        ss["slide_number"] = num
        scores_slides.append(ss)

    print(f"[score] Global: {score_global['score_global']} ({score_global['zona_global']})")
    slides_con_rec = sum(1 for s in scores_slides if s["necesita_recomendacion"])
    print(f"[score] {slides_con_rec}/{len(scores_slides)} slides necesitan recomendación")

    # ── 5: Recomendaciones ────────────────────────────────────────────────────
    recomendaciones = []
    resumen_ejecutivo = None

    if generar_recomendaciones and llm_disponible:
        print("[rec] Generando recomendaciones...")
        slide_map = {s["slide_number"]: s for s in slides_contenido}

        for ss in scores_slides:
            num       = ss["slide_number"]
            slide_data = slide_map.get(num, {})
            rec = generar_recomendacion_slide(slide_data, ss)
            recomendaciones.append(rec)
            if rec["necesitaba_rec"]:
                status = "OK" if not rec.get("error") else f"ERROR: {rec['error']}"
                print(f"  [{num:02d}] {status}")

        resumen_ejecutivo = generar_resumen_presentacion(
            datos["filename"], score_global, r_icd, r_wps, r_hss, r_nts
        )
    elif generar_recomendaciones and not llm_disponible:
        print("[rec] Ollama no disponible — recomendaciones omitidas")

    # ── Resultado final ───────────────────────────────────────────────────────
    datos.update({
        "llm_disponible":        llm_disponible,
        "resumen_clasificacion": conteo,
        "icd":                   r_icd,
        "wps":                   r_wps,
        "hss":                   r_hss,
        "nts":                   r_nts,
        "score_global":          score_global,
        "scores_slides":         scores_slides,
        "recomendaciones":       recomendaciones,
        "resumen_ejecutivo":     resumen_ejecutivo,
    })

    return datos