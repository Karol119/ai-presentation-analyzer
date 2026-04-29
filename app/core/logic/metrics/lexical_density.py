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

def calcular_densidad_lexica(datos_diapositiva: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    texto = preparar_texto_slide(datos_diapositiva)
    tokens = _tokenizar(texto)

    if len(tokens) < 5:
        return None

    total_palabras = len(tokens)
    palabras_funcionales = sum(1 for t in tokens if t in _STOPWORDS)
    palabras_contenido = total_palabras - palabras_funcionales

    dl = (palabras_contenido / total_palabras) * 100
    dln = dl / 100.0

    return {
        "total_palabras":     total_palabras,
        "palabras_contenido": palabras_contenido,
        "palabras_funcional": palabras_funcionales,
        "dl":  round(dl, 2),
        "dln": round(dln, 4)
    }

def _tokenizar(texto: str) -> list[str]:
    return [t.lower() for t in _RE_TOKENS.findall(texto)]