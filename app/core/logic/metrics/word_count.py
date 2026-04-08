# app/core/logic/metrics/word_count.py
"""
word_count.py
Métrica de palabras por diapositiva (WPS).

CAMBIO: slides con imagen tienen umbral mínimo reducido a 15 palabras
porque la imagen complementa el texto visualmente.

Escala:
    0  – 14   → insuficiente
    15 – 39   → escasa  (o optima si tiene imagen)
    40 – 75   → optima
    76 – 120  → densa
    120+      → saturada
"""

import re

MIN_OPTIMO          = 40
MIN_OPTIMO_IMAGEN   = 15   # umbral reducido cuando hay imagen
MAX_OPTIMO          = 75
PENALIZACION_EXCESO = 15

_ESCALA_BASE = [
    (14,  "insuficiente"),
    (39,  "escasa"),
    (75,  "optima"),
    (120, "densa"),
]

_RE_NO_PALABRA = re.compile(
    r'^\d+$'
    r'|^\d+[\.,/\-:]\d+'
    r'|^[A-Z]{1,6}\d+$'
)


def calcular_wps(slide_data):
    texto        = _preparar_texto(slide_data)
    palabras     = _contar_palabras(texto)
    tiene_imagen = len(slide_data.get("images", [])) > 0

    score = _calcular_score(palabras, tiene_imagen)
    zona  = _zona(palabras, tiene_imagen)

    return {
        "slide_number":  slide_data.get("slide_number"),
        "palabras":      palabras,
        "tiene_imagen":  tiene_imagen,
        "wps_score":     round(score, 2),
        "zona":          zona,
        "en_rango":      zona == "optima",
        "exceso":        max(0, palabras - MAX_OPTIMO),
        "deficit":       max(0, _min_efectivo(tiene_imagen) - palabras) if palabras < _min_efectivo(tiene_imagen) else 0,
    }


def calcular_wps_presentacion(slides_contenido):
    resultados = [calcular_wps(s) for s in slides_contenido]
    scores     = [r["wps_score"] for r in resultados]
    palabras   = [r["palabras"]  for r in resultados]

    return {
        "resultados":           resultados,
        "wps_promedio":         round(sum(scores)   / len(scores),   2) if scores   else 0.0,
        "palabras_promedio":    round(sum(palabras) / len(palabras), 1) if palabras else 0.0,
        "slides_insuficientes": sum(1 for r in resultados if r["zona"] == "insuficiente"),
        "slides_escasas":       sum(1 for r in resultados if r["zona"] == "escasa"),
        "slides_optimas":       sum(1 for r in resultados if r["zona"] == "optima"),
        "slides_densas":        sum(1 for r in resultados if r["zona"] == "densa"),
        "slides_saturadas":     sum(1 for r in resultados if r["zona"] == "saturada"),
    }


def _min_efectivo(tiene_imagen):
    return MIN_OPTIMO_IMAGEN if tiene_imagen else MIN_OPTIMO


def _calcular_score(palabras, tiene_imagen):
    minimo = _min_efectivo(tiene_imagen)
    if minimo <= palabras <= MAX_OPTIMO:
        return 10.0
    if palabras < minimo:
        return (palabras / minimo) * 10.0
    penalizacion = (palabras - MAX_OPTIMO) / PENALIZACION_EXCESO
    return max(0.0, 10.0 - penalizacion)


def _zona(palabras, tiene_imagen):
    if palabras <= 14:
        return "insuficiente"
    minimo = _min_efectivo(tiene_imagen)
    if palabras < minimo:
        return "escasa"
    if palabras <= MAX_OPTIMO:
        return "optima"
    for limite, etiqueta in _ESCALA_BASE:
        if palabras <= limite:
            return etiqueta
    return "saturada"


def _preparar_texto(slide_data):
    partes = []
    titulo = slide_data.get("title", "").strip()
    if titulo:
        partes.append(titulo)
    for bloque in slide_data.get("content", []):
        bloque = bloque.strip()
        if bloque:
            partes.append(bloque)
    return " ".join(partes)


def _contar_palabras(texto):
    tokens = texto.split()
    return sum(1 for t in tokens if not _RE_NO_PALABRA.match(t))