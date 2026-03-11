import os
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

def extraer_datos_pptx(ruta_pptx):
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
            "images": []  
        }

        if slide.shapes.title and slide.shapes.title.text.strip():
            slide_info["title"] = slide.shapes.title.text.strip()
        
        candidatos_titulo = []
        for shape in slide.shapes:

            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                slide_info["images"].append(shape.name) 

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