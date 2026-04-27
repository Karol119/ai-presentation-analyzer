import re
from typing import Dict, Any, List, Optional
from app.core.logic.metrics.readability import calculate_readability
from app.core.logic.metrics.lexical_density import calculate_lexical_density, _STOPWORDS
from app.core.logic.metrics.text_counter import preparar_texto_slide

WEIGHT_CF = 0.6
WEIGHT_DLN = 0.4
MIN_WORDS_ICD = 15

_SCALE = [
    (2.0,  "muy simple"),
    (4.0,  "simple"),
    (6.0,  "apropiado"),
    (8.0,  "complejo"),
    (10.0, "muy complejo"),
]

def calculate_icd(slide_data: Dict[str, Any]) -> Dict[str, Any]:
    readability_metrics = calculate_readability(slide_data)
    density_metrics = calculate_lexical_density(slide_data)
    text = preparar_texto_slide(slide_data)

    base_result = {
        "slide_number": slide_data.get("slide_number"),
        "calculable":   False,
        "icd":          None,
        "zona":         None,
        "feedback_local": None
    }

    if readability_metrics is None or density_metrics is None or readability_metrics["palabras"] < MIN_WORDS_ICD:
        return base_result

    cf  = readability_metrics["cf"]
    ldn = density_metrics["dln"]
    icd_score = (WEIGHT_CF * cf + WEIGHT_DLN * ldn) * 10
    icd_score = round(max(0.0, min(10.0, icd_score)), 2)
    
    # Generamos la retroalimentación instantánea
    local_feedback = _generate_icd_feedback(icd_score, text)

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
        "feedback_local":     local_feedback
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

# --- Funciones Auxiliares ---

def _extract_complex_words(text: str, max_words: int = 3) -> List[str]:
    """Identifica las palabras más largas (polisílabas) para dar ejemplos concretos."""
    tokens = re.findall(r'[a-záéíóúüñ]{6,}', text.lower(), re.IGNORECASE)
    # Filtramos las stopwords y quitamos duplicados
    valid_tokens = list(set([t for t in tokens if t not in _STOPWORDS]))
    # Ordenamos por longitud de palabra (las más largas primero)
    valid_tokens.sort(key=len, reverse=True)
    return valid_tokens[:max_words]

def _generate_icd_feedback(icd_score: float, text: str) -> Optional[str]:
    """Genera la retroalimentación basada en la penalización de sílabas."""
    if icd_score is None or 4.0 <= icd_score <= 6.0:
        return None
    
    if icd_score > 6.0:
        complex_words = _extract_complex_words(text)
        words_str = ", ".join(complex_words)
        example_text = f" (por ejemplo: '{words_str}')" if complex_words else ""
        
        return (
            f"El nivel de complejidad es alto (ICD: {icd_score}). Esto se debe principalmente a "
            f"la falta de conectores o al uso de términos muy extensos{example_text}. "
            f"Se sugiere simplificar la redacción utilizando sinónimos más accesibles o "
            f"dividiendo las oraciones, cuidando de no perder el concepto académico original."
        )
    else:
        return (
            f"El lenguaje utilizado es demasiado básico para el nivel superior (ICD: {icd_score}). "
            f"Se sugiere incorporar terminología académica o técnica apropiada para enriquecer el aprendizaje."
        )

def _get_icd_zone(value: float) -> str:
    for limit, label in _SCALE:
        if value <= limit:
            return label
    return "muy complejo"