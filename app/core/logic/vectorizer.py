def formatear_para_vectorizacion(datos_extraidos):
    titulos_reales = [s["title"] for s in datos_extraidos["slides"] if s["title"]]
    
    vectorizacion_final = {
        "filename": datos_extraidos["filename"],
        "combined_titles": " ".join(titulos_reales),
        "extracted_data": datos_extraidos["slides"]
    }
    
    return vectorizacion_final