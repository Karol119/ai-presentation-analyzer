"""
analyzer_controller.py
Orchestrator for presentation analysis. 
Implements concurrent execution (multithreading) to separate fast local metrics (CPU-bound)
from slow AI-driven metrics (I/O-bound).
"""

import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

# --- 1. Importaciones de Extracción y Clasificación ---
from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.slide_classifier import clasificar_diapositiva # (Asumo que esta la traduciremos luego o ya la tienes)

# --- 2. Importaciones de Métricas Locales (Rápidas) ---
from app.core.logic.metrics.icd import calculate_presentation_icd
from app.core.logic.metrics.word_count import calculate_presentation_wps

# --- 3. Importaciones de Score ---
from app.core.logic.presentation_score import calculate_global_score, calculate_slide_score

_SKIPPED_TYPES = {"portada", "indice", "referencias", "cierre", "sin_contenido"}

def _run_local_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    WORKER 1 (CPU-Bound): Ejecuta las métricas matemáticas y de conteo.
    Esto ocurre en un hilo separado y termina casi instantáneamente.
    """
    icd_result = calculate_presentation_icd(content_slides)
    wps_result = calculate_presentation_wps(content_slides)
    
    return {
        "icd": icd_result,
        "wps": wps_result
    }

def analyze_presentation(file_path: str, status_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Ejecuta el pipeline completo de análisis sobre un archivo .pptx usando hilos.
    """
    
    if status_cb:
        status_cb("[PROGRESO] Extrayendo texto y elementos de la presentación...")
        
    extracted_data = extract_pptx_data(file_path)
    
    if status_cb:
        status_cb("[PROGRESO] Clasificando diapositivas...")
        
    # --- 1. Clasificación ---
    for slide in extracted_data["slides"]:
        # Aquí eventualmente pondremos el llamado a Ollama si aplica, 
        # por ahora lo dejamos con la lógica base.
        slide["clasificacion"] = clasificar_diapositiva(slide, llm_fn=None)

    content_slides = [
        s for s in extracted_data["slides"] 
        if not s.get("clasificacion", {}).get("excluir", False)
    ]

    if status_cb:
        status_cb("[PROGRESO] Calculando métricas locales (ICD y WPS)...")

    # --- 2. Ejecución Concurrente (Multithreading) ---
    # Usamos ThreadPoolExecutor para manejar los hilos. Preparamos el espacio para 2 trabajadores.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        
        # DISPARAMOS EL HILO 1: Métricas Locales
        local_metrics_future = executor.submit(_run_local_metrics, content_slides)
        
        # (AQUÍ DISPARAREMOS EL HILO 2: Métricas de IA en el próximo paso)
        # ai_metrics_future = executor.submit(_run_ai_metrics, content_slides)
        
        # ESPERAMOS A QUE TERMINE EL HILO (Sincronización)
        local_results = local_metrics_future.result()
        
    # Desempaquetamos los resultados del hilo
    res_icd = local_results["icd"]
    res_wps = local_results["wps"]
    
    # (Por ahora creamos diccionarios vacíos para las métricas de IA que aún no conectamos)
    res_hss = {"resultados": [], "hss_promedio": 0.0}
    res_nts = {"resultados": [], "nts_promedio": 0.0}

    # --- 3. Construcción del Score Global ---
    if status_cb:
        status_cb("[PROGRESO] Integrando resultados y calculando Score Global...")
        
    global_score = calculate_global_score(res_icd, res_wps, res_hss, res_nts)

    # --- 4. Construcción de resultados por slide ---
    final_slides = []

    for idx, slide in enumerate(content_slides):
        slide_num = slide["slide_number"]
        slide_type = slide.get("clasificacion", {}).get("tipo", "contenido")
        
        if slide_type in _SKIPPED_TYPES:
            final_slides.append({
                "slide_number": slide_num,
                "tipo":         slide_type,
                "omitida":      True,
                "score":        None,
                "metricas_raw": None,
                "feedback":     None,
                "restructura":  None,
            })
            continue

        # Extraemos los resultados locales calculados por el hilo
        mi = next((r for r in res_icd.get("resultados", []) if r["slide_number"] == slide_num), {})
        mw = next((r for r in res_wps.get("resultados", []) if r["slide_number"] == slide_num), {})
        
        # Calculamos el score individual de esta diapositiva
        slide_score = calculate_slide_score(mi, mw, {}, {}) # Se pasan diccionarios vacíos para HSS y NTS por ahora
        
        final_slides.append({
            "slide_number": slide_num,
            "tipo":         slide_type,
            "omitida":      False,
            "score":        slide_score,
            "metricas_raw": {"icd": mi, "wps": mw, "hss": {}, "nts": {}},
            "feedback":     None,
            "restructura":  None,
        })

    if status_cb:
        status_cb("[PROGRESO] ¡Análisis de métricas locales completado!")

    return {
        "nombre":       Path(file_path).name,
        "score_global": global_score,
        "slides":       final_slides,
    }