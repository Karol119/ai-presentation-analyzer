# app/core/logic/text_extractor.py
import os
import re
from typing import List, Dict, Any
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

UMBRAL_SUPERIOR_TITULO = 0.25
UMBRAL_SUPERIOR_PIE = 0.75  
MAX_PALABRAS_TITULO = 25
MAX_CARACTERES_TITULO = 180

_RE_SOLO_NUMEROS = re.compile(r'^\d{1,3}$')

_PATRONES_META = [
    re.compile(r'\b(materia|asignatura|unidad|semestre|grupo|docente|profesor|instituto|tecnol[oó]gico|universidad|facultad)\b', re.IGNORECASE),
    re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),
    re.compile(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', re.IGNORECASE),
    re.compile(r'\b[A-Z]{2,6}\d{3,4}\b'),
    re.compile(r'^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+$'),
]

def contar_diapositivas(ruta_pptx: str) -> int:
    try:
        return len(Presentation(ruta_pptx).slides)
    except Exception as e:
        print(f"[text_extractor] Error al contar diapositivas: {e}")
        return 0

def extraer_datos_pptx(ruta_pptx: str) -> Dict[str, Any]:
    presentacion = Presentation(ruta_pptx)
    altura_diapositiva = presentacion.slide_height

    resultado = {
        "filename":     os.path.basename(ruta_pptx),
        "total_slides": len(presentacion.slides),
        "slides":       []
    }

    for indice, diapositiva in enumerate(presentacion.slides):
        resultado["slides"].append(
            _procesar_diapositiva(diapositiva, indice + 1, altura_diapositiva)
        )

    return resultado

def _procesar_diapositiva(diapositiva: Any, numero_diapositiva: int, altura_diapositiva: float) -> Dict[str, Any]:
    info_diapositiva = {
        "slide_number":      numero_diapositiva,
        "title":             "",
        "content":           [],
        "footer":            [],
        "images":            [],
        "tiene_solo_imagen": False,
    }

    if diapositiva.shapes.title and diapositiva.shapes.title.has_text_frame and diapositiva.shapes.title.text.strip():
        titulo_crudo = _limpiar_texto(diapositiva.shapes.title.text)
        if not _es_numero_decorativo(diapositiva.shapes.title, titulo_crudo, altura_diapositiva):
            info_diapositiva["title"] = titulo_crudo

    candidatos_titulo: List[Dict[str, Any]] = []

    for forma in diapositiva.shapes:
        _procesar_forma(forma, info_diapositiva, candidatos_titulo, altura_diapositiva)

    if not info_diapositiva["title"] and candidatos_titulo:
        candidatos_titulo.sort(key=lambda x: (x["size"] or 0, -x["top"]), reverse=True)
        mejor_candidato = candidatos_titulo[0]
        
        if mejor_candidato["words"] <= MAX_PALABRAS_TITULO and len(mejor_candidato["text"]) <= MAX_CARACTERES_TITULO:
            info_diapositiva["title"] = mejor_candidato["text"]
            info_diapositiva["content"].extend([c["text"] for c in candidatos_titulo[1:]])
        else:
            info_diapositiva["content"].extend([c["text"] for c in candidatos_titulo])

    sin_texto = len(info_diapositiva["content"]) == 0 and info_diapositiva["title"] == ""
    info_diapositiva["tiene_solo_imagen"] = sin_texto and len(info_diapositiva["images"]) > 0
    info_diapositiva["image_count"] = len(info_diapositiva["images"])

    return info_diapositiva

def _procesar_forma(forma: Any, info_diapositiva: Dict[str, Any], candidatos_titulo: List[Dict[str, Any]], altura_diapositiva: float) -> None:
    if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
        for hijo in forma.shapes:
            _procesar_forma(hijo, info_diapositiva, candidatos_titulo, altura_diapositiva)
        return

    es_imagen = False
    if forma.shape_type == MSO_SHAPE_TYPE.PICTURE:
        es_imagen = True
    elif getattr(forma, "is_placeholder", False) and hasattr(forma, "image"):
        es_imagen = True

    if es_imagen:
        info_diapositiva["images"].append(forma.name)
        return

    if forma.shape_type == MSO_SHAPE_TYPE.TABLE:
        for fila in forma.table.rows:
            for celda in fila.cells:
                texto_celda = _limpiar_texto(celda.text)
                if texto_celda and not _es_numero_decorativo(forma, texto_celda, altura_diapositiva):
                    info_diapositiva["content"].append(texto_celda)
        return

    if not getattr(forma, "has_text_frame", False) or not forma.has_text_frame or not forma.text.strip():
        return

    texto = _limpiar_texto(forma.text)
    if not texto or texto == info_diapositiva["title"]:
        return

    if _es_numero_decorativo(forma, texto, altura_diapositiva):
        return

    proporcion_superior = forma.top / altura_diapositiva
    conteo_palabras = len(texto.split())

    if proporcion_superior >= UMBRAL_SUPERIOR_PIE:
        if _es_pie_de_pagina(texto, conteo_palabras, proporcion_superior):
            info_diapositiva["footer"].append(texto)
            return

    if not info_diapositiva["title"] and proporcion_superior < UMBRAL_SUPERIOR_TITULO:
        tamano_fuente = _obtener_tamano_fuente(forma)
        candidatos_titulo.append({
            "text": texto, 
            "size": tamano_fuente,
            "top": forma.top, 
            "words": conteo_palabras
        })
        return

    info_diapositiva["content"].append(texto)
    
def _es_pie_de_pagina(texto: str, conteo_palabras: int, proporcion_superior: float) -> bool:
    if proporcion_superior >= 0.85 and conteo_palabras <= 25:
        return True
    if conteo_palabras <= 6:
        return True
    if conteo_palabras <= 15:
        for patron in _PATRONES_META:
            if patron.search(texto):
                return True
    return False

def _es_numero_decorativo(forma: Any, texto: str, altura_diapositiva: float) -> bool:
    texto_limpio = texto.strip()
    if not bool(_RE_SOLO_NUMEROS.match(texto_limpio)):
        return False
    
    proporcion_superior = forma.top / altura_diapositiva
    es_zona_numeracion = proporcion_superior < 0.05 or proporcion_superior > 0.90
    
    nombre_obj = forma.name.lower()
    es_tipo_num_pagina = "slide number" in nombre_obj or "page" in nombre_obj

    return es_zona_numeracion or es_tipo_num_pagina

def _obtener_tamano_fuente(forma: Any) -> int:
    if getattr(forma, "has_text_frame", False):
        try:
            for parrafo in forma.text_frame.paragraphs:
                for run in parrafo.runs:
                    if run.font and run.font.size:
                        return int(run.font.size)
        except Exception:
            pass
    return 0

def _limpiar_texto(texto: str) -> str:
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    lineas = [linea.strip() for linea in texto.split("\n") if linea.strip()]
    return " \n ".join(lineas)

def limpiar_para_metricas(texto: str) -> str:
    if not texto: return ""
    texto_temp = re.sub(r'\s+', ' ', texto)
    return texto_temp.strip()