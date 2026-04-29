# app/core/logic/metrics/readability.py
from typing import Dict, Any, Optional
from app.core.logic.metrics.text_counter import (
    contar_palabras, contar_silabas, segmentar_frases, preparar_texto_slide
)

def calcular_legibilidad(datos_diapositiva: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    texto = preparar_texto_slide(datos_diapositiva)

    conteo_palabras = contar_palabras(texto)
    if conteo_palabras < 5:
        return None

    conteo_silabas = contar_silabas(texto)
    frases = segmentar_frases(texto)
    num_frases = len(frases) if frases else 1

    promedio_silabas_por_palabra = conteo_silabas / conteo_palabras
    promedio_palabras_por_frase = conteo_palabras / num_frases

    # Fórmula de Flesch-Szigriszt (FSZ) adaptada al español
    fsz = 206.835 - (62.3 * promedio_silabas_por_palabra) - promedio_palabras_por_frase
    fsz = max(0.0, min(100.0, fsz))

    # Factor de Complejidad (CF) normalizado de 0 a 1
    cf = (100.0 - fsz) / 100.0
    cf = round(max(0.0, min(1.0, cf)), 4)

    return {
        "palabras":     conteo_palabras,
        "silabas":      conteo_silabas,
        "frases":       num_frases,
        "prom_sil_pal": round(promedio_silabas_por_palabra, 3),
        "prom_pal_fra": round(promedio_palabras_por_frase, 3),
        "fsz":          round(fsz, 2),
        "cf":           cf,
        "fsz_zona":     _obtener_zona_fsz(fsz)
    }

def _obtener_zona_fsz(fsz: float) -> str:
    if fsz >= 80: return "muy facil"
    if fsz >= 65: return "facil"
    if fsz >= 50: return "normal"
    if fsz >= 35: return "dificil"
    if fsz >= 15: return "muy dificil"
    return "arido"