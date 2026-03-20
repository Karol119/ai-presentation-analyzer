# app/core/controller/subject_controller.py
from app.data.queries import (
    obtener_todas_las_materias,
    obtener_materias_disponibles,
    actualizar_estado_materia,
    obtener_id_materia_por_nombre,
    obtener_presentaciones_por_materia
)
from app.data.queries import obtener_temario_materia

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

def obtener_id_materia(nombre_materia):
    """Obtiene el UUID único de la materia por su nombre."""
    return obtener_id_materia_por_nombre(nombre_materia)

def obtener_archivos_materia(id_materia):
    """
    Recupera las presentaciones vinculadas a la materia.
    Retorna: [(nombre, ruta_pptx, ruta_miniatura), ...]
    """
    return obtener_presentaciones_por_materia(id_materia)

def obtener_temario_completo(nombre_materia):
    """Orquesta la obtención del árbol de temas (Unidad -> Tema -> Subtema)."""
    return obtener_temario_materia(nombre_materia)