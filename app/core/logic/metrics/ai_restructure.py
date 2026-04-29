# app/core/logic/metrics/ai_restructure.py
import json
import re
from typing import Dict, Any, List
from app.infrastructure.ai.llm_provider import consultar_modelo
from app.infrastructure.ai.prompts import PROMPT_REESTRUCTURACION_LOTE

def reestructurar_diapositivas_lote(diapositivas_a_corregir: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    if not diapositivas_a_corregir: return {}

    carga_lote = []
    for diapositiva in diapositivas_a_corregir:
        contenido_original = " ".join(diapositiva.get("content", [])) if "content" in diapositiva else ""
        carga_lote.append({
            "slide_number": diapositiva["slide_number"],
            "contenido_original": contenido_original[:1500],
            "requiere_reestructuracion": diapositiva.get("requiere_reestructuracion", True)
        })

    prompt = PROMPT_REESTRUCTURACION_LOTE.format(batch_data=json.dumps(carga_lote, ensure_ascii=False, indent=2))
    print("[IA REESTRUCTURACION] Generando Material Extra y Evaluando Reestructuraciones...")
    respuesta = consultar_modelo(prompt)
    
    mapa_reestructurado = {}
    try:
        match_json = re.search(r'\[\s*\{.*\}\s*\]', respuesta, re.DOTALL)
        if match_json:
            json_limpio = re.sub(r'[\n\r\t]+', ' ', match_json.group())
            lista_datos_ia = json.loads(json_limpio, strict=False)
            for item in lista_datos_ia:
                mapa_reestructurado[item.get("slide_number")] = item
    except Exception as e:
        print(f"[ERROR IA REESTRUCTURACION] Fallo al parsear JSON: {e}")

    return mapa_reestructurado