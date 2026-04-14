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
from app.core.logic.metrics.text_counter import preparar_texto_slide

# ──────────────────────────────────────────────────────────────────────────────
# Stopwords del español (palabras funcionales que NO son contenido)
# Artículos, preposiciones, conjunciones, pronombres, auxiliares comunes
# ──────────────────────────────────────────────────────────────────────────────

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


def calcular_densidad_lexica(slide_data):
    """
    Calcula DL y DLN para una diapositiva.

    Returns:
        {
            "total_palabras":     int,
            "palabras_contenido": int,
            "palabras_funcional": int,
            "dl":  float,    # densidad léxica en porcentaje (0–100)
            "dln": float     # densidad léxica normalizada (0–1)
        }
        None si no hay suficiente texto.
    """
    texto = preparar_texto_slide(slide_data)
    tokens = _tokenizar(texto)

    if len(tokens) < 5:
        return None

    total    = len(tokens)
    funcional = sum(1 for t in tokens if t in _STOPWORDS)
    contenido = total - funcional

    dl  = (contenido / total) * 100
    dln = dl / 100.0

    return {
        "total_palabras":     total,
        "palabras_contenido": contenido,
        "palabras_funcional": funcional,
        "dl":  round(dl, 2),
        "dln": round(dln, 4)
    }


def _tokenizar(texto):
    """Convierte el texto en lista de tokens en minúsculas, solo palabras."""
    return [
        t.lower()
        for t in re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+', texto)
    ]