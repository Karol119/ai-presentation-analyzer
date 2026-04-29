# app/core/logic/metrics/word_count.py
from typing import Dict, Any, List, Optional
from app.core.logic.metrics.text_counter import contar_palabras

MAX_PALABRAS_OPTIMO = 45
PENALIZACION_EXCESO    = 15

def calcular_wps(datos_diapositiva: Dict[str, Any]) -> Dict[str, Any]:
    texto = " ".join(datos_diapositiva.get("content", [])) if "content" in datos_diapositiva else ""
    conteo_palabras = contar_palabras(texto)

    puntaje = _calcular_puntaje_exceso(conteo_palabras)
    zona  = _obtener_zona_exceso(conteo_palabras)
    
    retroalimentacion_local = _generar_retroalimentacion_wps(conteo_palabras)

    return {
        "slide_number": datos_diapositiva.get("slide_number"),
        "palabras":     conteo_palabras,
        "wps_score":    round(puntaje, 2),
        "zona":         zona,
        "en_rango":     conteo_palabras <= MAX_PALABRAS_OPTIMO,
        "exceso":       max(0, conteo_palabras - MAX_PALABRAS_OPTIMO),
        "deficit":      0,
        "feedback_local": retroalimentacion_local
    }

def calcular_wps_presentacion(diapositivas_contenido: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not diapositivas_contenido:
        return {
            "resultados": [],
            "wps_promedio": 0.0,
            "palabras_promedio": 0.0,
            "slides_optimas": 0,
            "slides_densas": 0,
            "slides_saturadas": 0
        }

    resultados = [calcular_wps(s) for s in diapositivas_contenido]
    puntajes = [r["wps_score"] for r in resultados]
    conteos_palabras = [r["palabras"] for r in resultados]

    return {
        "resultados":        resultados,
        "wps_promedio":      round(sum(puntajes) / len(puntajes), 2) if puntajes else 0.0,
        "palabras_promedio": round(sum(conteos_palabras) / len(conteos_palabras), 1) if conteos_palabras else 0.0,
        "slides_optimas":    sum(1 for r in resultados if r["zona"] == "optima"),
        "slides_densas":     sum(1 for r in resultados if r["zona"] == "densa"),
        "slides_saturadas":  sum(1 for r in resultados if r["zona"] == "saturada"),
    }

def _generar_retroalimentacion_wps(conteo_palabras: int) -> Optional[str]:
    if conteo_palabras <= MAX_PALABRAS_OPTIMO:
        return None
        
    exceso = conteo_palabras - MAX_PALABRAS_OPTIMO
    return (
        f"Se ha detectado un exceso de contenido ({exceso} palabras de más). "
        f"Se sugiere reestructurar el texto o dividir las ideas principales en múltiples "
        f"diapositivas para mantener un máximo de {MAX_PALABRAS_OPTIMO} palabras (sin contar el título), "
        f"optimizando así la retención del estudiante."
    )

def _calcular_puntaje_exceso(palabras: int) -> float:
    if palabras <= MAX_PALABRAS_OPTIMO:
        return 10.0
    penalizacion = (palabras - MAX_PALABRAS_OPTIMO) / PENALIZACION_EXCESO
    return max(0.0, 10.0 - penalizacion)

def _obtener_zona_exceso(palabras: int) -> str:
    if palabras <= MAX_PALABRAS_OPTIMO:
        return "optima"
    if palabras <= 70: 
        return "densa"
    return "saturada"