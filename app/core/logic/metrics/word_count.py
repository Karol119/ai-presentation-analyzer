# app/core/logic/metrics/word_count.py

import re

MAX_OPTIMO          = 75
PENALIZACION_EXCESO = 15  # Cada 15 palabras de exceso restan aproximadamente 1 punto

def calcular_wps(slide_data):
    """
    Calcula el WPS (Words Per Slide) para una sola diapositiva.
    Siguiendo la definición de tesis: No se penaliza el contenido breve[cite: 12],
    solo se evalúa el riesgo de saturación por encima de 75 palabras[cite: 8].
    """
    texto    = _preparar_texto(slide_data)
    palabras = _contar_palabras(texto)

    # El score es 10 perfecto si no excede el máximo
    score = _calcular_score_exclusivo_exceso(palabras)
    zona  = _zona_solo_exceso(palabras)

    return {
        "slide_number": slide_data.get("slide_number"),
        "palabras":     palabras,
        "wps_score":    round(score, 2),
        "zona":         zona,
        "en_rango":     palabras <= MAX_OPTIMO,
        "exceso":       max(0, palabras - MAX_OPTIMO),
        "deficit":      0  
    }

def calcular_wps_presentacion(slides_contenido):
    """
    Función INTEGRADORA: Calcula el WPS para todas las diapositivas de contenido 
    y genera las estadísticas globales de la presentación.
    """
    if not slides_contenido:
        return {
            "resultados": [],
            "wps_promedio": 0.0,
            "palabras_promedio": 0.0,
            "slides_optimas": 0,
            "slides_densas": 0,
            "slides_saturadas": 0
        }

    resultados = [calcular_wps(s) for s in slides_contenido]
    scores = [r["wps_score"] for r in resultados]
    palabras = [r["palabras"] for r in resultados]

    return {
        "resultados":        resultados,
        "wps_promedio":      round(sum(scores) / len(scores), 2) if scores else 0.0,
        "palabras_promedio": round(sum(palabras) / len(palabras), 1) if palabras else 0.0,
        "slides_optimas":    sum(1 for r in resultados if r["zona"] == "optima"),
        "slides_densas":     sum(1 for r in resultados if r["zona"] == "densa"),
        "slides_saturadas":  sum(1 for r in resultados if r["zona"] == "saturada"),
    }

# --- Funciones Auxiliares ---

def _calcular_score_exclusivo_exceso(palabras):
    if palabras <= MAX_OPTIMO:
        return 10.0
    penalizacion = (palabras - MAX_OPTIMO) / PENALIZACION_EXCESO
    return max(0.0, 10.0 - penalizacion)

def _zona_solo_exceso(palabras):
    if palabras <= MAX_OPTIMO:
        return "optima"
    if palabras <= 120:
        return "densa"
    return "saturada"

def _preparar_texto(slide_data):
    partes = []
    titulo = slide_data.get("title", "").strip()
    if titulo:
        partes.append(titulo)
    for bloque in slide_data.get("content", []):
        bloque = bloque.strip()
        if bloque:
            partes.append(bloque)
    return " ".join(partes)

def _contar_palabras(texto):
    tokens = texto.split()
    from app.core.logic.metrics.text_counter import _RE_TOKEN_NO_PALABRA
    return sum(1 for t in tokens if not _RE_TOKEN_NO_PALABRA.match(t))