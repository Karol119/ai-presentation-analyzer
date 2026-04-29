# app/core/logic/metrics/icd.py
import re
from typing import Dict, Any, List, Optional
from app.core.logic.metrics.readability import calcular_legibilidad
from app.core.logic.metrics.lexical_density import calcular_densidad_lexica, _STOPWORDS
from app.core.logic.metrics.text_counter import preparar_texto_slide

PESO_CF = 0.6
PESO_DLN = 0.4
MIN_PALABRAS_ICD = 15

_ESCALA = [
    (2.0,  "muy simple"),
    (4.0,  "simple"),
    (6.0,  "apropiado"),
    (8.0,  "complejo"),
    (10.0, "muy complejo"),
]

def calcular_icd(datos_diapositiva: Dict[str, Any]) -> Dict[str, Any]:
    metricas_legibilidad = calcular_legibilidad(datos_diapositiva)
    metricas_densidad = calcular_densidad_lexica(datos_diapositiva)
    texto = preparar_texto_slide(datos_diapositiva)

    resultado_base = {
        "slide_number": datos_diapositiva.get("slide_number"),
        "calculable":   False,
        "icd":          None,
        "zona":         None,
        "feedback_local": None
    }

    if metricas_legibilidad is None or metricas_densidad is None or metricas_legibilidad["palabras"] < MIN_PALABRAS_ICD:
        return resultado_base

    cf  = metricas_legibilidad["cf"]
    ldn = metricas_densidad["dln"]
    puntaje_icd = (PESO_CF * cf + PESO_DLN * ldn) * 10
    puntaje_icd = round(max(0.0, min(10.0, puntaje_icd)), 2)
    
    retroalimentacion_local = _generar_retroalimentacion_icd(puntaje_icd, texto)

    resultado_base.update({
        "calculable":         True,
        "icd":                puntaje_icd,
        "zona":               _obtener_zona_icd(puntaje_icd),
        "cf":                 cf,
        "dln":                ldn,
        "fsz":                metricas_legibilidad["fsz"],
        "fsz_zona":           metricas_legibilidad["fsz_zona"],
        "dl":                 metricas_densidad["dl"],
        "palabras":           metricas_legibilidad["palabras"],
        "silabas":            metricas_legibilidad["silabas"],
        "frases":             metricas_legibilidad["frases"],
        "prom_sil_pal":       metricas_legibilidad["prom_sil_pal"],
        "prom_pal_fra":       metricas_legibilidad["prom_pal_fra"],
        "palabras_contenido": metricas_densidad["palabras_contenido"],
        "feedback_local":     retroalimentacion_local
    })

    return resultado_base

def calcular_icd_presentacion(diapositivas_contenido: List[Dict[str, Any]]) -> Dict[str, Any]:
    resultados = [calcular_icd(s) for s in diapositivas_contenido]

    valores_icd = [r["icd"] for r in resultados if r["calculable"]]
    diapositivas_sin_texto = sum(1 for r in resultados if not r["calculable"])

    if not valores_icd:
        return {
            "resultados":        resultados,
            "icd_promedio":      None,
            "icd_minimo":        None,
            "icd_maximo":        None,
            "zona_promedio":     None,
            "slides_calculadas": 0,
            "slides_sin_texto":  diapositivas_sin_texto,
        }

    promedio_icd = round(sum(valores_icd) / len(valores_icd), 2)

    return {
        "resultados":        resultados,
        "icd_promedio":      promedio_icd,
        "icd_minimo":        round(min(valores_icd), 2),
        "icd_maximo":        round(max(valores_icd), 2),
        "zona_promedio":     _obtener_zona_icd(promedio_icd),
        "slides_calculadas": len(valores_icd),
        "slides_sin_texto":  diapositivas_sin_texto,
    }

def _extraer_palabras_complejas(texto: str, max_palabras: int = 3) -> List[str]:
    tokens = re.findall(r'[a-záéíóúüñ]{6,}', texto.lower(), re.IGNORECASE)
    tokens_validos = list(set([t for t in tokens if t not in _STOPWORDS]))
    tokens_validos.sort(key=len, reverse=True)
    return tokens_validos[:max_palabras]

def _generar_retroalimentacion_icd(puntaje_icd: float, texto: str) -> Optional[str]:
    if puntaje_icd is None or 4.0 <= puntaje_icd <= 6.0:
        return None
    
    if puntaje_icd > 6.0:
        palabras_complejas = _extraer_palabras_complejas(texto)
        cadena_palabras = ", ".join(palabras_complejas)
        texto_ejemplo = f" (por ejemplo: '{cadena_palabras}')" if palabras_complejas else ""
        
        return (
            f"El nivel de complejidad es alto (ICD: {puntaje_icd}). Esto se debe principalmente a "
            f"la falta de conectores o al uso de términos muy extensos{texto_ejemplo}. "
            f"Se sugiere simplificar la redacción utilizando sinónimos más accesibles o "
            f"dividiendo las oraciones, cuidando de no perder el concepto académico original."
        )
    else:
        return (
            f"El lenguaje utilizado es demasiado básico para el nivel superior (ICD: {puntaje_icd}). "
            f"Se sugiere incorporar terminología académica o técnica apropiada para enriquecer el aprendizaje."
        )

def _obtener_zona_icd(valor: float) -> str:
    for limite, etiqueta in _ESCALA:
        if valor <= limite:
            return etiqueta
    return "muy complejo"