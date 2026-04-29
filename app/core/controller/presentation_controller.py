# app/core/controller/presentation_controller.py
import json
import os
from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import count_slides

# Importaciones de datos
from app.data.queries import existe_hash_en_db, obtener_id_version_actual, obtener_id_y_version_presentacion
from app.data.persistence import (
    registrar_presentacion, 
    eliminar_presentacion_completa,
    actualizar_estado_analisis,
    registrar_analisis_completo,
    registrar_nueva_version
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
    Ejecuta el análisis de IA, guarda el JSON en BD y actualiza las métricas de la versión.
    """
    try:
        if status_cb: status_cb("Iniciando motores de IA...")
        resultado_datos = analyze_presentation(ruta_pptx, status_cb=status_cb)

        # 1. Persistencia en Base de Datos
        id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
        if id_version:
            json_string = json.dumps(resultado_datos, ensure_ascii=False)
            
            # Guardamos el JSON completo en la tabla Analisis (usando tu función existente)
            registrar_analisis_completo(id_version, json_string)
            
            # Extraemos métricas para actualizar la tabla Historial_de_Versiones
            # Asumiendo que tu IA devuelve 'puntuacion_general' y 'recomendacion_general'
            score = resultado_datos.get("puntuacion_general", 0.0)
            recommendation = resultado_datos.get("recomendacion_general", "")
            
            # Llamaremos a una nueva función de persistencia para llenar los campos correspondientes
            from app.data.persistence import actualizar_metricas_version
            actualizar_metricas_version(id_version, score, recommendation)
            
            # Actualizamos el estado de la versión a "analizada" (analisis = 1)
            actualizar_estado_analisis(nombre_presentacion, id_materia, 1)

        # 2. Persistencia en Disco (Usando el nombre físico para evitar sobrescritura)
        directorio = os.path.dirname(ruta_pptx)
        nombre_fisico_sin_ext = os.path.splitext(os.path.basename(ruta_pptx))[0]
        ruta_json = os.path.join(directorio, f"{nombre_fisico_sin_ext}_analysis.json")

        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(resultado_datos, f, indent=4, ensure_ascii=False)

        return True, resultado_datos

    except Exception as e:
        print(f"Error en orquestar_analisis_ia: {e}")
        return False, str(e)
    
def orquestar_actualizacion_presentacion(ruta_pptx, nombre_presentacion, id_materia):
    """
    Orquesta el flujo para validar y añadir una nueva versión a una presentación existente.
    """
    try:
        # 1. Valida tamaño (30MB)
        es_valido, mensaje_val = validar_tamano_archivo(ruta_pptx, limite_mb=30)
        if not es_valido:
            return False, mensaje_val
        
        # 2. Genera hash
        hash_unico = generar_hash_archivo(ruta_pptx)
        
        # Opcional pero recomendado: evitar subir un archivo que ya existe en general
        if existe_hash_en_db(hash_unico):
            return False, "El archivo seleccionado es idéntico a una versión que ya existe en el sistema."
        
        # 3. Conteo de diapositivas
        num_diapositivas = count_slides(ruta_pptx)
        if num_diapositivas == 0:
            return False, "No se pudo leer el archivo o está vacío."
        
        # 4. Obtener ID original y calcular la nueva versión
        id_pres, version_actual = obtener_id_y_version_presentacion(nombre_presentacion, id_materia)
        if not id_pres:
            return False, "No se encontró la presentación original en la base de datos."
        
        nueva_version = version_actual + 1

        # 5. Persistir datos y archivos
        exito_registro, msj = registrar_nueva_version(
            id_pres, ruta_pptx, hash_unico, num_diapositivas, nueva_version, id_materia
        )
        
        if exito_registro:
            return True, "Presentación actualizada."
        else:
            return False, msj

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"