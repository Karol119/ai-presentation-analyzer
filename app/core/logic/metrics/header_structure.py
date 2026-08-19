# app/core/logic/metrics/header_structure.py
import re
from typing import Set

# --- CONFIGURACIÓN & FILTROS ---
_STOPWORDS: Set[str] = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además", "este", "esta", "estos", 
    "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas",
    "yo","tú","él","ella","nosotros","ellos","me","te","se","nos","es","son"
}

_EXCLUSIONES_ACADEMICAS: Set[str] = {
    "ejemplo", "caso", "importante", "definicion", "concepto", "introduccion", 
    "conclusion", "tema", "unidad", "capitulo", "objetivo", "descripcion", 
    "analisis", "nota", "resumen", "fundamentos", "presentacion"
}

_RE_NOMBRE_PERSONA = re.compile(
    r'[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}'
)

_RE_TOKENS_CLAVE = re.compile(r'[a-záéíóúüñ]{4,}', re.IGNORECASE)

# --- AYUDANTES MATEMÁTICOS & TEXTUALES ---

def _obtener_palabras_clave(texto: str) -> Set[str]:
    """Extrae palabras significativas ignorando stopwords y términos académicos genéricos."""
    if not texto:
        return set()
    tokens = _RE_TOKENS_CLAVE.findall(texto.lower())
    return {
        t for t in tokens 
        if t not in _STOPWORDS and t not in _EXCLUSIONES_ACADEMICAS
    }

def _filtrar_nombres_personas(texto: str) -> str:
    """Elimina secuencias que parecen nombres propios (comunes en footers)."""
    return _RE_NOMBRE_PERSONA.sub("", texto).strip()

def _clasificar_puntaje_hss(puntaje: float) -> str:
    """Clasifica el puntaje numérico en una etiqueta de estado."""
    if puntaje >= 8.0: return "coherente"
    if puntaje >= 5.0: return "debil"
    return "no_coherente"