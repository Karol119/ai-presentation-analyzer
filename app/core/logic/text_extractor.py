import os
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

def extraer_datos_pptx(ruta_pptx):
    """Extrae el texto y las imágenes de un archivo PPTX, organizándolos por diapositiva.

    Args:
        ruta_pptx (str): La ruta del archivo PPTX a procesar.

    Returns:
        dict: Un diccionario con los datos extraídos de la presentación.
        

    El diccionario tiene la siguiente estructura:
        {
            "filename": "nombre_del_archivo.pptx",
            "slides": [
                {
                    "slide_number": 1,
                    "title": "Título de la diapositiva",
                    "content": ["Texto de la diapositiva", "Más texto..."],
                    "images": ["Imagen 1", "Imagen 2"]  # Lista de nombres de imágenes
                },
                {
                    "slide_number": 2,
                    "title": "Título de la segunda diapositiva",  
                    "content": ["Texto de la segunda diapositiva"],
                    "images": []  # Sin imágenes en esta diapositiva
                },
                ...
            ]
        }
    """
    prs = Presentation(ruta_pptx)
    presentacion_estructurada = {
        "filename": os.path.basename(ruta_pptx),
        "slides": []
    }

    for i, slide in enumerate(prs.slides):
        slide_info = {
            "slide_number": i + 1,
            "title": "",
            "content": [],
            "images": []  # <--- Ahora será una lista de nombres
        }

        # 1. Título oficial
        if slide.shapes.title and slide.shapes.title.text.strip():
            slide_info["title"] = slide.shapes.title.text.strip()
        
        candidatos_titulo = []
        for shape in slide.shapes:
            # --- DETECCIÓN DE IMÁGENES ---
            # El tipo 13 o PICTURE es el estándar para imágenes insertadas
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                slide_info["images"].append(shape.name) # Extrae el nombre (ej. "Imagen 2")

            # --- DETECCIÓN DE TEXTO (con tu heurística) ---
            if hasattr(shape, "text") and shape.text.strip():
                texto = shape.text.strip()
                if slide_info["title"] == texto: continue

                umbral_superior = prs.slide_height * 0.25
                if not slide_info["title"] and shape.top < umbral_superior:
                    try:
                        size = shape.text_frame.paragraphs[0].runs[0].font.size
                    except: size = 0
                    candidatos_titulo.append({"text": texto, "size": size, "top": shape.top})
                else:
                    slide_info["content"].append(texto)

        # Resolución de títulos (lo que ya tenías)
        if not slide_info["title"] and candidatos_titulo:
            candidatos_titulo.sort(key=lambda x: (x['size'] or 0, -x['top']), reverse=True)
            mejor = candidatos_titulo[0]
            if len(mejor['text']) < 150:
                slide_info["title"] = mejor['text']
                for c in candidatos_titulo[1:]: slide_info["content"].append(c['text'])
            else:
                for c in candidatos_titulo: slide_info["content"].append(c['text'])

        presentacion_estructurada["slides"].append(slide_info)

    return presentacion_estructurada