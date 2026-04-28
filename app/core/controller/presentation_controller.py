# app/core/controller/presentation_controller.py
import json
import os
from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import count_slides

# Importaciones de datos
from app.data.queries import existe_hash_en_db, obtener_id_version_actual
from app.data.persistence import (
    registrar_presentacion, 
    eliminar_presentacion_completa,
    actualizar_estado_analisis,
    registrar_analisis_completo  # <-- Esta debe existir en persistence.py
)
from app.core.controller.analyzer_controller import analyze_presentation

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
        num_diapositivas = count_slides(ruta_pptx)
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

def orquestar_eliminacion_presentacion(nombre_presentacion, id_materia):
    """
    Actúa como puente entre la UI y la persistencia para eliminar 
    física y lógicamente una presentación.
    """
    return eliminar_presentacion_completa(nombre_presentacion, id_materia)

def orquestar_actualizacion_analisis(nombre_presentacion, id_materia):
    """
    Marca una presentación como analizada en la base de datos tras finalizar el proceso.
    """
    return actualizar_estado_analisis(nombre_presentacion, id_materia, 1)

def orquestar_analisis_ia(ruta_pptx: str, nombre_presentacion: str, id_materia: int, status_cb=None):
    """
    Ejecuta el análisis de IA, guarda el JSON en BD (campo resultado) y en disco.
    """
    try:
        if status_cb: status_cb("Iniciando motores de IA...")
        resultado_datos = analyze_presentation(ruta_pptx, status_cb=status_cb)

        # 1. Persistencia en Base de Datos
        id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
        if id_version:
            json_string = json.dumps(resultado_datos, ensure_ascii=False)
            # Guardamos el JSON completo en la tabla Analisis
            registrar_analisis_completo(id_version, json_string)
            # Actualizamos el estado a analizado
            actualizar_estado_analisis(nombre_presentacion, id_materia, 1)

        # 2. Persistencia en Disco
        directorio = os.path.dirname(ruta_pptx)
        nombre_sin_ext = os.path.splitext(nombre_presentacion)[0]
        ruta_json = os.path.join(directorio, f"{nombre_sin_ext}_analysis.json")

        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(resultado_datos, f, indent=4, ensure_ascii=False)

        return True, resultado_datos

    except Exception as e:
        print(f"Error en orquestar_analisis_ia: {e}")
        return False, str(e)