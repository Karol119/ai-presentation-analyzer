# app/core/logic/metrics/ai_restructure.py
import json
import re
from typing import Dict, Any, List
from app.infrastructure.ai.llm_provider import query_model
from app.infrastructure.ai.prompts import RESTRUCTURE_BATCH_PROMPT

def restructure_slides_batch(slides_to_fix: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    if not slides_to_fix: return {}

    batch_payload = []
    for slide in slides_to_fix:
        contenido_original = " ".join(slide.get("content", [])) if "content" in slide else ""
        batch_payload.append({
            "slide_number": slide["slide_number"],
            "contenido_original": contenido_original[:1500],
            "requiere_reestructuracion": slide.get("requiere_reestructuracion", True)
        })

    prompt = RESTRUCTURE_BATCH_PROMPT.format(batch_data=json.dumps(batch_payload, ensure_ascii=False, indent=2))
    print("[AI RESTRUCTURE] Generando Material Extra y Evaluando Reestructuraciones...")
    response = query_model(prompt)
    
    restructure_map = {}
    try:
        json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
        if json_match:
            clean_json = re.sub(r'[\n\r\t]+', ' ', json_match.group())
            ai_data_list = json.loads(clean_json, strict=False)
            for item in ai_data_list:
                restructure_map[item.get("slide_number")] = item
    except Exception as e:
        print(f"[AI RESTRUCTURE ERROR] Fallo al parsear JSON: {e}")

    return restructure_map