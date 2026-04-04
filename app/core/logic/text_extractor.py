import os
import re
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

_UMBRAL_TITULO_TOP   = 0.25
_UMBRAL_PIE_TOP      = 0.80
_MAX_PALABRAS_TITULO = 25
_MAX_CHARS_TITULO    = 180

# Texto que es solo número (página o decorativo) — se descarta siempre
_RE_SOLO_NUMERO = re.compile(r'^\d{1,3}$')

# Patrones de metadata institucional para reforzar detección de pie
_PATRONES_META = [
    re.compile(r'\b(materia|asignatura|unidad|semestre|grupo|docente|profesor|instituto|tecnol[oó]gico)\b', re.IGNORECASE),
    re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),               # fecha 12/03/2025
    re.compile(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', re.IGNORECASE),
    re.compile(r'\b[A-Z]{2,6}\d{3,4}\b'),                        # clave materia: BD101
    re.compile(r'^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+$'),  # nombre completo
]


def contar_diapositivas(ruta_pptx):
    try:
        return len(Presentation(ruta_pptx).slides)
    except Exception as e:
        print(f"[text_extractor] Error: {e}")
        return 0


def extraer_datos_pptx(ruta_pptx):
    prs  = Presentation(ruta_pptx)
    alto = prs.slide_height

    resultado = {
        "filename":     os.path.basename(ruta_pptx),
        "total_slides": len(prs.slides),
        "slides":       []
    }

    for i, slide in enumerate(prs.slides):
        resultado["slides"].append(
            _procesar_diapositiva(slide, i + 1, alto)
        )

    return resultado


def _procesar_diapositiva(slide, numero, alto_slide):
    info = {
        "slide_number":      numero,
        "title":             "",
        "content":           [],
        "footer":            [],
        "images":            [],
        "tiene_solo_imagen": False,
    }

    # Título oficial del placeholder de PowerPoint
    if slide.shapes.title and slide.shapes.title.text.strip():
        titulo_raw = _limpiar_texto(slide.shapes.title.text)
        # Descartar si el placeholder de título contiene solo un número decorativo
        if not _es_numero_decorativo(titulo_raw):
            info["title"] = titulo_raw

    candidatos_titulo = []

    for shape in slide.shapes:
        _procesar_shape(shape, info, candidatos_titulo, alto_slide)

    # Resolver título por fallback
    if not info["title"] and candidatos_titulo:
        candidatos_titulo.sort(
            key=lambda x: (x["size"] or 0, -x["top"]),
            reverse=True
        )
        mejor = candidatos_titulo[0]
        if mejor["words"] <= _MAX_PALABRAS_TITULO and len(mejor["text"]) <= _MAX_CHARS_TITULO:
            info["title"] = mejor["text"]
            for c in candidatos_titulo[1:]:
                info["content"].append(c["text"])
        else:
            for c in candidatos_titulo:
                info["content"].append(c["text"])

    # Limpiar números decorativos del contenido
    info["content"] = [
        t for t in info["content"]
        if not _es_numero_decorativo(t)
    ]

    sin_texto = len(info["content"]) == 0 and info["title"] == ""
    info["tiene_solo_imagen"] = sin_texto and len(info["images"]) > 0

    return info


def _procesar_shape(shape, info, candidatos_titulo, alto_slide):
    # Grupos: recursivo
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            _procesar_shape(child, info, candidatos_titulo, alto_slide)
        return

    # Imágenes
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        info["images"].append(shape.name)
        return

    if not hasattr(shape, "text") or not shape.text.strip():
        return

    texto = _limpiar_texto(shape.text)
    if not texto or texto == info["title"]:
        return

    # Descartar números decorativos antes de cualquier otra lógica
    if _es_numero_decorativo(texto):
        return

    top_ratio = shape.top / alto_slide
    palabras  = len(texto.split())

    # Pie de página: lógica mejorada en dos niveles
    if top_ratio >= _UMBRAL_PIE_TOP:
        if _es_pie_de_pagina(texto, palabras):
            info["footer"].append(texto)
            return

    # Candidato a título (fallback, tercio superior)
    if not info["title"] and top_ratio < _UMBRAL_TITULO_TOP:
        size = _tamanio_fuente(shape)
        candidatos_titulo.append({
            "text": texto, "size": size,
            "top": shape.top, "words": palabras
        })
        return

    info["content"].append(texto)


def _es_pie_de_pagina(texto, palabras):
    """
    Criterio más estricto:
    - ≤ 6 palabras: siempre es pie (fecha, número de página, nombre corto)
    - 7–15 palabras: solo si coincide con patrón de metadata institucional
    - > 15 palabras: nunca es pie, es contenido que quedó abajo
    """
    if palabras <= 6:
        return True

    if palabras <= 15:
        for patron in _PATRONES_META:
            if patron.search(texto):
                return True
        return False

    return False


def _es_numero_decorativo(texto):
    """
    Devuelve True si el texto es solo un número de 1 a 3 dígitos.
    Estos son típicamente numeración de página o marcadores decorativos de paso.
    """
    limpio = texto.strip()
    return bool(_RE_SOLO_NUMERO.match(limpio))


def _tamanio_fuente(shape):
    try:
        size = shape.text_frame.paragraphs[0].runs[0].font.size
        return int(size) if size else 0
    except Exception:
        return 0


def _limpiar_texto(texto):
    texto  = texto.replace("\r\n", "\n").replace("\r", "\n")
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    return " \n ".join(lineas)