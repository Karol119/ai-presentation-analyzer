from app.presentation.views.gui import interfaz_seleccionar_archivo
from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import extraer_datos_pptx, contar_diapositivas
from app.core.logic.vectorizer import formatear_para_vectorizacion
from app.data.queries import existe_hash_en_db
from app.data.persistence import registrar_presentacion 

def orquestar_proceso_completo():
    """
    Orquesta el proceso completo siguiendo el flujo estructurado.
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
        
        # 3. Genera hash único
        hash_unico = generar_hash_archivo(ruta_pptx)
        print(f"-> Hash generado: {hash_unico}")

        # 4. Verifica existencia (Usa queries.py)
        if existe_hash_en_db(hash_unico):
            return False, "Esta presentación ya ha sido procesada anteriormente."
        
        # 5. Conteo de diapositivas
        num_diapositivas = contar_diapositivas(ruta_pptx)
        if num_diapositivas == 0:
            return False, "No se pudo leer el archivo o está vacío."
        
        print(f"El archivo tiene {num_diapositivas} diapositivas. Iniciando extracción...")

        # 6. Extraer texto
        datos_crudos = extraer_datos_pptx(ruta_pptx)
        
        # 7. Formatear datos (Preparación para JSON/Vectores)
        datos_listos = formatear_para_vectorizacion(datos_crudos)
        
        # 8. ALMACENAR EN BASE DE DATOS (Usa persistence.py)
        # Nota: 'ID-MATERIA-PRUEBA' debería venir de la selección del usuario en la GUI
        id_materia_ejemplo = "ID-MATERIA-PRUEBA" 
        
        exito_registro, id_pres = registrar_presentacion(
            ruta_pptx, 
            hash_unico, 
            num_diapositivas, 
            id_materia_ejemplo
        )
        
        if exito_registro:
            return True, f"¡Éxito! Registrado en BD con ID: {id_pres[:8]}"
        else:
            return False, "Error al persistir los datos en la base de datos."

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"