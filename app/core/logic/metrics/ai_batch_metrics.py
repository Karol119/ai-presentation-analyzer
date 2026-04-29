# app/core/logic/metrics/ai_batch_metrics.py
import json
import re
from typing import Dict, Any, List

from app.infrastructure.ai.llm_provider import query_model
from app.infrastructure.ai.prompts import BATCH_EVALUATION_PROMPT

# Importamos las utilidades matemáticas puras
from app.core.logic.metrics.header_structure import _get_keywords, _filter_person_names, _classify_hss_score
from app.core.logic.metrics.narrative_thread import _vectorize, _cosine_similarity, _full_text, _determine_status_from_score

def calculate_ai_metrics_batch(slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not slides:
        return {"hss": _empty_hss(), "nts": _empty_nts(), "clasificaciones": {}}

    # --- 1. PREPARAR EL PAQUETE (Diagnósticos Matemáticos Locales) ---
    batch_payload = []
    
    for i, current_slide in enumerate(slides):
        prev_slide = slides[i-1] if i > 0 else None
        
        title = current_slide.get("title", "").strip()
        clean_content = _filter_person_names(" ".join(current_slide.get("content", [])))
        title_kw = _get_keywords(title)
        content_kw = _get_keywords(clean_content)
        overlap = title_kw.intersection(content_kw)
        
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

    # --- 3. PARSEAR LA RESPUESTA EN LOTE (CON SANITIZACIÓN EXTREMA) ---
    ai_results_map = {}
    try:
        # Extraemos solo el arreglo JSON [...]
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            raw_json = json_match.group()
            
            # TRUCO ANTIFALLOS PARA MODELOS PEQUEÑOS (1.5B - 3B):
            # Eliminamos los saltos de línea reales (\n), retornos (\r) y tabulaciones (\t)
            # que el modelo haya incrustado ilegalmente dentro de las cadenas de texto.
            # Convertimos todo el JSON en una sola línea plana.
            clean_json = re.sub(r'[\n\r\t]+', ' ', raw_json)
            
            # Usamos strict=False para perdonar errores menores de sintaxis
            ai_data_list = json.loads(clean_json, strict=False)
            
            for item in ai_data_list:
                ai_results_map[item.get("slide_number")] = item
        else:
            raise ValueError("No se detectó un arreglo JSON válido en la respuesta.")
    except Exception as e:
        print(f"\n{'-'*60}")
        print(f"[AI BATCH ERROR] Fallo al parsear JSON de la IA: {e}")
        print(f"[DEBUG] Esto fue lo que escribió la IA y rompió el sistema:\n{response}")
        print(f"{'-'*60}\n")

    # --- 4. RECONSTRUIR ESTRUCTURAS PARA EL ORQUESTADOR ---
    hss_results = []
    nts_results = []
    clasificaciones = {}

    hss_valid_scores = []
    nts_valid_scores = []

    for i, slide in enumerate(slides):
        slide_num = slide.get("slide_number")
        
        # 1. Obtenemos los datos originales de la IA
        ia_original_data = ai_results_map.get(slide_num, {})
        
        # --- NUEVO: Extraemos el tiempo ANTES del cortafuegos ---
        # Si la IA no mandó el dato por alguna razón, asignamos 10 segundos por defecto
        tiempo_slide = ia_original_data.get("tiempo_estimado_segundos", 10)
        
        # Hacemos una copia para que el cortafuegos pueda vaciar ai_data sin borrar el tiempo original
        ai_data = ia_original_data.copy() 
        
        # --- CORTAFUEGOS LOCAL (LA REGLA DE ORO) ---
        texto_completo = slide.get("title", "") + " " + " ".join(slide.get("content", []))
        palabras_totales = len(texto_completo.split())
        imagenes = slide.get("image_count", 0)
        
        if imagenes > 0 and palabras_totales < 15:
            # Evadimos a la IA: Es una diapositiva visual
            tipo_diapositiva = "visual"
            ai_data = {} # Vaciamos los datos de IA para que no afecten métricas
        elif palabras_totales < 5:
            # Evadimos a la IA: Es un salto de sección
            tipo_diapositiva = "sin_contenido"
            ai_data = {}
        else:
            # Es contenido válido, confiamos en la clasificación de la IA
            tipo_diapositiva = ai_data.get("tipo", "contenido").lower()
            
        # --- MODIFICADO: Ahora guardamos un diccionario con el tipo y el tiempo ---
        clasificaciones[slide_num] = {
            "tipo": tipo_diapositiva,
            "tiempo": tiempo_slide
        }
        is_content = (tipo_diapositiva == "contenido")

        # --- Ensamblar HSS Individual ---
        raw_hss_score = ai_data.get("hss_score")
        hss_score = float(raw_hss_score) if raw_hss_score is not None and is_content else 5.0
        
        if is_content: hss_valid_scores.append(hss_score)

        hss_results.append({
            "slide_number": slide_num,
            "tiene_titulo": bool(slide.get("title", "").strip()),
            "titulo": slide.get("title", ""),
            "hss_score": hss_score if is_content else None,
            "coherencia": _classify_hss_score(hss_score) if is_content else "no_aplica",
            "feedback_ai": ai_data.get("hss_feedback", "") if is_content else None
        })

        # --- Ensamblar NTS Individual ---
        raw_nts_score = ai_data.get("nts_score")
        nts_score = float(raw_nts_score) if raw_nts_score is not None and is_content else 10.0
        
        if is_content: nts_valid_scores.append(nts_score)

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
        
    # --- 5. CALCULAR PROMEDIOS FINALES ---
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

    return {"hss": res_hss, "nts": res_nts, "clasificaciones": clasificaciones}

def _empty_hss() -> Dict[str, Any]: 
    return {"resultados": [], "hss_promedio": 0.0}

def _empty_nts() -> Dict[str, Any]: 
    return {"resultados": [], "nts_promedio": 0.0}