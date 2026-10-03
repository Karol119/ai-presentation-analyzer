# app/core/controller/subject_controller.py
import os
import shutil
from app.data.queries import (
    obtener_todas_las_materias,
    obtener_materias_disponibles,
    obtener_id_materia,
    obtener_rutas_archivos_materia,
    obtener_presentaciones_por_materia,
    obtener_temario_materia,
    obtener_nombre_materia_por_id
)

# Persistencia: Solo funciones que alteran el estado (Escritura/Borrado)
from app.data.persistence import (
    actualizar_estado_materia,
    eliminar_datos_materia_cascada 
)

def obtener_catalogo_materias_activas():
    """Orquesta la carga de materias habilitadas en el panel principal."""
    return obtener_todas_las_materias()

def obtener_materias_para_agregar():
    """Recupera el catálogo de materias disponibles para activar."""
    return obtener_materias_disponibles()

def activar_materia(nombre_materia):
    """Lógica para habilitar una materia en la base de datos."""
    return actualizar_estado_materia(nombre_materia, True)

def desactivar_materia(nombre_materia):
    """Lógica para ocultar una materia del panel (borrado lógico)."""
    return actualizar_estado_materia(nombre_materia, False)

def obtener_id_materia_controlador(nombre_materia):
    """Obtiene el UUID único de la materia por su nombre."""
    return obtener_id_materia(nombre_materia)

def obtener_archivos_materia(id_materia):
    """
    Recupera las presentaciones vinculadas a la materia.
    Retorna: [(nombre, ruta_pptx, ruta_miniatura, analisis, ruta_pdf), ...]
    """
    return obtener_presentaciones_por_materia(id_materia)

def obtener_temario_completo(nombre_materia):
    """
    Orquesta la obtención del árbol de temas (Unidad -> Tema -> Subtema).
    Esta es la función que faltaba y causaba el ImportError.
    """
    return obtener_temario_materia(nombre_materia)

def orquestar_desactivacion_materia(nombre_materia):
    """
    Coordina la eliminación física de archivos y la limpieza 
    lógica/física en la base de datos.
    """
    id_materia = obtener_id_materia(nombre_materia)
    if not id_materia:
        return False, "No se encontró la materia en el sistema."

    try:
        # 1. ACCIÓN FÍSICA: Obtener rutas desde queries y borrar archivos del disco
        archivos = obtener_rutas_archivos_materia(id_materia)
        carpetas_vistas = set()
        for ruta_pptx, ruta_thumb, ruta_pdf in archivos:
            for ruta in (ruta_pptx, ruta_thumb, ruta_pdf):
                if ruta and os.path.exists(ruta):
                    os.remove(ruta)
                if ruta:
                    carpetas_vistas.add(os.path.dirname(ruta))
            # JSON de análisis junto al pdf/pptx
            for base in (ruta_pdf, ruta_pptx):
                if base:
                    ruta_json = os.path.splitext(base)[0] + "_analysis.json"
                    if os.path.exists(ruta_json):
                        os.remove(ruta_json)

        # Carpeta storage de la materia (si quedó vacía) y carpeta de mejoras en Documentos
        for carpeta in carpetas_vistas:
            try:
                if os.path.isdir(carpeta) and not os.listdir(carpeta):
                    os.rmdir(carpeta)
            except Exception:
                pass
        try:
            ruta_docs = os.path.join(
                os.path.expanduser('~'), 'Documents', 'AI Presentation Analyzer', nombre_materia
            )
            if os.path.isdir(ruta_docs):
                shutil.rmtree(ruta_docs, ignore_errors=True)
        except Exception:
            pass

        # 2. ACCIÓN EN BD: Limpiar registros (Analisis, Versiones, Presentaciones)
        if not eliminar_datos_materia_cascada(id_materia):
            return False, "Error al limpiar los registros de las presentaciones."

        # 3. ACCIÓN EN BD: Desactivar la materia (activa = 0)
        if actualizar_estado_materia(nombre_materia, False):
            return True, f"Materia '{nombre_materia}' y su contenido eliminados con éxito."
        
        return False, "No se pudo actualizar el estado de la materia."

    except Exception as e:
        return False, f"Error crítico en la orquestación: {str(e)}"

def obtener_nombre_materia_controlador(id_materia):
    """Obtiene el nombre de una materia mediante su ID."""
    return obtener_nombre_materia_por_id(id_materia)