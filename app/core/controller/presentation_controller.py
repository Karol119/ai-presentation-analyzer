# Cambiamos de 'app.presentation.gui' a 'app.presentation.views.gui'
# (Asumiendo que tu archivo se llama gui.py y está en la carpeta views)
from app.presentation.views.gui import interfaz_seleccionar_archivo
from app.data.presentation_repository import crear_carpeta_y_copiar

def orquestar_subida():
    # El orquestador toma el mando.
    # 1. Llama a la presentación para que dé la cara
    ruta_seleccionada = interfaz_seleccionar_archivo()
    
    if not ruta_seleccionada:
        return False, "Operación cancelada por el usuario."
    
    try:
        # 2. Le pasa la ruta a Data para el trabajo sucio
        ruta_final = crear_carpeta_y_copiar(ruta_seleccionada)
        return True, f"Éxito: Guardado en {ruta_final}"
    except Exception as e:
        return False, f"Error en el proceso: {str(e)}"