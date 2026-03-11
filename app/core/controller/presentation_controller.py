from app.presentation.views.gui import interfaz_seleccionar_archivo
from app.core.logic.file_validator import validar_tamano_archivo # <--- Paso 2
from app.core.logic.text_extractor import extraer_datos_pptx      # <--- Paso 3
from app.core.logic.vectorizer import formatear_para_vectorizacion # <--- Paso 4
from app.data.presentation_repository import guardar_todo        # <--- Paso 5

def orquestar_proceso_completo():
    # 1. Selecciona el archivo
    ruta_pptx = interfaz_seleccionar_archivo()
    if not ruta_pptx: 
        return False, "Operación cancelada."

    try:
        # 2. Valida tamaño (30MB)
        es_valido, mensaje_val = validar_tamano_archivo(ruta_pptx, limite_mb=30)
        if not es_valido:
            return False, mensaje_val

        # 3. Extraer texto
        datos_crudos = extraer_datos_pptx(ruta_pptx)
        
        # 4. Vectorizar
        datos_listos = formatear_para_vectorizacion(datos_crudos)
        
        # 5. Almacenar
        ruta_final = guardar_todo(ruta_pptx, datos_listos)
        
        return True, f"¡Éxito! Archivo procesado y guardado en: {ruta_final}"

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"