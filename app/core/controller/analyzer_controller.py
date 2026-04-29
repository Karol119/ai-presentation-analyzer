# app/core/controller/analyzer_controller.py
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.metrics.icd import calculate_presentation_icd
from app.infrastructure.ai.llm_provider import verify_ai_connection  # <-- Importación del Fail Fast
from app.core.logic.metrics.word_count import calculate_presentation_wps
from app.core.logic.metrics.ai_restructure import restructure_slides_batch
from app.core.logic.metrics.ai_batch_metrics import calculate_ai_metrics_batch
from app.core.logic.presentation_score import calculate_global_score, calculate_slide_score

def _run_local_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "icd": calculate_presentation_icd(content_slides),
        "wps": calculate_presentation_wps(content_slides)
    }

def _run_ai_metrics(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    return calculate_ai_metrics_batch(content_slides)

def analyze_presentation(file_path: str, status_cb: Optional[Callable] = None) -> Dict[str, Any]:
    
    # --- PRE-FLIGHT CHECK (FAIL FAST) ---
    if status_cb: status_cb("[SISTEMA] Comprobando estado del motor de Inteligencia Artificial...")
    try:
        verify_ai_connection()
    except Exception as e:
        if status_cb: status_cb("[CANCELADO] El análisis no pudo iniciar.")
        raise e # Detiene el programa instantáneamente antes de extraer datos

    # --- INICIO DEL PROCESO ---
    if status_cb: status_cb("[SISTEMA] Iniciando extracción de datos...")
    extracted_data = extract_pptx_data(file_path)
    
    total_diapositivas_pptx = extracted_data.get("total_slides", 0)
    content_slides = extracted_data["slides"]

    if status_cb: status_cb(f"[SISTEMA] Analizando {len(content_slides)} diapositivas en hilos paralelos...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        local_future = executor.submit(_run_local_metrics, content_slides)
        ai_future    = executor.submit(_run_ai_metrics, content_slides)
        
        try:
            local_res = local_future.result()
            if status_cb: status_cb("[OK] Métricas locales completadas.")
            
            ai_res = ai_future.result()
            if status_cb: status_cb("[OK] Evaluación de IA y clasificación completadas.")
        except Exception as e:
            if status_cb: status_cb("[CANCELADO] Proceso interrumpido por un error de IA.")
            raise e

    res_icd, res_wps = local_res["icd"], local_res["wps"]
    res_hss, res_nts = ai_res["hss"], ai_res["nts"]
    datos_ia_batch = ai_res.get("clasificaciones", {})

    final_slides = []
    slides_para_enriquecer = []
    tiempo_total_segundos = 0
    
    # Variables para calcular el score global sin trampas
    valid_slide_count = 0
    sum_icd = 0.0
    sum_wps = 0.0
    sum_hss = 0.0
    sum_nts = 0.0
    
    for slide in content_slides:
        num = slide["slide_number"]
        info_ia = datos_ia_batch.get(num, {"tipo": "contenido", "tiempo": 10})
        
        tipo_detectado = info_ia["tipo"]
        tiempo_slide = info_ia["tiempo"]
        tiempo_total_segundos += tiempo_slide
        
        omitida = (tipo_detectado != "contenido")
        
        if omitida:
            final_slides.append({
                "slide_number": num,
                "tipo":         tipo_detectado,
                "tiempo_exposicion": tiempo_slide,
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
        norm_vals = slide_score_data["valores_normalizados"]
        
        # Acumular para el global SOLO si no fue omitida
        valid_slide_count += 1
        sum_icd += norm_vals["icd"]
        sum_wps += norm_vals["wps"]
        sum_hss += norm_vals["hss"]
        sum_nts += norm_vals["nts"]
        
        necesita_reestructurar = slide_score_data["necesita_recomendacion"]
        feedback_combinado = f"ICD: {mi.get('feedback_local','')} | WPS: {mw.get('feedback_local','')} | HSS: {mh.get('feedback_ai','')} | NTS: {mn.get('feedback_ai','')}"

        slide_db_format = {
            "slide_number": num,
            "tipo":         tipo_detectado,
            "tiempo_exposicion": tiempo_slide,
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
            "content": slide.get("content", []),
            "feedback_combinado": feedback_combinado
        }
        
        final_slides.append(slide_db_format)
        slides_para_enriquecer.append(slide_db_format)

    # --- CÁLCULO DEL SCORE GLOBAL ESTRICTO ---
    if status_cb: status_cb("[SISTEMA] Calculando Score Global final...")
    if valid_slide_count > 0:
        global_score_data = calculate_global_score(
            sum_icd / valid_slide_count,
            sum_wps / valid_slide_count,
            sum_hss / valid_slide_count,
            sum_nts / valid_slide_count
        )
    else:
        global_score_data = calculate_global_score(0, 0, 0, 0)

    if slides_para_enriquecer:
        if status_cb: status_cb("[SISTEMA] Generando Material Didáctico y Reestructurando...")
        try:
            mapa_reestructurado = restructure_slides_batch([
                {
                    "slide_number": s["slide_number"], 
                    "content": s.pop("content"), 
                    "requiere_reestructuracion": s["requiere_reestructuracion"],
                    "feedback_a_corregir": s.pop("feedback_combinado")
                } 
                for s in slides_para_enriquecer
            ])
        except Exception as e:
            if status_cb: status_cb("[CANCELADO] El enriquecimiento fue interrumpido.")
            raise e
        
        for s in final_slides:
            if not s["omitida"]:
                datos_ai = mapa_reestructurado.get(s["slide_number"], {})
                s["preguntas"] = datos_ai.get("preguntas", [])
                s["datos_curiosos"] = datos_ai.get("datos_curiosos", [])
                arreglo_gen = datos_ai.get("diapositivas_generadas", [])
                s["reestructuracion"] = {"diapositivas_generadas": arreglo_gen} if arreglo_gen else None

    return {
        "total_diapositivas": total_diapositivas_pptx,
        "score_global_presentacion": global_score_data,
        "tiempo_total_exposicion_segundos": tiempo_total_segundos,
        "tiempo_total_formateado": f"{tiempo_total_segundos // 60}m {tiempo_total_segundos % 60}s",
        "slides": final_slides,
    }