"""
recommendation_service.py — v3

Correcciones:
  1. num_predict aumentado a 1500 para slides largas
  2. Slides IRREDUCIBLE NO generan recomendación — solo se reportan
  3. Slides WPS escasa con imagen o < 20 palabras no se mandan a recomendación
  4. Slides saturadas reciben instrucción de dividir, no solo resumir
  5. Reintento sin JSON forzado si el primer intento falla
"""

import json
import re
import requests

OLLAMA_URL   = "http://localhost:11434/api/generate"
MODELO       = "llama3.2"
TIMEOUT_SEG  = 45
MAX_CONTENIDO_CHARS = 800   # Límite de chars del contenido original en el prompt


def generar_recomendacion_slide(slide_data, score_slide):
    """
    Genera la recomendación para una diapositiva si la necesita.
    Respeta los casos donde no es posible ni necesario recomendar.
    """
    from app.core.logic.recommendation_prompt import generar_prompt_recomendacion

    num   = score_slide.get("slide_number")
    metr  = score_slide.get("metricas", {})

    base = {
        "slide_number":       num,
        "necesitaba_rec":     False,
        "omitida_razon":      None,
        "titulo_nuevo":       None,
        "contenido_nuevo":    None,
        "sugerencia_division": None,
        "cambios_realizados": [],
        "justificacion":      None,
        "error":              None,
    }

    if not score_slide.get("necesita_recomendacion"):
        return base

    # ── Caso 1: ICD irreducible — reportar pero no recomendar ────────────────
    icd_m = metr.get("icd", {})
    if icd_m.get("irreducible"):
        base["omitida_razon"] = (
            "El texto tiene vocabulario técnico especializado de nivel posgrado "
            "que no puede simplificarse sin alterar el contenido académico. "
            "Se recomienda al docente revisar si el nivel es apropiado para sus alumnos."
        )
        return base

    # ── Caso 2: WPS escasa con poco texto real — no penalizar ────────────────
    wps_m = metr.get("wps", {})
    solo_mejora_wps = score_slide.get("aspectos_mejorar") == ["wps"]
    if solo_mejora_wps:
        palabras     = wps_m.get("palabras", 0)
        tiene_imagen = slide_data.get("images", [])
        # Si tiene imagen o tiene menos de 20 palabras y solo falla WPS,
        # no tiene sentido pedirle que agregue texto
        if tiene_imagen or palabras < 20:
            base["omitida_razon"] = (
                "La diapositiva tiene poco texto pero está acompañada de elementos visuales "
                "o es una diapositiva de concepto clave. No se requiere ampliar el texto."
                if tiene_imagen else
                "La diapositiva tiene muy poco texto. Considere si es intencional "
                "(diapositiva visual o de concepto único) o si necesita más contenido."
            )
            return base

    # ── Caso 3: Slide saturada — sugerir división antes de resumir ───────────
    sugerencia_division = None
    if wps_m.get("zona") in ("saturada", "densa") and wps_m.get("exceso", 0) > 50:
        sugerencia_division = (
            f"Esta diapositiva tiene {wps_m.get('palabras',0)} palabras — "
            f"considera dividirla en {_cuantas_slides(wps_m.get('palabras',0))} diapositivas "
            f"temáticas de 40-75 palabras cada una en lugar de resumirla."
        )
        base["sugerencia_division"] = sugerencia_division

    base["necesitaba_rec"] = True

    # ── Generar prompt con contenido truncado si es muy largo ────────────────
    prompt = generar_prompt_recomendacion(slide_data, score_slide, MAX_CONTENIDO_CHARS)

    # Calcular num_predict según largo del contenido
    contenido_chars = sum(len(b) for b in slide_data.get("content", []))
    num_predict = min(2000, max(1000, contenido_chars * 2))

    resultado = _llamar_ollama(prompt, num_predict)

    if resultado:
        base.update({
            "titulo_nuevo":       resultado.get("titulo_nuevo"),
            "contenido_nuevo":    resultado.get("contenido_nuevo"),
            "cambios_realizados": resultado.get("cambios_realizados", []),
            "justificacion":      resultado.get("justificacion"),
        })
    else:
        base["error"] = "Respuesta no parseable como JSON"

    return base


def generar_resumen_presentacion(nombre, score_global, icd, wps, hss, nts):
    from app.core.logic.recommendation_prompt import generar_prompt_resumen
    prompt = generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts)
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 400}},
            timeout=TIMEOUT_SEG
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except Exception as e:
        return f"[Error generando resumen: {e}]"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llamar_ollama(prompt, num_predict):
    """Llama a Ollama con reintento si el JSON falla."""
    for intento in range(2):
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model":  MODELO,
                    "prompt": prompt if intento == 0 else prompt + "\nResponde SOLO con el JSON:",
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": num_predict,
                    }
                },
                timeout=TIMEOUT_SEG
            )
            response.raise_for_status()
            texto = response.json().get("response", "").strip()
            resultado = _parsear_json(texto)
            if resultado:
                return resultado
        except Exception:
            pass
    return None


def _parsear_json(texto):
    """Intenta parsear JSON con múltiples estrategias."""
    try:
        return json.loads(texto)
    except Exception:
        pass
    match = re.search(r'\{.*?\}', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    limpio = re.sub(r'```(?:json)?|```', '', texto).strip()
    try:
        return json.loads(limpio)
    except Exception:
        pass
    return None


def _cuantas_slides(palabras):
    """Estima en cuántas slides dividir el contenido."""
    return max(2, round(palabras / 57))   # 57 = centro del rango óptimo