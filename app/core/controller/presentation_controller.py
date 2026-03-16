from app.core.logic.hash_generator import generar_hash_archivo
from app.presentation.views.gui import interfaz_seleccionar_archivo
from app.core.logic.file_validator import validar_tamano_archivo # <--- Validador de tamaño de archivo
from app.core.logic.hash_generator import generar_hash_archivo   # <--- Generador de hash para archivos grandes
from app.core.logic.text_extractor import extraer_datos_pptx      # <--- Extractor de texto de PPTX
from app.core.logic.vectorizer import formatear_para_vectorizacion # <--- Formateador para vectorización
from app.data.presentation_repository import guardar_todo        # <--- Función para guardar toda la información procesada

def orquestar_proceso_completo():
    """
    Orquesta el proceso completo de análisis de presentación.
        Args:       
            None

        Returns:
            (bool, str): Tupla con el resultado del proceso y un mensaje descriptivo.
            
        Flujo:
            1. El usuario selecciona un archivo PPTX a través de la interfaz gráfica.
            2. El sistema valida que el archivo no exceda los 30MB.
            3. Si el archivo es válido, se extrae el texto de cada diapositiva.
            4. El texto extraído se formatea para ser compatible con el proceso de vectorización.
            5. Finalmente, se almacena toda la información procesada en una ubicación definida, y se devuelve un mensaje de éxito o error según corresponda.
            
    """
    # 1. Selecciona el archivo
    ruta_pptx = interfaz_seleccionar_archivo()
    if not ruta_pptx: 
        return False, "Operación cancelada."

    try:
        # 2. Valida tamaño (30MB)
        es_valido, mensaje_val = validar_tamano_archivo(ruta_pptx, limite_mb=30)
        if not es_valido:
            return False, mensaje_val
        
        # 3. El controlador llama a la función para el hash antes de procesar
        hash_unico = generar_hash_archivo(ruta_pptx)
        print(f"-> Hash generado: {hash_unico}")

        # 4. Extraer texto
        datos_crudos = extraer_datos_pptx(ruta_pptx)
        
        # 5. Vectorizar
        datos_listos = formatear_para_vectorizacion(datos_crudos)
        
        # 6. Almacenar
        ruta_final = guardar_todo(ruta_pptx, datos_listos)
        
        return True, f"¡Éxito! Archivo procesado y guardado en: {ruta_final}"

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"