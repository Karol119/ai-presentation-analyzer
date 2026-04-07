from app.core.logic.text_extractor               import extraer_datos_pptx
from app.core.logic.slide_classifier             import clasificar_diapositiva
from app.core.logic.metrics.icd                   import calcular_icd_presentacion
from app.core.logic.metrics.word_count            import calcular_wps_presentacion
from app.core.logic.metrics.header_structure      import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread      import calcular_nts
from app.infrastructure.ollama.ollama_service     import (
    clasificar_tipo_diapositiva,
    verificar_conexion
)
from app.infrastructure.ollama.coherencia_service import verificar_coherencia_titulo


def analizar_presentacion(ruta_pptx, usar_llm=True):
    """
    Análisis completo de una presentación:
        1. Extracción y zonificación del texto
        2. Clasificación de diapositivas
        3. ICD  — complejidad textual         (por slide)
        4. WPS  — palabras por diapositiva    (por slide)
        5. HSS  — estructura del encabezado   (por slide)
        6. NTS  — hilo narrativo              (entre slides)
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

    print(f"[analyzer] Extrayendo: {ruta_pptx}")
    datos = extraer_datos_pptx(ruta_pptx)
    print(f"[analyzer] {datos['total_slides']} diapositivas")

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

    slides_contenido = obtener_slides_contenido(datos)

    resultado_icd = calcular_icd_presentacion(slides_contenido)
    resultado_wps = calcular_wps_presentacion(slides_contenido)
    resultado_hss = calcular_hss_presentacion(slides_contenido, llm_fn=llm_coh_fn)
    resultado_nts = calcular_nts(slides_contenido)

    _log_resumen(resultado_icd, resultado_wps, resultado_hss, resultado_nts)

    datos["llm_disponible"]        = llm_disponible
    datos["resumen_clasificacion"] = conteo
    datos["icd"]                   = resultado_icd
    datos["wps"]                   = resultado_wps
    datos["hss"]                   = resultado_hss
    datos["nts"]                   = resultado_nts

    return datos


def obtener_slides_contenido(resultado):
    return [s for s in resultado["slides"] if not s["clasificacion"]["excluir"]]


def _log_resumen(icd, wps, hss, nts):
    print(f"\n{'─'*70}")
    if icd["icd_promedio"] is not None:
        print(f"[ICD] promedio:{icd['icd_promedio']}  zona:{icd['zona_promedio']}")
    print(f"[WPS] palabras_prom:{wps['palabras_promedio']}  "
          f"optimas:{wps['slides_optimas']}  escasas:{wps['slides_escasas']}  "
          f"densas:{wps['slides_densas']}  saturadas:{wps['slides_saturadas']}")
    print(f"[HSS] promedio:{hss['hss_promedio']}  "
          f"cobertura:{hss['cobertura_titulo']}%  "
          f"coherentes:{hss['slides_coherentes']}  "
          f"sin_titulo:{hss['slides_sin_titulo']}")
    print(f"[NTS] promedio:{nts['nts_promedio']}  "
          f"relacionadas:{nts['slides_relacionadas']}  "
          f"debiles:{nts['slides_debiles']}  "
          f"desconectadas:{nts['slides_desconectadas']}  "
          f"roturas:{len(nts['pares_rotura'])}")

    if nts["pares_rotura"]:
        print(f"  Roturas de hilo: " +
              ", ".join(f"[{p['entre'][0]}→{p['entre'][1]}]" for p in nts["pares_rotura"]))

    print(f"\n{'Slide':>5}  {'ICD':>5}  {'WPS':>5}  {'Pal':>4}  {'HSS':>5}  {'NTS':>5}  Estado NTS")
    print("─"*65)

    icd_map = {r["slide_number"]: r for r in icd["resultados"]}
    wps_map = {r["slide_number"]: r for r in wps["resultados"]}
    hss_map = {r["slide_number"]: r for r in hss["resultados"]}
    nts_map = {r["slide_number"]: r for r in nts["resultados"]}

    for num in sorted(set(list(icd_map) + list(wps_map))):
        i = icd_map.get(num, {})
        w = wps_map.get(num, {})
        h = hss_map.get(num, {})
        nt = nts_map.get(num, {})
        print(
            f"  [{num:02d}]"
            f"  {str(i.get('icd','—')):>5}"
            f"  {str(w.get('wps_score','—')):>5}"
            f"  {str(w.get('palabras','—')):>4}"
            f"  {str(h.get('hss_score','—')):>5}"
            f"  {str(nt.get('nts_score','—')):>5}"
            f"  {nt.get('estado','—')}"
        )