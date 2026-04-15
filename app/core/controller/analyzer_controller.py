import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

# --- Importaciones de Lógica Core ---
from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.presentation_score import calculate_global_score, calculate_slide_score

# --- Importaciones de Métricas ---
from app.core.logic.metrics.icd import calculate_presentation_icd
from app.core.logic.metrics.word_count import calculate_presentation_wps
from app.core.logic.metrics.header_structure import calculate_presentation_hss
from app.core.logic.metrics.ai_batch_metrics import calculate_ai_metrics_batch
from app.core.logic.metrics.narrative_thread import calculate_nts

def _run_local_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """WORKER 1 (CPU-Bound): Ejecuta métricas matemáticas (ICD, WPS)."""
    return {
        "icd": calculate_presentation_icd(content_slides),
        "wps": calculate_presentation_wps(content_slides)
    }

def _run_ai_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """WORKER 2 (I/O-Bound): Llama al motor de IA en Lote para HSS y NTS simultáneamente."""
    return calculate_ai_metrics_batch(content_slides)

def analyze_presentation(file_path: str, status_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Orquestador principal: Ejecuta el pipeline completo usando multithreading.
    """
    if status_cb: status_cb("[SISTEMA] Iniciando extracción de datos...")
    extracted_data = extract_pptx_data(file_path)
    
    # Tomamos todas las diapositivas extraídas. 
    # Ya no simulamos la clasificación local porque ahora la IA la hará en el batch.
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
    if status_cb: status_cb("[SISTEMA] Calculando Score Global y consolidando feedback...")
    global_score = calculate_global_score(res_icd, res_wps, res_hss, res_nts)

    final_slides = []
    
    # --- 3. Armado Final ---
    for slide in content_slides:
        num = slide["slide_number"]
        
        # ¡CORRECCIÓN AQUÍ! Buscamos el tipo que le dio la IA a ESTA diapositiva
        tipo_detectado = clasificaciones_ia.get(num, "contenido")
        omitida = (tipo_detectado != "contenido")
        
        # Si la IA dijo que es portada, índice, cierre, etc., la guardamos pero omitimos su score
        if omitida:
            final_slides.append({
                "slide_number": num,
                "tipo":         tipo_detectado,
                "omitida":      True,
                "score":        None,
                "metricas_raw": None,
                "feedback":     None,
                "restructura":  None,
            })
            continue # Saltamos a la siguiente diapositiva

        # Si sí es de "contenido", extraemos sus métricas individuales
        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == num), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == num), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == num), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == num), {})
        
        slide_score = calculate_slide_score(mi, mw, mh, mn)
        
        final_slides.append({
            "slide_number": num,
            "tipo":         tipo_detectado,
            "omitida":      False,
            "score":        slide_score,
            "metricas_raw": {"icd": mi, "wps": mw, "hss": mh, "nts": mn},
            "feedback": {
                "icd": mi.get("feedback_local"),
                "wps": mw.get("feedback_local"),
                "hss": mh.get("feedback_ai"), 
                "nts": mn.get("feedback_ai"), 
                "preguntas": [],
                "datos_curiosos": []
            },
            "restructura":  None
        })

    return {
        "nombre":       Path(file_path).name,
        "score_global": global_score,
        "slides":       final_slides,
    }