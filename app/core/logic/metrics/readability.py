# app/core/logic/metrics/readability.py

"""
calculo_legibilidad.py
Calcula el índice Flesch-Szigriszt (FSZ) adaptado al español
y su transformación a CF (complejidad Flesch normalizada).

Fórmulas:
    FSZ = 206.835 - 62.3 × (sílabas / palabras) - (palabras / frases)
    CF  = (100 - FSZ) / 100   → rango [0, 1], mayor = más complejo
"""

from app.core.logic.metrics.text_counter import (
    contar_palabras,
    contar_silabas,
    segmentar_frases,
    preparar_texto_slide
)


def calcular_legibilidad(slide_data):
    """
    Calcula FSZ y CF para una diapositiva.

    Args:
        slide_data: dict del extractor (con title, content, footer ya excluido)

    Returns:
        {
            "palabras":  int,
            "silabas":   int,
            "frases":    int,
            "prom_sil_pal": float,   # sílabas / palabras
            "prom_pal_fra": float,   # palabras / frases
            "fsz":       float,      # Flesch-Szigriszt (0–100)
            "cf":        float,      # Complejidad Flesch normalizada (0–1)
            "fsz_zona":  str         # etiqueta de dificultad
        }
        None si no hay suficiente texto para calcular.
    """
    texto = preparar_texto_slide(slide_data)

    palabras = contar_palabras(texto)
    if palabras < 5:
        return None

    silabas = contar_silabas(texto)
    frases  = segmentar_frases(texto)
    n_frases = len(frases) if frases else 1

    prom_sil_pal = silabas / palabras
    prom_pal_fra = palabras / n_frases

    fsz = 206.835 - (62.3 * prom_sil_pal) - prom_pal_fra
    # Clamp a rango realista (el índice puede salir de 0-100 en textos extremos)
    fsz = max(0.0, min(100.0, fsz))

    cf = (100.0 - fsz) / 100.0
    cf = round(max(0.0, min(1.0, cf)), 4)

    return {
        "palabras":     palabras,
        "silabas":      silabas,
        "frases":       n_frases,
        "prom_sil_pal": round(prom_sil_pal, 3),
        "prom_pal_fra": round(prom_pal_fra, 3),
        "fsz":          round(fsz, 2),
        "cf":           cf,
        "fsz_zona":     _zona_fsz(fsz)
    }


def _zona_fsz(fsz):
    if fsz >= 80: return "muy facil"
    if fsz >= 65: return "facil"
    if fsz >= 50: return "normal"
    if fsz >= 35: return "dificil"
    if fsz >= 15: return "muy dificil"
    return "arido"