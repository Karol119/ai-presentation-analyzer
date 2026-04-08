# app/infrastructure/ollama/recommendation_service.py
"""
recommendation_service.py
Servicio que orquesta las llamadas a la API para generar recomendaciones.

Flujo por diapositiva:
    1. Calcular score_slide (presentation_score.py)
    2. Si necesita_recomendacion → generar prompt (recommendation_prompt.py)
    3. Llamar a la API de Ollama
    4. Parsear JSON de respuesta
    5. Devolver recomendación estructurada

La API solo se llama cuando hay aspectos que mejorar.
Aspectos marcados como BIEN nunca se envían para modificación.
"""

import json
import re
import requests

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "llama3.2"
TIMEOUT_SEG = 30   # recomendaciones toman más tiempo que clasificaciones


def generar_recomendacion_slide(slide_data, score_slide):
    """
    Genera la recomendación para una diapositiva si la necesita.

    Returns:
        {
            "slide_number":     int,
            "necesitaba_rec":   bool,
            "titulo_nuevo":     str | None,
            "contenido_nuevo":  str | None,
            "cambios_realizados": [str],
            "justificacion":    str | None,
            "error":            str | None
        }
    """
    from app.core.logic.recommendation_prompt import generar_prompt_recomendacion

    num = score_slide.get("slide_number")
    base = {
        "slide_number":      num,
        "necesitaba_rec":    False,
        "titulo_nuevo":      None,
        "contenido_nuevo":   None,
        "cambios_realizados": [],
        "justificacion":     None,
        "error":             None,
    }

    if not score_slide.get("necesita_recomendacion"):
        return base

    base["necesitaba_rec"] = True
    prompt = generar_prompt_recomendacion(slide_data, score_slide)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,   # baja temperatura = más determinismo
                    "num_predict": 800,
                }
            },
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        texto = response.json().get("response", "").strip()

        resultado = _parsear_json_respuesta(texto)
        if resultado:
            base.update({
                "titulo_nuevo":      resultado.get("titulo_nuevo"),
                "contenido_nuevo":   resultado.get("contenido_nuevo"),
                "cambios_realizados": resultado.get("cambios_realizados", []),
                "justificacion":     resultado.get("justificacion"),
            })
        else:
            base["error"] = "Respuesta no parseable como JSON"

    except requests.exceptions.Timeout:
        base["error"] = f"Timeout después de {TIMEOUT_SEG}s"
    except Exception as e:
        base["error"] = str(e)

    return base


def generar_resumen_presentacion(nombre, score_global, icd, wps, hss, nts):
    """
    Genera el resumen ejecutivo de la presentación completa.

    Returns:
        str — texto del reporte para el profesor
    """
    from app.core.logic.recommendation_prompt import generar_prompt_resumen

    prompt = generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  MODELO,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 300}
            },
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

    except Exception as e:
        return f"[Error generando resumen: {e}]"


def _parsear_json_respuesta(texto):
    """
    Extrae y parsea el JSON de la respuesta del LLM.
    Maneja casos donde el modelo agrega texto antes o después del JSON.
    """
    # Intentar parseo directo
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Buscar bloque JSON entre llaves
    match = re.search(r'\{.*\}', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Limpiar marcadores de código markdown
    limpio = re.sub(r'```(?:json)?', '', texto).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError:
        pass

    return None