import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

# --- Importaciones de Lógica Core ---
from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.presentation_score import calculate_global_score, calculate_slide_score

# --- Importaciones de Métricas ---
from app.core.logic.metrics.icd import calculate_presentation_icd
from app.core.logic.metrics.word_count import calculate_presentation_wps
from app.core.logic.metrics.ai_batch_metrics import calculate_ai_metrics_batch
from app.core.logic.metrics.ai_restructure import restructure_slides_batch

# (Fíjate que aquí ya borramos las importaciones viejas de HSS y NTS)

def _run_local_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """WORKER 1 (CPU-Bound): Ejecuta métricas matemáticas (ICD, WPS)."""
    return {
        "icd": calculate_presentation_icd(content_slides),
        "wps": calculate_presentation_wps(content_slides)
    }

def _run_ai_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """WORKER 2 (I/O-Bound): Llama al motor de IA en Lote para Clasificación, HSS y NTS simultáneamente."""
    return calculate_ai_metrics_batch(content_slides)

def analyze_presentation(file_path: str, status_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Orquestador principal: Ejecuta el pipeline completo usando multithreading.
    """
    if status_cb: status_cb("[SISTEMA] Iniciando extracción de datos...")
    extracted_data = extract_pptx_data(file_path)
    
    # Tomamos todas las diapositivas extraídas. 
    content_slides = extracted_data["slides"]

    if status_cb: status_cb(f"[SISTEMA] Analizando {len(content_slides)} diapositivas en hilos paralelos...")

    # --- 1. EJECUCIÓN CONCURRENTE ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Lanzamos ambos hilos al mismo tiempo
        local_future = executor.submit(_run_local_metrics, content_slides)
        ai_future    = executor.submit(_run_ai_metrics, content_slides)
        
        # Esperamos resultados locales
        local_res = local_future.result()
        if status_cb: status_cb("[OK] Métricas locales completadas.")
        
        # Esperamos resultados de la IA (que incluye la clasificación)
        ai_res = ai_future.result()
        if status_cb: status_cb("[OK] Evaluación de IA y clasificación completadas.")

    # Desempaquetado de resultados
    res_icd, res_wps = local_res["icd"], local_res["wps"]
    res_hss, res_nts = ai_res["hss"], ai_res["nts"]
    clasificaciones_ia = ai_res.get("clasificaciones", {})

    # --- 2. Integración y Scoring ---
    from app.core.logic.metrics.ai_restructure import restructure_slides_batch
    if status_cb: status_cb("[SISTEMA] Calculando Score Global y consolidando feedback...")
    global_score = calculate_global_score(res_icd, res_wps, res_hss, res_nts)

    final_slides = []
    slides_para_enriquecer = []
    
    # Primera pasada
    for slide in content_slides:
        num = slide["slide_number"]
        tipo_detectado = clasificaciones_ia.get(num, "contenido")
        omitida = (tipo_detectado != "contenido")
        
        if omitida:
            final_slides.append({
                "slide_number": num,
                "tipo":         tipo_detectado,
                "omitida":      True,
                "score_slide":  None,
                "zona_slide":   None,
                "metricas":     None,
                "preguntas":    None,
                "datos_curiosos": None,
                "reestructuracion": None
            })
            continue

        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == num), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == num), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == num), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == num), {})
        
        slide_score_data = calculate_slide_score(mi, mw, mh, mn)
        estados = slide_score_data["estados"]
        necesita_reestructurar = slide_score_data["necesita_recomendacion"]

        slide_db_format = {
            "slide_number": num,
            "tipo":         tipo_detectado,
            "omitida":      False,
            "requiere_reestructuracion": necesita_reestructurar,
            "score_slide":  slide_score_data["score_total"],
            "zona_slide":   slide_score_data["zona"],
            "metricas": {
                "icd": {"valor": estados["icd"]["valor"], "estado": estados["icd"]["estado"], "feedback": mi.get("feedback_local")},
                "wps": {"valor": estados["wps"]["valor"], "estado": estados["wps"]["estado"], "feedback": mw.get("feedback_local")},
                "hss": {"valor": estados["hss"]["valor"], "estado": estados["hss"]["estado"], "feedback": mh.get("feedback_ai")},
                "nts": {"valor": estados["nts"]["valor"], "estado": estados["nts"]["estado"], "feedback": mn.get("feedback_ai")}
            },
            "preguntas": [],
            "datos_curiosos": [],
            "reestructuracion": None,
            "content": slide.get("content", []) 
        }
        
        final_slides.append(slide_db_format)
        slides_para_enriquecer.append(slide_db_format)

    # --- 4. Llamada al Motor de Enriquecimiento/Reestructuración ---
    if slides_para_enriquecer:
        if status_cb: status_cb("[SISTEMA] Generando Material Didáctico y Reestructurando...")
        mapa_reestructurado = restructure_slides_batch([
            {"slide_number": s["slide_number"], "content": s.pop("content"), "requiere_reestructuracion": s["requiere_reestructuracion"]} 
            for s in slides_para_enriquecer
        ])
        
        # Inyectamos los datos en nuestro JSON final
        for s in final_slides:
            if not s["omitida"]:
                datos_ai = mapa_reestructurado.get(s["slide_number"], {})
                s["preguntas"] = datos_ai.get("preguntas", [])
                s["datos_curiosos"] = datos_ai.get("datos_curiosos", [])
                
                arreglo_gen = datos_ai.get("diapositivas_generadas", [])
                s["reestructuracion"] = {"diapositivas_generadas": arreglo_gen} if arreglo_gen else None

    return {
        "score_global_presentacion": global_score, # Pasamos todo el objeto global con su desglose
        "slides": final_slides,
    }