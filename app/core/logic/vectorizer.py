def formatear_para_vectorizacion(datos_extraidos):
    """Formatea los datos extraídos de la presentación para que sean compatibles con el proceso de vectorización.
    

    Args:
        datos_extraidos (dict): El diccionario con los datos extraídos de la presentación, que incluye el nombre del archivo, los títulos de las diapositivas, el contenido y las imágenes.

    Returns:
        dict: El diccionario formateado para vectorización.
        
    El diccionario resultante tiene la siguiente estructura:
        {
            "filename": "nombre_del_archivo.pptx",
            "combined_titles": "Título de la diapositiva 1 Título de la diapositiva 2 ...",
            "extracted_data": [
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
    titulos_reales = [s["title"] for s in datos_extraidos["slides"] if s["title"]]
    
    vectorizacion_final = {
        "filename": datos_extraidos["filename"],
        "combined_titles": " ".join(titulos_reales),
        "extracted_data": datos_extraidos["slides"]
    }
    
    return vectorizacion_final