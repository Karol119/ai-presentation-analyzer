import json
import re
from typing import Dict, Any, List

from app.infrastructure.ai.llm_provider import query_model
from app.infrastructure.ai.prompts import BATCH_EVALUATION_PROMPT

# Importamos las utilidades matemáticas puras que dejamos en los otros archivos
from app.core.logic.metrics.header_structure import _get_keywords, _filter_person_names, _classify_hss_score
from app.core.logic.metrics.narrative_thread import _vectorize, _cosine_similarity, _full_text, _determine_status_from_score

def calculate_ai_metrics_batch(slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Procesa TODAS las diapositivas en una sola llamada a la API de la IA (Gemini/Mistral).
    Realiza 3 tareas: Clasificación, cálculo de HSS y cálculo de NTS simultáneamente.
    """
    if not slides:
        return {"hss": _empty_hss(), "nts": _empty_nts(), "clasificaciones": {}}

    # --- 1. PREPARAR EL PAQUETE (Diagnósticos Matemáticos Locales) ---
    batch_payload = []
    
    for i, current_slide in enumerate(slides):
        prev_slide = slides[i-1] if i > 0 else None
        
        # Cálculo Local HSS
        title = current_slide.get("title", "").strip()
        clean_content = _filter_person_names(" ".join(current_slide.get("content", [])))
        title_kw = _get_keywords(title)
        content_kw = _get_keywords(clean_content)
        overlap = title_kw.intersection(content_kw)
        
        # Cálculo Local NTS
        v_curr = _vectorize(_full_text(current_slide))
        v_prev = _vectorize(_full_text(prev_slide)) if prev_slide else {}
        cosine_score = _cosine_similarity(v_prev, v_curr) if prev_slide else 1.0

        batch_payload.append({
            "slide_number": current_slide.get("slide_number"),
            "titulo": title if title else "[SIN TÍTULO]",
            "contenido_truncado": clean_content[:400] + "..." if len(clean_content) > 400 else clean_content,
            "hss_diagnostico": {
                "solapamiento_lexico": list(overlap) if overlap else "Ninguno"
            },
            "nts_diagnostico": {
                "similitud_coseno": round(cosine_score, 4)
            }
        })

    # --- 2. LLAMADA ÚNICA AL LLM ---
    prompt = BATCH_EVALUATION_PROMPT.format(batch_data=json.dumps(batch_payload, ensure_ascii=False, indent=2))
    
    print("[AI BATCH] Evaluando lote en la IA (Clasificación + HSS + NTS)...")
    response = query_model(prompt)

    # --- 3. PARSEAR LA RESPUESTA EN LOTE ---
    ai_results_map = {}
    try:
        # Extraemos solo el arreglo JSON [...] para evitar el texto de relleno que suele poner la IA
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            ai_data_list = json.loads(json_match.group())
            for item in ai_data_list:
                ai_results_map[item.get("slide_number")] = item
        else:
            raise ValueError("No se detectó un arreglo JSON válido en la respuesta de la IA.")
    except Exception as e:
        print(f"[AI BATCH ERROR] Fallo al parsear JSON de la IA: {e}")
        # El mapa quedará vacío, por lo que usaremos valores por defecto abajo

    # --- 4. RECONSTRUIR ESTRUCTURAS PARA EL ORQUESTADOR ---
    hss_results = []
    nts_results = []
    clasificaciones = {}

    hss_valid_scores = []
    nts_valid_scores = []

    for i, slide in enumerate(slides):
        slide_num = slide.get("slide_number")
        ai_data = ai_results_map.get(slide_num, {})
        
        # a) Extraer Clasificación
        tipo_diapositiva = ai_data.get("tipo", "contenido").lower()
        clasificaciones[slide_num] = tipo_diapositiva
        is_content = (tipo_diapositiva == "contenido")

        # b) Ensamblar HSS Individual (Manejo de nulls)
        raw_hss_score = ai_data.get("hss_score")
        hss_score = float(raw_hss_score) if raw_hss_score is not None and is_content else 5.0
        
        if is_content: 
            hss_valid_scores.append(hss_score)

        hss_results.append({
            "slide_number": slide_num,
            "tiene_titulo": bool(slide.get("title", "").strip()),
            "titulo": slide.get("title", ""),
            "hss_score": hss_score if is_content else None,
            "coherencia": _classify_hss_score(hss_score) if is_content else "no_aplica",
            "feedback_ai": ai_data.get("hss_feedback", "") if is_content else None
        })

        # c) Ensamblar NTS Individual (Manejo de nulls)
        raw_nts_score = ai_data.get("nts_score")
        nts_score = float(raw_nts_score) if raw_nts_score is not None and is_content else 10.0
        
        if is_content: 
            nts_valid_scores.append(nts_score)

        prev_slide = slides[i-1] if i > 0 else None
        cosine_sim = _cosine_similarity(_vectorize(_full_text(prev_slide)), _vectorize(_full_text(slide))) if prev_slide else 1.0

        nts_results.append({
            "slide_number": slide_num,
            "sim_anterior": round(cosine_sim, 4) if prev_slide else None,
            "sim_promedio": round(cosine_sim, 4),
            "nts_score": nts_score if is_content else None,
            "estado": _determine_status_from_score(nts_score) if is_content else "no_aplica",
            "feedback_ai": ai_data.get("nts_feedback", "") if is_content else None
        })

    # --- 5. CALCULAR PROMEDIOS FINALES (Solo para diapositivas de "contenido") ---
    num_valid_hss = len(hss_valid_scores)
    num_valid_nts = len(nts_valid_scores)

    res_hss = {
        "resultados": hss_results,
        "hss_promedio": round(sum(hss_valid_scores) / num_valid_hss, 2) if num_valid_hss else 0.0,
        "slides_con_titulo": sum(1 for r in hss_results if r["tiene_titulo"] and r["coherencia"] != "no_aplica"),
        "slides_coherentes": sum(1 for r in hss_results if r["coherencia"] == "coherente"),
        "slides_debiles": sum(1 for r in hss_results if r["coherencia"] == "debil"),
        "slides_no_coherentes": sum(1 for r in hss_results if r["coherencia"] == "no_coherente")
    }

    res_nts = {
        "resultados": nts_results,
        "nts_promedio": round(sum(nts_valid_scores) / num_valid_nts, 2) if num_valid_nts else 0.0,
        "slides_relacionadas": sum(1 for r in nts_results if r["estado"] == "relacionada"),
        "slides_debiles": sum(1 for r in nts_results if r["estado"] == "debil"),
        "slides_desconectadas": sum(1 for r in nts_results if r["estado"] == "desconectada")
    }

    # Retornamos el paquete con las 3 tareas resueltas
    return {"hss": res_hss, "nts": res_nts, "clasificaciones": clasificaciones}

def _empty_hss() -> Dict[str, Any]: 
    return {"resultados": [], "hss_promedio": 0.0}

def _empty_nts() -> Dict[str, Any]: 
    return {"resultados": [], "nts_promedio": 0.0}