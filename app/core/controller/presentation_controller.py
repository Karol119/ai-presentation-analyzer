from app.data.presentation_repository import seleccionar_y_guardar_archivo

def orquestar_carga_presentacion():
    # El orquestador llama a la función de la capa de datos
    resultado_ruta = seleccionar_y_guardar_archivo()
    
    if resultado_ruta:
        return True, f"Archivo cargado exitosamente en: {resultado_ruta}"
    else:
        return False, "Operación cancelada o error en la carga."