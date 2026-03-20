# app/core/controller/presentation_controller.py

from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import contar_diapositivas
from app.data.queries import existe_hash_en_db
from app.data.persistence import registrar_presentacion, eliminar_presentacion_completa # <-- Añadir importación

def orquestar_proceso_completo(ruta_pptx, id_materia):
    """
    Orquesta el proceso de carga, validación y registro de una presentación.
    """
    try:
        # 1. Valida tamaño (30MB)
        es_valido, mensaje_val = validar_tamano_archivo(ruta_pptx, limite_mb=30)
        if not es_valido:
            return False, mensaje_val
        
        # 2. Genera hash único
        hash_unico = generar_hash_archivo(ruta_pptx)
        
        # 3. Verifica existencia
        if existe_hash_en_db(hash_unico):
            return False, "Esta presentación ya ha sido procesada anteriormente."
        
        # 4. Conteo de diapositivas
        num_diapositivas = contar_diapositivas(ruta_pptx)
        if num_diapositivas == 0:
            return False, "No se pudo leer el archivo o está vacío."
        
        # 5. ALMACENAR EN BASE DE DATOS Y STORAGE
        exito_registro, id_pres = registrar_presentacion(
            ruta_pptx, 
            hash_unico, 
            num_diapositivas, 
            id_materia
        )
        
        if exito_registro:
            return True, f"Registrado con éxito."
        else:
            return False, "Error al persistir los datos en la base de datos."

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"

# =========================================================
# NUEVA FUNCIÓN DE BORRADO (CAPA DE NEGOCIO)
# =========================================================

def orquestar_eliminacion_presentacion(nombre_presentacion, id_materia):
    """
    Actúa como puente entre la UI y la persistencia para eliminar 
    física y lógicamente una presentación.
    """
    # Aquí podrías añadir lógica de negocio adicional en el futuro,
    # como verificar si el usuario tiene permisos o registrar un log.
    return eliminar_presentacion_completa(nombre_presentacion, id_materia)