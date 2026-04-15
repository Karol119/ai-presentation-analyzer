from typing import Dict, Any, List
from app.core.logic.metrics.readability import calculate_readability
from app.core.logic.metrics.lexical_density import calculate_lexical_density

WEIGHT_CF = 0.6
WEIGHT_DLN = 0.4
MIN_WORDS_ICD = 15

_SCALE = [
    (2.0,  "muy simple"),
    (4.0,  "simple"),
    (6.5,  "apropiado"),
    (8.0,  "complejo"),
    (10.0, "muy complejo"),
]

def calculate_icd(slide_data: Dict[str, Any]) -> Dict[str, Any]:
    readability_metrics = calculate_readability(slide_data)
    density_metrics = calculate_lexical_density(slide_data)

    base_result = {
        "slide_number": slide_data.get("slide_number"),
        "calculable":   False,
        "icd":          None,
        "zona":         None,
    }

    if readability_metrics is None or density_metrics is None or readability_metrics["palabras"] < MIN_WORDS_ICD:
        return base_result

    cf  = readability_metrics["cf"]
    ldn = density_metrics["dln"]
    icd_score = (WEIGHT_CF * cf + WEIGHT_DLN * ldn) * 10
    icd_score = round(max(0.0, min(10.0, icd_score)), 2)

    base_result.update({
        "calculable":         True,
        "icd":                icd_score,
        "zona":               _get_icd_zone(icd_score),
        "cf":                 cf,
        "dln":                ldn,
        "fsz":                readability_metrics["fsz"],
        "fsz_zona":           readability_metrics["fsz_zona"],
        "dl":                 density_metrics["dl"],
        "palabras":           readability_metrics["palabras"],
        "silabas":            readability_metrics["silabas"],
        "frases":             readability_metrics["frases"],
        "prom_sil_pal":       readability_metrics["prom_sil_pal"],
        "prom_pal_fra":       readability_metrics["prom_pal_fra"],
        "palabras_contenido": density_metrics["palabras_contenido"],
    })

    return base_result

def calculate_presentation_icd(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = [calculate_icd(s) for s in content_slides]

    icd_values = [r["icd"] for r in results if r["calculable"]]
    textless_slides = sum(1 for r in results if not r["calculable"])

    if not icd_values:
        return {
            "resultados":        results,
            "icd_promedio":      None,
            "icd_minimo":        None,
            "icd_maximo":        None,
            "zona_promedio":     None,
            "slides_calculadas": 0,
            "slides_sin_texto":  textless_slides,
        }

    average_icd = round(sum(icd_values) / len(icd_values), 2)

    return {
        "resultados":        results,
        "icd_promedio":      average_icd,
        "icd_minimo":        round(min(icd_values), 2),
        "icd_maximo":        round(max(icd_values), 2),
        "zona_promedio":     _get_icd_zone(average_icd),
        "slides_calculadas": len(icd_values),
        "slides_sin_texto":  textless_slides,
    }

def _get_icd_zone(value: float) -> str:
    for limit, label in _SCALE:
        if value <= limit:
            return label
    return "muy complejo"