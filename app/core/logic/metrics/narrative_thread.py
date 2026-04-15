import re
import math
from collections import Counter
from typing import Dict, Any, List, Callable, Optional, Set

from app.infrastructure.ollama.narrativa_service import verificar_hilo_narrativo

# Umbrales definidos por literatura de lingüística de corpus
RELATED_THRESHOLD = 0.15
WEAK_THRESHOLD    = 0.05
STRONG_THRESHOLD  = 0.30

# ── OPTIMIZACIÓN: Sets y Regex precompilados ─────────────────────────────────
_STOPWORDS: Set[str] = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además","yo","tú","él","ella",
    "nosotros","ellos","me","te","se","nos","es","son","era","fue","ser","estar"
}

# Regex precompilada: 3 o más letras, ignorando mayúsculas/minúsculas
_RE_TOKENS_NTS = re.compile(r'[a-záéíóúüñ]{3,}', re.IGNORECASE)

def calculate_nts(content_slides: List[Dict[str, Any]], llm_fn: Optional[Callable] = verificar_hilo_narrativo) -> Dict[str, Any]:
    
    if not content_slides:
        return _empty_summary()

    if len(content_slides) == 1:
        n = content_slides[0].get("slide_number")
        return {
            "resultados": [{
                "slide_number":  n,
                "sim_anterior":  None,
                "sim_siguiente": None,
                "sim_promedio":  1.0,   # puntuación perfecta
                "nts_score":     10.0,
                "estado":        "relacionada",
            }],
            "nts_promedio":        10.0,
            "slides_relacionadas": 1,
            "slides_debiles":      0,
            "slides_desconectadas":0,
        }
    
    vectors = [_vectorize(_full_text(s)) for s in content_slides]
    num_slides = len(vectors)
    results = []

    for i in range(num_slides):
        # Calculamos similitudes individuales
        prev_sim = _evaluate_connection(i-1, i, content_slides, vectors, llm_fn) if i > 0 else None
        next_sim = _evaluate_connection(i, i+1, content_slides, vectors, llm_fn) if i < num_slides-1 else None

        valid_sims = [s for s in [prev_sim, next_sim] if s is not None]
        avg_sim = sum(valid_sims) / len(valid_sims) if valid_sims else 0.0

        nts_score = _score_segments(avg_sim)
        
        results.append({
            "slide_number":  content_slides[i].get("slide_number"),
            "sim_anterior":  round(prev_sim, 4) if prev_sim is not None else None,
            "sim_siguiente": round(next_sim, 4) if next_sim is not None else None,
            "sim_promedio":  round(avg_sim, 4),
            "nts_score":     nts_score,
            "estado":        _determine_status(avg_sim)
        })

    scores = [r["nts_score"] for r in results]

    return {
        "resultados": results,
        "nts_promedio": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "slides_relacionadas": sum(1 for r in results if r["estado"] == "relacionada"),
        "slides_debiles": sum(1 for r in results if r["estado"] == "debil"),
        "slides_desconectadas": sum(1 for r in results if r["estado"] == "desconectada"),
    }

# ── Helpers de Cálculo ───────────────────────────────────────────────────────

def _evaluate_connection(idx1: int, idx2: int, slides: List[Dict[str, Any]], vectors: List[Dict[str, float]], llm_fn: Optional[Callable]) -> float:
    """
    Lógica híbrida: Coseno (rápido) -> Mistral (semántico).
    """
    cosine_sim = _cosine_similarity(vectors[idx1], vectors[idx2])
    
    # Si la relación léxica es baja, pedimos juicio semántico al modelo
    if cosine_sim < RELATED_THRESHOLD and llm_fn:
        text1 = _full_text(slides[idx1])
        text2 = _full_text(slides[idx2])
        llm_score = llm_fn(text1, text2)
        
        if llm_score:
            # Mapeamos la nota 1-10 del LLM al espacio de similitud (0.0 a 0.4)
            sim_llm = (llm_score / 10.0) * 0.4
            return max(cosine_sim, sim_llm)
            
    return cosine_sim

