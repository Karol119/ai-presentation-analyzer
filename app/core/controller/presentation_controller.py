# app/core/controller/presentation_controller.py

from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import  contar_diapositivas
from app.data.queries import existe_hash_en_db
from app.data.persistence import registrar_presentacion 

def orquestar_proceso_completo(ruta_pptx, id_materia):
    """
    Orquesta el proceso completo recibiendo la ruta y el ID desde main_gui.py
    """
    try:
        # 1. Valida tamaño (30MB)
        es_valido, mensaje_val = validar_tamano_archivo(ruta_pptx, limite_mb=30)
        if not es_valido:
            return False, mensaje_val
        
        # 2. Genera hash único
        hash_unico = generar_hash_archivo(ruta_pptx)
        print(f"-> Hash generado: {hash_unico}")

        # 3. Verifica existencia (Usa queries.py)
        if existe_hash_en_db(hash_unico):
            return False, "Esta presentación ya ha sido procesada anteriormente."
        
        # 4. Conteo de diapositivas
        num_diapositivas = contar_diapositivas(ruta_pptx)
        if num_diapositivas == 0:
            return False, "No se pudo leer el archivo o está vacío."
        
        print(f"El archivo tiene {num_diapositivas} diapositivas. Iniciando extracción...")

        # 7. ALMACENAR EN BASE DE DATOS (Usa persistence.py)
        exito_registro, id_pres = registrar_presentacion(
            ruta_pptx, 
            hash_unico, 
            num_diapositivas, 
            id_materia
        )
        
        if exito_registro:
            return True, f"Registrado en BD con ID: {id_pres[:8]}"
        else:
            return False, "Error al persistir los datos en la base de datos."

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"