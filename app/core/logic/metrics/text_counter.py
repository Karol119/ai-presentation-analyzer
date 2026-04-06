"""
text_counter.py
Utilidades de conteo para el cálculo de complejidad textual.

Funciones expuestas:
    preparar_texto_slide(slide_data)  → texto listo para analizar
    segmentar_frases(texto)           → lista de frases
    contar_palabras(texto)            → int
    contar_silabas(texto)             → int
"""

import re

_MAX_PALABRAS_FRASE = 20

_RE_PUNTUACION = re.compile(r'[.!?;]\s+')
_RE_BULLET     = re.compile(r'^\s*([•\-\*\u2022]|\d+[\.\)])\s+')

# Tokens que NO son palabras del idioma — se excluyen del conteo de palabras
# para no distorsionar el FSZ con números, IPs, puertos, siglas numéricas, etc.
_RE_TOKEN_NO_PALABRA = re.compile(
    r'^\d+$'                   # número puro: 8, 22, 1023
    r'|^\d+[\.,/\-:]\d+'       # número compuesto: 192.168, 0-1023, 20/21
    r'|^[A-Z]{1,6}\d+$'        # sigla numérica: BD101, TCP22
)

_VOCALES = set('aeiouáéíóúüAEIOUÁÉÍÓÚÜ')
_DEBILES = set('iuüIUÜ')
_FUERTES = set('aeoáéóAEOÁÉÓ')


def preparar_texto_slide(slide_data):
    """
    Combina título + cuerpo en un único texto limpio.
    Footer excluido siempre — es metadata, no contenido educativo.
    """
    partes = []

    titulo = slide_data.get("title", "").strip()
    if titulo:
        partes.append(titulo)

    for bloque in slide_data.get("content", []):
        bloque = bloque.strip()
        if bloque:
            partes.append(bloque)

    return "\n".join(partes)


def segmentar_frases(texto):
    """
    Divide el texto en frases respetando la estructura de diapositiva:
      - Cada bullet = 1 frase
      - Líneas con puntuación → dividir por . ! ? ;
      - Líneas largas sin puntuación (> MAX palabras) → segmentar cada MAX palabras
      - Líneas cortas sin puntuación → 1 frase
    """
    frases = []

    for linea in _aplanar_lineas(texto):
        linea = linea.strip()
        if not linea:
            continue

        if _RE_BULLET.match(linea):
            frases.append(linea)
            continue

        if _RE_PUNTUACION.search(linea):
            for parte in _RE_PUNTUACION.split(linea):
                parte = parte.strip()
                if parte:
                    frases.append(parte)
            continue

        palabras = linea.split()
        if len(palabras) > _MAX_PALABRAS_FRASE:
            for i in range(0, len(palabras), _MAX_PALABRAS_FRASE):
                segmento = " ".join(palabras[i:i + _MAX_PALABRAS_FRASE])
                if segmento:
                    frases.append(segmento)
            continue

        frases.append(linea)

    return [f for f in frases if f.strip()]


def contar_palabras(texto):
    """
    Cuenta solo palabras del idioma.
    Excluye números sueltos y tokens técnicos que distorsionan el FSZ.
    """
    tokens = texto.split()
    return sum(1 for t in tokens if not _RE_TOKEN_NO_PALABRA.match(t))


def contar_silabas(texto):
    """
    Cuenta sílabas del texto en español.
    Solo procesa tokens con letras — ignora números y códigos.
    """
    total = 0
    for token in re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+', texto):
        total += _silabas_palabra(token)
    return total


def _silabas_palabra(palabra):
    palabra = palabra.lower()
    if not palabra:
        return 0

    silabas = 0
    i = 0
    n = len(palabra)

    while i < n:
        c = palabra[i]
        if c in _VOCALES:
            silabas += 1
            if i + 1 < n and palabra[i + 1] in _VOCALES:
                v1, v2 = c, palabra[i + 1]
                if v1 in _DEBILES or v2 in _DEBILES:
                    i += 1
        i += 1

    return max(1, silabas)


def _aplanar_lineas(texto):
    return [b.strip() for b in texto.split("\n") if b.strip()]