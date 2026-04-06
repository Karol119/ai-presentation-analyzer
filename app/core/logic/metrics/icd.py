"""
icd.py
Calcula el Índice de Complejidad de Diapositiva (ICD).

Fórmula:
    ICD = (0.6 × CF + 0.4 × DLN) × 10   → rango [0, 10]

Escala para nivel superior:
    0.0 – 2.0  → muy simple
    2.0 – 4.0  → simple
    4.0 – 6.0  → apropiado  ← rango objetivo
    6.0 – 8.0  → complejo
    8.0 – 10.0 → muy complejo
"""

from app.core.logic.metrics.readability    import calcular_legibilidad
from app.core.logic.metrics.lexical_density import calcular_densidad_lexica

PESO_CF  = 0.6
MIN_PALABRAS_ICD = 15   # umbral mínimo para ICD confiable
PESO_DLN = 0.4

_ESCALA = [
    (2.0,  "muy simple"),
    (4.0,  "simple"),
    (6.0,  "apropiado"),
    (8.0,  "complejo"),
    (10.0, "muy complejo"),
]


def calcular_icd(slide_data):
    """
    Calcula el ICD de una diapositiva de contenido.

    Args:
        slide_data: dict del extractor (con title, content, sin footer)
                    Solo debe llamarse para slides con excluir=False.

    Returns:
        {
            "slide_number": int,
            "icd":          float,     # 0–10
            "zona":         str,       # etiqueta de la escala
            "cf":           float,
            "dln":          float,
            "fsz":          float,
            "fsz_zona":     str,
            "dl":           float,
            "palabras":     int,
            "silabas":      int,
            "frases":       int,
            "palabras_contenido": int,
            "calculable":   bool       # False si no hay suficiente texto
        }
    """
    legibilidad   = calcular_legibilidad(slide_data)
    densidad      = calcular_densidad_lexica(slide_data)

    base = {
        "slide_number": slide_data.get("slide_number"),
        "calculable":   False,
        "icd":          None,
        "zona":         None,
    }

    if legibilidad is None or densidad is None or legibilidad["palabras"] < MIN_PALABRAS_ICD:
        return base

    cf  = legibilidad["cf"]
    dln = densidad["dln"]
    icd = (PESO_CF * cf + PESO_DLN * dln) * 10
    icd = round(max(0.0, min(10.0, icd)), 2)

    base.update({
        "calculable":         True,
        "icd":                icd,
        "zona":               _zona_icd(icd),
        "cf":                 cf,
        "dln":                dln,
        "fsz":                legibilidad["fsz"],
        "fsz_zona":           legibilidad["fsz_zona"],
        "dl":                 densidad["dl"],
        "palabras":           legibilidad["palabras"],
        "silabas":            legibilidad["silabas"],
        "frases":             legibilidad["frases"],
        "prom_sil_pal":       legibilidad["prom_sil_pal"],
        "prom_pal_fra":       legibilidad["prom_pal_fra"],
        "palabras_contenido": densidad["palabras_contenido"],
    })

    return base


def calcular_icd_presentacion(slides_contenido):
    """
    Calcula el ICD para todas las diapositivas de contenido
    y agrega un resumen de la presentación.

    Args:
        slides_contenido: lista de slide_data (ya filtradas por excluir=False)

    Returns:
        {
            "resultados":    [dict por diapositiva],
            "icd_promedio":  float | None,
            "icd_minimo":    float | None,
            "icd_maximo":    float | None,
            "zona_promedio": str | None,
            "slides_calculadas":   int,
            "slides_sin_texto":    int
        }
    """
    resultados = [calcular_icd(s) for s in slides_contenido]

    valores = [r["icd"] for r in resultados if r["calculable"]]
    sin_texto = sum(1 for r in resultados if not r["calculable"])

    if not valores:
        return {
            "resultados":         resultados,
            "icd_promedio":       None,
            "icd_minimo":         None,
            "icd_maximo":         None,
            "zona_promedio":      None,
            "slides_calculadas":  0,
            "slides_sin_texto":   sin_texto,
        }

    promedio = round(sum(valores) / len(valores), 2)

    return {
        "resultados":        resultados,
        "icd_promedio":      promedio,
        "icd_minimo":        round(min(valores), 2),
        "icd_maximo":        round(max(valores), 2),
        "zona_promedio":     _zona_icd(promedio),
        "slides_calculadas": len(valores),
        "slides_sin_texto":  sin_texto,
    }


def _zona_icd(valor):
    for limite, etiqueta in _ESCALA:
        if valor <= limite:
            return etiqueta
    return "muy complejo"