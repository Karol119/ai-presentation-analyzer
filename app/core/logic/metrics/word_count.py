from typing import Dict, Any, List, Optional
from app.core.logic.metrics.text_counter import contar_palabras, preparar_texto_slide

OPTIMAL_MAX_WORDS = 75
EXCESS_PENALTY    = 15

def calculate_wps(slide_data: Dict[str, Any]) -> Dict[str, Any]:
    text = preparar_texto_slide(slide_data)
    word_count = contar_palabras(text)

    score = _calculate_excess_score(word_count)
    zone  = _get_excess_zone(word_count)
    
    # Generamos la retroalimentación instantánea
    local_feedback = _generate_wps_feedback(word_count)

    return {
        "slide_number": slide_data.get("slide_number"),
        "palabras":     word_count,
        "wps_score":    round(score, 2),
        "zona":         zone,
        "en_rango":     word_count <= OPTIMAL_MAX_WORDS,
        "exceso":       max(0, word_count - OPTIMAL_MAX_WORDS),
        "deficit":      0,
        "feedback_local": local_feedback
    }

def calculate_presentation_wps(content_slides: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not content_slides:
        return {
            "resultados": [],
            "wps_promedio": 0.0,
            "palabras_promedio": 0.0,
            "slides_optimas": 0,
            "slides_densas": 0,
            "slides_saturadas": 0
        }

    results = [calculate_wps(s) for s in content_slides]
    scores = [r["wps_score"] for r in results]
    word_counts = [r["palabras"] for r in results]

    return {
        "resultados":        results,
        "wps_promedio":      round(sum(scores) / len(scores), 2) if scores else 0.0,
        "palabras_promedio": round(sum(word_counts) / len(word_counts), 1) if word_counts else 0.0,
        "slides_optimas":    sum(1 for r in results if r["zona"] == "optima"),
        "slides_densas":     sum(1 for r in results if r["zona"] == "densa"),
        "slides_saturadas":  sum(1 for r in results if r["zona"] == "saturada"),
    }

# --- Funciones Auxiliares ---

def _generate_wps_feedback(word_count: int) -> Optional[str]:
    """Genera la retroalimentación local para la cantidad de palabras."""
    if word_count <= OPTIMAL_MAX_WORDS:
        return None
        
    excess = word_count - OPTIMAL_MAX_WORDS
    return (
        f"Se ha detectado un exceso de contenido ({excess} palabras de más). "
        f"Se sugiere reestructurar el texto o dividir las ideas principales en múltiples "
        f"diapositivas para mantener un máximo de {OPTIMAL_MAX_WORDS} palabras, "
        f"optimizando así la retención del estudiante."
    )

def _calculate_excess_score(words: int) -> float:
    if words <= OPTIMAL_MAX_WORDS:
        return 10.0
    penalty = (words - OPTIMAL_MAX_WORDS) / EXCESS_PENALTY
    return max(0.0, 10.0 - penalty)

def _get_excess_zone(words: int) -> str:
    if words <= OPTIMAL_MAX_WORDS:
        return "optima"
    if words <= 120:
        return "densa"
    return "saturada"