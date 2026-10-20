# app/core/controller/presentation_controller.py
import json
import os
import tempfile
from app.core.logic.file_validator import validar_tamano_archivo, validar_ruta_destino
from app.core.logic.hash_generator import generar_hash_archivo
from app.core.logic.text_extractor import validar_pptx_legible, contar_diapositivas
from app.core.logic.pptx_repairer import reparar_pptx
import tempfile
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

        # 1.5 Valida que el NOMBRE quepa en las rutas internas que se generarán
        #     (storage + sufijos '_thumb.png'/'.pdf'/'_analysis.json'). Windows
        #     falla si la ruta completa pasa de 260 caracteres: mejor rechazar
        #     aquí con un mensaje claro que crashear a mitad del proceso.
        nombre_materia_ruta = obtener_nombre_materia_controlador(id_materia)
        if nombre_materia_ruta:
            es_valida_ruta, mensaje_ruta = validar_ruta_destino(ruta_pptx, nombre_materia_ruta)
            if not es_valida_ruta:
                return False, mensaje_ruta

        # 2. VALIDACIÓN ROBUSTA: intenta abrir el archivo y recorrer TODO su
        #    contenido (títulos, diapositivas, shapes, texto e imágenes)
        #    exactamente como lo hará el análisis. Así un archivo con
        #    problemas se atrapa aquí y NUNCA en plena sesión de análisis.
        legible, estado_lectura, num_diapositivas = validar_pptx_legible(ruta_pptx)

        ruta_para_registro = ruta_pptx
        detalle_reparacion = None

        if not legible:
            if estado_lectura == "vacio":
                return False, "El archivo no contiene diapositivas."
            if estado_lectura == "corrupto":
                return False, ("Archivo dañado: no se pudo abrir el archivo "
                               "(puede estar corrupto o incompleto).")

            # estado "danado": el archivo SÍ se abre, pero tiene contenido
            # ilegible. Se intenta la REPARACIÓN AUTOMÁTICA (como PowerPoint):
            # se conserva lo legible y se quita lo dañado, guardando un nuevo
            # archivo. Si tras reparar todo es legible, se registra ÉSTE.
            nombre_original = os.path.basename(ruta_pptx)
            os.makedirs(tempfile.gettempdir(), exist_ok=True)
            ruta_reparada = os.path.join(
                tempfile.gettempdir(),
                f"reparado_{os.getpid()}_{nombre_original}"
            )
            detalle_reparacion = reparar_pptx(ruta_pptx, ruta_reparada)

            if not detalle_reparacion["exito"]:
                return False, "Archivo dañado: no se pudo preparar una versión legible."

            legible_rep, estado_rep, num_rep = validar_pptx_legible(ruta_reparada)
            if not legible_rep:
                if estado_rep == "vacio":
                    return False, "Archivo dañado: la reparación dejaría el archivo sin diapositivas legibles."
                return False, "Archivo dañado: contiene elementos internos que no se pudieron leer."

            ruta_para_registro = ruta_reparada
            num_diapositivas = num_rep

        # 3. Hash único del archivo que FINALMENTE se registrará (reparado si aplicó)
        hash_unico = generar_hash_archivo(ruta_para_registro)

        # 4. Verifica existencia (evita duplicados)
        if existe_hash_en_db(hash_unico):
            return False, "Esta presentación ya ha sido procesada anteriormente."

        # 5. ALMACENAR EN BASE DE DATOS Y STORAGE (copy2: el temporal ya no
        #    se necesita una vez copiado el archivo a storage)
        exito_registro, id_pres = registrar_presentacion(
            ruta_para_registro, 
            hash_unico, 
            num_diapositivas, 
            id_materia
        )

        if exito_registro:
            # Limpieza del temporal reparado (ya está copiado en storage)
            if ruta_para_registro != ruta_pptx:
                try:
                    os.remove(ruta_para_registro)
                except OSError:
                    pass

            if detalle_reparacion:
                d = detalle_reparacion
                return True, (f"Registrado con éxito (reparado automáticamente). "
                              f"REPARADO::{d['diapositivas_eliminadas']}"
                              f"::{d['elementos_eliminados']}")
            return True, "Registrado con éxito."
        else:
            return False, f"Error al persistir los datos: {id_pres}"

    except Exception as e:
        return False, f"Error en el flujo: {str(e)}"

def orquestar_eliminacion_presentacion(nombre_presentacion, id_materia):
    """
    Actúa como puente entre la UI y la persistencia para eliminar 
    física y lógicamente una presentación.
    """
    return eliminar_presentacion_completa(nombre_presentacion, id_materia)

def orquestar_ocultar_presentacion(nombre_presentacion, id_materia):
    """Oculta una presentación (borrado lógico) conservando todos sus datos."""
    from app.data.persistence import actualizar_visibilidad_presentacion
    return actualizar_visibilidad_presentacion(nombre_presentacion, id_materia, False)

