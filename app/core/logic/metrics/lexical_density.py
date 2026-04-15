# app/core/logic/metrics/lexical_density.py
"""
densidad_lexica.py
Calcula la densidad léxica (DL) y su forma normalizada (DLN).

Fórmula:
    DL  = (palabras_contenido / total_palabras) × 100
    DLN = DL / 100   → rango [0, 1]

Palabras de contenido: sustantivos, verbos, adjetivos y adverbios.
Aproximación: total_palabras - stopwords (palabras funcionales).
"""

import re
from typing import Dict, Any, Optional
from app.core.logic.metrics.text_counter import preparar_texto_slide

# ──────────────────────────────────────────────────────────────────────────────
# Stopwords del español (palabras funcionales que NO son contenido)
# Artículos, preposiciones, conjunciones, pronombres, auxiliares comunes
# ──────────────────────────────────────────────────────────────────────────────
_RE_TOKENS = re.compile(r'[a-záéíóúüñ]+', re.IGNORECASE)
_STOPWORDS = {
    # Artículos
    "el","la","los","las","un","una","unos","unas",
    # Preposiciones
    "a","ante","bajo","con","contra","de","desde","durante","en","entre",
    "hacia","hasta","mediante","para","por","según","sin","sobre","tras",
    "versus","vía",
    # Conjunciones
    "y","e","ni","o","u","pero","sino","aunque","porque","pues","que",
    "si","como","cuando","donde","mientras","ya","además","también",
    "sin embargo","es decir","por lo tanto","por eso","así",
    # Pronombres personales
    "yo","tú","él","ella","nosotros","vosotros","ellos","ellas",
    "me","te","se","nos","os","le","les","lo","la","los","las",
    "mi","tu","su","nuestro","vuestra","nuestros","sus",
    # Pronombres relativos/interrogativos
    "que","quien","quienes","cual","cuales","cuyo","cuya",
    "qué","quién","cómo","cuándo","dónde","cuánto",
    # Verbos auxiliares y copulativos comunes
    "es","son","era","eran","fue","fueron","ser","estar","estoy","estás",
    "está","estamos","están","estaba","estaban","hay","haber","ha","han",
    "había","hubiera","tiene","tienen","tenía","tener","puede","pueden",
    "podía","poder","debe","deben","debía","deber","hace","hacen","hacer",
    # Determinantes y cuantificadores
    "este","esta","estos","estas","ese","esa","esos","esas",
    "aquel","aquella","aquellos","aquellas","mucho","muchos","poco","pocos",
    "todo","todos","toda","todas","otro","otros","otra","otras",
    "más","menos","muy","bien","mal","tan","tanto","cuanto",
    # Adverbios de negación y afirmación
    "no","sí","tampoco","nunca","jamás","siempre","ya","aún","todavía",
    # Preposiciones contractas y artículos combinados
    "al","del",
    # Conectores discursivos comunes (no aportan contenido temático)
    "también","además","sin","embargo","aunque","entonces","luego",
    "después","antes","finalmente","primero","segundo","tercero",
}
_RE_TOKENS = re.compile(r'[a-záéíóúüñ]+', re.IGNORECASE)

def calculate_lexical_density(slide_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = preparar_texto_slide(slide_data)
    tokens = _tokenize(text)

    if len(tokens) < 5:
        return None

    total_words = len(tokens)
    functional_words = sum(1 for t in tokens if t in _STOPWORDS)
    content_words = total_words - functional_words

    ld = (content_words / total_words) * 100
    ldn = ld / 100.0

    return {
        "total_palabras":     total_words,
        "palabras_contenido": content_words,
        "palabras_funcional": functional_words,
        "dl":  round(ld, 2),
        "dln": round(ldn, 4)
    }

def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _RE_TOKENS.findall(text)]