def _score_segments(sim: float) -> float:
    """Cálculo de score basado en los tramos definidos en el archivo de tesis."""
    if sim >= STRONG_THRESHOLD: return 10.0
    if sim >= RELATED_THRESHOLD:
        t = (sim - RELATED_THRESHOLD) / (STRONG_THRESHOLD - RELATED_THRESHOLD)
        return round(7.0 + t * 3.0, 2)
    if sim >= WEAK_THRESHOLD:
        t = (sim - WEAK_THRESHOLD) / (RELATED_THRESHOLD - WEAK_THRESHOLD)
        return round(3.0 + t * 4.0, 2)
    return round((sim / WEAK_THRESHOLD) * 3.0, 2)

def _vectorize(text: str) -> Dict[str, float]:
    # OPTIMIZACIÓN: Uso de regex precompilada
    tokens = _RE_TOKENS_NTS.findall(text.lower())
    useful_tokens = [t for t in tokens if t not in _STOPWORDS]
    
    if not useful_tokens: 
        return {}
        
    total = len(useful_tokens)
    # OPTIMIZACIÓN: Counter es nativo de Python en C, muchísimo más rápido que iterar diccionarios
    tf = Counter(useful_tokens)
    
    return {t: c / total for t, c in tf.items()}

def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    if not v1 or not v2: return 0.0
    common = set(v1.keys()) & set(v2.keys())
    if not common: return 0.0
    
    dot = sum(v1[t] * v2[t] for t in common)
    mag1 = math.sqrt(sum(x**2 for x in v1.values()))
    mag2 = math.sqrt(sum(x**2 for x in v2.values()))
    
    return dot / (mag1 * mag2)

def _full_text(slide_data: Dict[str, Any]) -> str:
    parts = [slide_data.get("title", "")] + slide_data.get("content", [])
    return " ".join([p.strip() for p in parts if p.strip()])

def _determine_status(sim: float) -> str:
    if sim >= RELATED_THRESHOLD: return "relacionada"
    if sim >= WEAK_THRESHOLD: return "debil"
    return "desconectada"

def _empty_summary() -> Dict[str, Any]:
    return {
        "resultados": [], "nts_promedio": 0.0,
        "slides_relacionadas": 0, "slides_debiles": 0,
        "slides_desconectadas": 0
    }
    
def calculate_individual_nts(current_slide: Dict[str, Any], previous_slide: Optional[Dict[str, Any]] = None, llm_fn: Optional[Callable] = verificar_hilo_narrativo) -> Dict[str, Any]:
    """
    Calcula el NTS comparando la slide actual con la anterior.
    """
    if previous_slide is None:
        return {
            "slide_number": current_slide.get("slide_number"),
            "sim_anterior": None,
            "sim_promedio": 1.0,
            "nts_score": 10.0,
            "estado": "relacionada",
        }

    v_current = _vectorize(_full_text(current_slide))
    v_previous = _vectorize(_full_text(previous_slide))
    
    sim = _evaluate_direct_connection(v_previous, v_current, previous_slide, current_slide, llm_fn)
    
    return {
        "slide_number": current_slide.get("slide_number"),
        "sim_anterior": round(sim, 4),
        "sim_promedio": round(sim, 4),
        "nts_score": _score_segments(sim),
        "estado": _determine_status(sim)
    }

def _evaluate_direct_connection(v1: Dict[str, float], v2: Dict[str, float], s1: Dict[str, Any], s2: Dict[str, Any], llm_fn: Optional[Callable]) -> float:
    cosine_sim = _cosine_similarity(v1, v2)
    if cosine_sim < RELATED_THRESHOLD and llm_fn:
        llm_score = llm_fn(_full_text(s1), _full_text(s2))
        if llm_score:
            return max(cosine_sim, (llm_score / 10.0) * 0.4)
    return cosine_sim