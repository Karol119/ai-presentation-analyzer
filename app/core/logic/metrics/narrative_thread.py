# app/core/logic/metrics/narrative_thread.py
import re
import math
from collections import Counter
from typing import Dict, Any, Set

# --- THRESHOLDS ---
RELATED_THRESHOLD = 0.15
WEAK_THRESHOLD    = 0.05
STRONG_THRESHOLD  = 0.30

_STOPWORDS: Set[str] = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además","yo","tú","él","ella",
    "nosotros","ellos","me","te","se","nos","es","son","era","fue","ser","estar"
}

_RE_TOKENS_NTS = re.compile(r'[a-záéíóúüñ]{3,}', re.IGNORECASE)

# --- PURE MATHEMATICAL & TEXT HELPERS ---

def _vectorize(text: str) -> Dict[str, float]:
    """Convierte un texto en un vector de frecuencias de términos (TF)."""
    tokens = _RE_TOKENS_NTS.findall(text.lower())
    useful_tokens = [t for t in tokens if t not in _STOPWORDS]
    if not useful_tokens: return {}
    
    total = len(useful_tokens)
    tf = Counter(useful_tokens)
    return {t: count / total for t, count in tf.items()}

def _cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Calcula la similitud del coseno entre dos vectores espaciales."""
    if not v1 or not v2: return 0.0
    common = set(v1.keys()) & set(v2.keys())
    if not common: return 0.0
    
    dot_product = sum(v1[t] * v2[t] for t in common)
    mag1 = math.sqrt(sum(val**2 for val in v1.values()))
    mag2 = math.sqrt(sum(val**2 for val in v2.values()))
    return dot_product / (mag1 * mag2)

def _full_text(slide_data: Dict[str, Any]) -> str:
    """Une el título y el contenido en un solo bloque de texto."""
    parts = [slide_data.get("title", "")] + slide_data.get("content", [])
    return " ".join([p.strip() for p in parts if p.strip()])

def _determine_status_from_score(score: float) -> str:
    """Clasifica el score numérico en una etiqueta de estado."""
    if score >= 7.0: return "relacionada"
    if score >= 4.0: return "debil"
    return "desconectada"