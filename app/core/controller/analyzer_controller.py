from app.core.logic.text_extractor                import extraer_datos_pptx
from app.core.logic.slide_classifier              import clasificar_diapositiva
from app.core.logic.metrics.icd                    import calcular_icd_presentacion
from app.core.logic.metrics.word_count             import calcular_wps_presentacion
from app.core.logic.metrics.header_structure       import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread       import calcular_nts
from app.core.logic.presentation_score             import calcular_score_global, calcular_score_slide
from app.core.logic.recommendation_prompt          import imprimir_tabla_diagnostico
from app.infrastructure.ollama.ollama_service      import clasificar_tipo_diapositiva, verificar_conexion
from app.infrastructure.ollama.coherencia_service  import verificar_coherencia_titulo
from app.infrastructure.ollama.recommendation_service import (
    generar_recomendacion_slide,
    generar_resumen_presentacion
)


def analizar_presentacion(ruta_pptx, usar_llm=True, generar_recomendaciones=True):
    llm_fn = llm_coh_fn = None
    llm_disponible = False

    if usar_llm:
        llm_disponible = verificar_conexion()
        if llm_disponible:
            llm_fn     = clasificar_tipo_diapositiva
            llm_coh_fn = verificar_coherencia_titulo
            print("[analyzer] Ollama disponible")
        else:
            print("[analyzer] Ollama no disponible — solo reglas")

    print(f"[analyzer] Extrayendo: {ruta_pptx}")
    datos = extraer_datos_pptx(ruta_pptx)
    print(f"[analyzer] {datos['total_slides']} diapositivas")

    conteo = {"contenido": 0, "excluidas": 0, "por_llm": 0, "inciertas": 0}
    for slide in datos["slides"]:
        clf = clasificar_diapositiva(slide, llm_fn=llm_fn)
        slide["clasificacion"] = clf
        if clf["excluir"]:          conteo["excluidas"] += 1
        else:                        conteo["contenido"]  += 1
        if clf["metodo"] == "llm":  conteo["por_llm"]    += 1
        if clf["confianza"] < 0.70: conteo["inciertas"]  += 1

    slides_contenido = [s for s in datos["slides"] if not s["clasificacion"]["excluir"]]

    print("[analyzer] Calculando métricas...")
    r_icd = calcular_icd_presentacion(slides_contenido)
    r_wps = calcular_wps_presentacion(slides_contenido)
    r_hss = calcular_hss_presentacion(slides_contenido, llm_fn=llm_coh_fn)
    r_nts = calcular_nts(slides_contenido)

    score_global = calcular_score_global(r_icd, r_wps, r_hss, r_nts)

    icd_map = {r["slide_number"]: r for r in r_icd.get("resultados", [])}
    wps_map = {r["slide_number"]: r for r in r_wps.get("resultados", [])}
    hss_map = {r["slide_number"]: r for r in r_hss.get("resultados", [])}
    nts_map = {r["slide_number"]: r for r in r_nts.get("resultados", [])}

    scores_slides = []
    for slide in slides_contenido:
        n  = slide["slide_number"]
        ss = calcular_score_slide(
            icd_map.get(n), wps_map.get(n),
            hss_map.get(n), nts_map.get(n)
        )
        ss["slide_number"] = n
        scores_slides.append(ss)

    sg = score_global
    print(f"\n[score] {sg['score_global']} ({sg['zona_global']}) — "
          f"ICD:{sg['scores_metrica']['icd']} "
          f"WPS:{sg['scores_metrica']['wps']} "
          f"HSS:{sg['scores_metrica']['hss']} "
          f"NTS:{sg['scores_metrica']['nts']}")
##-----------------------------------------------------------------------------------------
    recomendaciones   = []
    resumen_ejecutivo = None

    if generar_recomendaciones and llm_disponible:
        print("\n[rec] Generando recomendaciones...")
        slide_map = {s["slide_number"]: s for s in slides_contenido}

        for ss in scores_slides:
            n          = ss["slide_number"]
            slide_data = slide_map.get(n, {})
            rec        = generar_recomendacion_slide(slide_data, ss)
            recomendaciones.append(rec)

            # Log por slide
            if rec.get("necesitaba_rec"):
                if rec.get("slides_division"):
                    print(f"  [{n:02d}] DIVIDIR → {len(rec['slides_division'])} slides "
                          f"({rec.get('sugerencia_division','')})")
                elif rec.get("error"):
                    print(f"  [{n:02d}] ERROR: {rec['error']}")
                else:
                    v = rec.get("verificacion") or {}
                    ok = "✓ en rango" if v.get("wps_zona") == "optima" else f"WPS:{v.get('wps_zona','?')}"
                    print(f"  [{n:02d}] generada ({rec.get('intentos',1)} intentos) "
                          f"→ {v.get('palabras','?')} pal, ICD:{v.get('icd','?')} [{ok}]")
            elif rec.get("omitida_razon"):
                print(f"  [{n:02d}] omitida")

        resumen_ejecutivo = generar_resumen_presentacion(
            datos["filename"], score_global, r_icd, r_wps, r_hss, r_nts
        )
    elif generar_recomendaciones:
        print("[rec] Ollama no disponible")

    imprimir_tabla_diagnostico(scores_slides, r_icd, r_wps, r_hss, r_nts, recomendaciones)

    if resumen_ejecutivo:
        print(f"\n[Resumen para el docente]\n{resumen_ejecutivo}\n")

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