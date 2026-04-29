# app/core/logic/metrics/header_structure.py
import re
from typing import Set

# --- CONFIGURATION & FILTERS ---
_STOPWORDS: Set[str] = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además", "este", "esta", "estos", 
    "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas",
    "yo","tú","él","ella","nosotros","ellos","me","te","se","nos","es","son"
}

_ACADEMIC_EXCLUSIONS: Set[str] = {
    "ejemplo", "caso", "importante", "definicion", "concepto", "introduccion", 
    "conclusion", "tema", "unidad", "capitulo", "objetivo", "descripcion", 
    "analisis", "nota", "resumen", "fundamentos", "presentacion"
}

_RE_PERSON_NAME = re.compile(
    r'[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}'
)

_RE_KEY_TOKENS = re.compile(r'[a-záéíóúüñ]{4,}', re.IGNORECASE)

# --- PURE MATHEMATICAL & TEXT HELPERS ---

def _get_keywords(text: str) -> Set[str]:
    """Extrae palabras significativas ignorando stopwords y términos académicos genéricos."""
    if not text:
        return set()
    tokens = _RE_KEY_TOKENS.findall(text.lower())
    return {
        t for t in tokens 
        if t not in _STOPWORDS and t not in _ACADEMIC_EXCLUSIONS
    }

def _filter_person_names(text: str) -> str:
    """Elimina secuencias que parecen nombres propios (comunes en footers)."""
    return _RE_PERSON_NAME.sub("", text).strip()

def _classify_hss_score(score: float) -> str:
    """Clasifica el score numérico en una etiqueta de estado."""
    if score >= 8.0: return "coherente"
    if score >= 5.0: return "debil"
    return "no_coherente"