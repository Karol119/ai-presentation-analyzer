# app/core/logic/metrics/narrative_thread.py
import re
import math
from collections import Counter
from typing import Dict, Any, Set

# --- UMBRALES ---
UMBRAL_RELACIONADO = 0.15
UMBRAL_DEBIL       = 0.05
UMBRAL_FUERTE      = 0.30

_STOPWORDS: Set[str] = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además","yo","tú","él","ella",
    "nosotros","ellos","me","te","se","nos","es","son","era","fue","ser","estar"
}

_RE_TOKENS_NTS = re.compile(r'[a-záéíóúüñ]{3,}', re.IGNORECASE)

# --- AYUDANTES MATEMÁTICOS & TEXTUALES ---

def _vectorizar(texto: str) -> Dict[str, float]:
    """Convierte un texto en un vector de frecuencias de términos (TF)."""
    tokens = _RE_TOKENS_NTS.findall(texto.lower())
    tokens_utiles = [t for t in tokens if t not in _STOPWORDS]
    if not tokens_utiles: return {}
    
    total = len(tokens_utiles)
    tf = Counter(tokens_utiles)
    return {t: conteo / total for t, conteo in tf.items()}

def _similitud_coseno(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    """Calcula la similitud del coseno entre dos vectores espaciales."""
    if not v1 or not v2: return 0.0
    comunes = set(v1.keys()) & set(v2.keys())
    if not comunes: return 0.0
    
    producto_punto = sum(v1[t] * v2[t] for t in comunes)
    mag1 = math.sqrt(sum(val**2 for val in v1.values()))
    mag2 = math.sqrt(sum(val**2 for val in v2.values()))
    return producto_punto / (mag1 * mag2)

def _texto_completo(datos_diapositiva: Dict[str, Any]) -> str:
    """Une el título y el contenido en un solo bloque de texto."""
    partes = [datos_diapositiva.get("title", "")] + datos_diapositiva.get("content", [])
    return " ".join([p.strip() for p in partes if p.strip()])

def _determinar_estado_por_puntaje(puntaje: float) -> str:
    """Clasifica el puntaje numérico en una etiqueta de estado."""
    if puntaje >= 7.0: return "relacionada"
    if puntaje >= 4.0: return "debil"
    return "desconectada"