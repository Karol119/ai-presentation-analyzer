# app/core/controller/presentation_controller.py
import json
import os
import tempfile
from app.core.logic.file_validator import validar_tamano_archivo
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import contar_diapositivas
from app.data.queries import obtener_reporte_tiempo_db
from app.data.persistence import actualizar_reporte_tiempo_db
from app.data.queries import obtener_analisis_desde_db
from app.data.queries import existe_hash_en_db, obtener_id_version_actual, obtener_id_y_version_presentacion
from app.data.persistence import (
    registrar_presentacion, 
    eliminar_presentacion_completa,
    actualizar_estado_analisis,
    registrar_analisis_completo,
    registrar_nueva_version
)

from app.core.controller.analyzer_controller import analizar_presentacion
from app.core.controller.subject_controller import obtener_nombre_materia_controlador
from app.core.logic.pptx_modifier import aplicar_mejoras_pptx

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
        
        # 4. Conteo de diapositivas (Nombre actualizado)
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

        nombre_materia = obtener_nombre_materia_controlador(id_materia)

        if not nombre_materia:
            return False, "No se encontró la materia asociada a la presentación."

        # CAMBIO CLAVE: Se usa 'callback_estado' en lugar de 'status_cb' para coincidir con el controlador
        resultado_datos = analizar_presentacion(ruta_pptx, nombre_materia, callback_estado=status_cb)

        # 1. Persistencia en Base de Datos
        id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
        if id_version:
            json_string = json.dumps(resultado_datos, ensure_ascii=False)
            
            # Guardamos el JSON completo en la tabla Analisis
            registrar_analisis_completo(id_version, json_string)
            
            # Extraemos métricas basadas en la nueva estructura del JSON traducido
            datos_score = resultado_datos.get("score_global_presentacion", {})
            score = datos_score.get("score_global", 0.0)
            zona = datos_score.get("zona_global", "N/A")
            
            # Actualizamos las métricas en el historial (Score y la etiqueta de Zona como recomendación)
            from app.data.persistence import actualizar_metricas_version
            actualizar_metricas_version(id_version, score, zona)
            
            # Actualizamos el estado de la versión a "analizada"
            actualizar_estado_analisis(nombre_presentacion, id_materia, 1)

        # 2. Persistencia en Disco
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
        
        if existe_hash_en_db(hash_unico):
            return False, "El archivo seleccionado es idéntico a una versión que ya existe."
        
        # 3. Conteo de diapositivas (Nombre actualizado)
        num_diapositivas = contar_diapositivas(ruta_pptx)
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
    
def orquestar_obtener_reporte_tiempo(nombre_presentacion, id_materia):
    """Busca el id_version y orquesta la lectura del reporte de tiempo (texto crudo)."""
    id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
    if not id_version:
        return None
    return obtener_reporte_tiempo_db(id_version)

def orquestar_guardado_tiempos(nombre_presentacion, id_materia, texto_reporte):
    """Busca el id_version y orquesta la escritura del reporte de tiempo."""
    id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
    if not id_version:
        return False
    return actualizar_reporte_tiempo_db(id_version, texto_reporte)

def orquestar_obtener_analisis(nombre_presentacion, id_materia):
    """Busca el id_version y orquesta la lectura del análisis (texto crudo)."""
    id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
    if not id_version:
        return None
    return obtener_analisis_desde_db(id_version)

def orquestar_aplicar_mejoras_ia(nombre_presentacion, id_materia, ruta_pdf):
    """
    Exporta una versión modificada del PPTX directamente a la carpeta de Descargas
    sin alterar la base de datos ni crear una versión nueva oficial.
    """
    try:
        # 1. Obtener la versión actual para buscar su análisis
        id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
        
        # 2. Recuperar el análisis de la IA desde la BD
        json_raw = obtener_analisis_desde_db(id_version)
        if not json_raw:
            return False, "No hay análisis previo para aplicar mejoras."
        
        datos_analisis = json.loads(json_raw)

        # 3. Deducir la ruta del PPTX original a partir del PDF
        ruta_pptx_original = ruta_pdf.replace(".pdf", ".pptx")
        if not os.path.exists(ruta_pptx_original):
            return False, "No se encontró el archivo PPTX original para modificar."

        # 4. Determinar la ruta de la carpeta "Descargas" del usuario (independiente del SO)
        ruta_descargas = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        # 5. Armar el nombre del archivo de salida
        nombre_base = os.path.splitext(os.path.basename(ruta_pptx_original))[0]
        ruta_destino = os.path.join(ruta_descargas, f"{nombre_base}_Optimizada_IA.pptx")

        # Evitar sobreescribir si el usuario descarga el archivo varias veces
        contador = 1
        while os.path.exists(ruta_destino):
            ruta_destino = os.path.join(ruta_descargas, f"{nombre_base}_Optimizada_IA_{contador}.pptx")
            contador += 1

        # 6. Llamar al cerebro (Capa Lógica) para aplicar la cirugía y guardarlo en Descargas
        exito_mod, msj_mod = aplicar_mejoras_pptx(ruta_pptx_original, ruta_destino, datos_analisis)
        if not exito_mod:
            return False, msj_mod

        return True, f"¡Éxito! La presentación se guardó en tus Descargas:\n\n{ruta_destino}"

    except Exception as e:
        return False, f"Error en la exportación de mejoras: {str(e)}"