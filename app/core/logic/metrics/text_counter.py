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

_RE_PUNTUACION = re.compile(r'[.!?;]\s*|\n')
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
    Mejora: Ahora considera cada línea (bullet) como una frase independiente
    para evitar que el promedio de palabras/frase se dispare en listas.
    """
    frases_finales = []
    # Dividimos primero por líneas para respetar la estructura de la slide
    lineas = texto.split('\n')
    
    for linea in lineas:
        linea = linea.strip()
        if not linea: continue
        
        # Si es un bullet, es una frase automática
        if _RE_BULLET.match(linea):
            frases_finales.append(linea)
        # Si tiene puntuación interna, subdividimos
        elif _RE_PUNTUACION.search(linea):
            partes = _RE_PUNTUACION.split(linea)
            frases_finales.extend([p.strip() for p in partes if p.strip()])
        # Si es una línea larga sin puntuación, segmentamos por longitud académica
        elif len(linea.split()) > _MAX_PALABRAS_FRASE:
            palabras = linea.split()
            for i in range(0, len(palabras), _MAX_PALABRAS_FRASE):
                frases_finales.append(" ".join(palabras[i:i + _MAX_PALABRAS_FRASE]))
        else:
            frases_finales.append(linea)
            
    return frases_finales


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
    """
    Mejora: Detección de hiatos y diptongos para mayor precisión en FSZ.
    """
    palabra = palabra.lower().strip()
    if not palabra: return 0
    
    # Manejo de 'y' como vocal al final
    if palabra.endswith('y'):
        palabra = palabra[:-1] + 'i'
        
    count = 0
    vowels = _VOCALES
    i = 0
    while i < len(palabra):
        if palabra[i] in vowels:
            count += 1
            # Si hay dos vocales juntas, checamos si es hiato o diptongo
            if i + 1 < len(palabra) and palabra[i+1] in vowels:
                v1, v2 = palabra[i], palabra[i+1]
                # HIATO: Dos fuertes juntas (a-e, o-a, etc.) se cuentan como 2 sílabas
                # Si NO es hiato (es decir, es diptongo), saltamos la vocal para contar solo 1
                if not (v1 in _FUERTES and v2 in _FUERTES):
                    i += 1 
        i += 1
    return max(1, count)


def _aplanar_lineas(texto):
    return [b.strip() for b in texto.split("\n") if b.strip()]