def orquestar_mostrar_presentacion(nombre_presentacion, id_materia):
    """Vuelve a mostrar una presentación oculta."""
    from app.data.persistence import actualizar_visibilidad_presentacion
    return actualizar_visibilidad_presentacion(nombre_presentacion, id_materia, True)

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
        
        # 1.5 Valida que el NOMBRE quepa en las rutas internas (las nuevas
        #     versiones añaden sufijo '_v2' al archivo en storage).
        nombre_materia_ruta = obtener_nombre_materia_controlador(id_materia)
        if nombre_materia_ruta:
            es_valida_ruta, mensaje_ruta = validar_ruta_destino(
                ruta_pptx, nombre_materia_ruta, longitud_extra=4
            )
            if not es_valida_ruta:
                return False, mensaje_ruta

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
    Delega la exportación al método genérico que construye la ruta en Documentos.
    (Utilizado por la vista de Análisis, siempre usa la versión más reciente).
    """
    id_version = obtener_id_version_actual(nombre_presentacion, id_materia)
    _, version_actual = obtener_id_y_version_presentacion(nombre_presentacion, id_materia)
    
    return orquestar_exportacion_historial(id_version, nombre_presentacion, id_materia, version_actual, ruta_pdf)


def orquestar_exportacion_historial(id_version, nombre_presentacion, id_materia, version_num, ruta_pdf):
    """
    Exporta una versión ESPECÍFICA a la carpeta de Documentos, 
    creando la estructura por materia y validando si ya existe.
    """
    try:
        # 1. Recuperar el análisis exacto de esta versión
        json_raw = obtener_analisis_desde_db(id_version)
        if not json_raw:
            return False, "No hay análisis previo para aplicar mejoras a esta versión."
        
        datos_analisis = json.loads(json_raw)

        # 2. Determinar la ruta base de Documentos (independiente del SO)
        ruta_documentos = os.path.join(os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer')
        nombre_materia = obtener_nombre_materia_controlador(id_materia)
        
        # Crear estructura: Documentos/AI Presentation Analyzer/Nombre_Materia/
        ruta_carpeta_materia = os.path.join(ruta_documentos, nombre_materia)
        os.makedirs(ruta_carpeta_materia, exist_ok=True)
        
        # 3. Armar el nombre del archivo de salida
        nombre_base = os.path.splitext(nombre_presentacion)[0]
        nombre_archivo_destino = f"{nombre_base}_v{version_num}.pptx"
        ruta_destino = os.path.join(ruta_carpeta_materia, nombre_archivo_destino)

        # 4. Validar si ya existe (Evitar trabajo doble)
        if os.path.exists(ruta_destino):
            return True, "La presentación ya había sido generada."

        # 5. Obtener PPTX original de esta versión
        ruta_pptx_original = ruta_pdf.replace(".pdf", ".pptx")
        if not os.path.exists(ruta_pptx_original):
            return False, "No se encontró el archivo PPTX original para modificar."

        # 6. Llamar al cerebro (Capa Lógica) para aplicar la cirugía
        exito_mod, msj_mod = aplicar_mejoras_pptx(ruta_pptx_original, ruta_destino, datos_analisis)
        if not exito_mod:
            return False, msj_mod

        return True, "¡Presentación generada con éxito!"

    except Exception as e:
        return False, f"Error en la exportación: {str(e)}"


def ruta_archivo_exportado(nombre_presentacion, id_materia, version_num):
    """Ruta física del PPTX optimizado para una versión, exista o no."""
    ruta_documentos = os.path.join(os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer')
    nombre_materia = obtener_nombre_materia_controlador(id_materia)
    nombre_base = os.path.splitext(nombre_presentacion)[0]
    return os.path.join(ruta_documentos, nombre_materia, f"{nombre_base}_v{version_num}.pptx")


def abrir_archivo(ruta):
    """Abre un archivo con la aplicación predeterminada del sistema."""
    try:
        if os.name == 'nt':
            os.startfile(ruta)
        else:
            import subprocess
            subprocess.Popen(['xdg-open', ruta])
    except Exception as e:
        print(f"No se pudo abrir el archivo: {e}")


def _necesita_mejoras_segun_datos(datos_analisis) -> bool:
    """
    Regla pura (compartida): una versión necesita mejoras si alguna
    diapositiva de su análisis está marcada con 'requiere_reestructuracion'
    o trae sugerencias de reestructuración ('reestructuracion.diapositivas_generadas').
    """
    if not datos_analisis:
        return False
    for s in datos_analisis.get("slides", []):
        if s.get("requiere_reestructuracion"):
            return True
        if (s.get("reestructuracion") or {}).get("diapositivas_generadas"):
            return True
    return False


def version_necesita_mejoras(id_version) -> bool:
    """
    Indica si una versión del historial tiene mejoras pendientes, leyendo su
    análisis guardado en la BD.

    Es la MISMA regla que usa la vista de Análisis para bloquear la
    generación («ya está en un nivel óptimo»), centralizada aquí para que
    el historial la comparta. Sin análisis o sin nada pendiente -> False.
    """
    json_raw = obtener_analisis_desde_db(id_version)
    if not json_raw:
        return False
    try:
        return _necesita_mejoras_segun_datos(json.loads(json_raw))
    except Exception:
        return False


def orquestar_abrir_o_generar(id_version, nombre_presentacion, id_materia, version_num, ruta_pdf):
    """
    Comportamiento unificado con la vista de Análisis:
    - Si la versión ya está en un nivel óptimo (sin mejoras pendientes), NO
      se genera ni se abre el PPTX con cambios: la regla es absoluta,
      también si el archivo ya existía de una descarga previa.
    - Si necesita mejoras: lo abre si ya existe; si no, lo genera y abre.
    """
    if not version_necesita_mejoras(id_version):
        return False, (
            "Esta presentación ya está en un nivel óptimo. "
            "No requiere reestructuración, por lo que no hay cambios que generar."
        )

    ruta_destino = ruta_archivo_exportado(nombre_presentacion, id_materia, version_num)
    if os.path.exists(ruta_destino):
        abrir_archivo(ruta_destino)
        return True, "Abriendo la presentación generada..."

    exito, mensaje = orquestar_exportacion_historial(
        id_version, nombre_presentacion, id_materia, version_num, ruta_pdf
    )
    if exito:
        abrir_archivo(ruta_destino)
        return True, "¡Presentación generada! Se abrirá ahora."
    return exito, mensaje