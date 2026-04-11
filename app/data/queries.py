# app/data/queries.py
from app.data.database_manager import conectar_db

def existe_hash_en_db(hash_archivo):
    """Verifica si el hash de una presentación ya existe en la base de datos."""
    conn = conectar_db()
    if not conn: return False
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM Historial_de_Versiones WHERE hash = ?", (hash_archivo,))
    existe = cursor.fetchone() is not None
    
    conn.close()
    return existe

def obtener_todas_las_materias():
    """Devuelve las materias que ya están en el panel (activa = 1)."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE activa = 1")
    materias = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return materias

def obtener_materias_disponibles():
    """Devuelve las materias con activa = 0 para el modal de agregar."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE activa = 0")
    materias = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return materias

def actualizar_estado_materia(nombre_materia, estado_activo):
    """Cambia el bit de activa en la BD (1 o 0)."""
    conn = conectar_db()
    if not conn: return False
    try:
        cursor = conn.cursor()
        val = 1 if estado_activo else 0
        cursor.execute(
            "UPDATE Unidad_de_Aprendizaje SET activa = ? WHERE unidad_aprendizaje = ?",
            (val, nombre_materia)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error BD: {e}")
        return False
    finally:
        conn.close()

def obtener_id_materia_por_nombre(nombre):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE unidad_aprendizaje = ?", (nombre,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

# --- NUEVAS FUNCIONES PARA BORRADO EN CASCADA ---

def obtener_rutas_archivos_materia(id_materia):
    """
    Recupera todas las rutas físicas (PPTX y Miniaturas) asociadas 
    a una materia para poder eliminarlas del disco.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
        SELECT hv.ruta, hv.ruta_miniatura
        FROM Presentacion p
        JOIN Historial_de_Versiones hv ON p.id_presentacion = hv.id_presentacion
        WHERE p.id_unidad_aprendizaje = ?
    """
    cursor.execute(query, (id_materia,))
    rutas = cursor.fetchall()
    conn.close()
    return rutas # Retorna [(ruta_pptx, ruta_thumb), ...]

def eliminar_datos_materia_cascada(id_materia):
    """
    Elimina los registros de presentaciones y versiones de la BD 
    antes de desactivar la materia.
    """
    conn = conectar_db()
    if not conn: return False
    try:
        cursor = conn.cursor()
        # 1. Eliminar versiones (dependen de presentación)
        cursor.execute("""
            DELETE FROM Historial_de_Versiones 
            WHERE id_presentacion IN (SELECT id_presentacion FROM Presentacion WHERE id_unidad_aprendizaje = ?)
        """, (id_materia,))
        
        # 2. Eliminar presentaciones
        cursor.execute("DELETE FROM Presentacion WHERE id_unidad_aprendizaje = ?", (id_materia,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error en borrado cascada BD: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ------------------------------------------------

def obtener_temario_materia(nombre_materia):
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
        SELECT u.numero_unidad, u.nombre_unidad_tematica, t.numero_tema, t.nombre_tema, s.numero_subtema, s.nombre_subtema
        FROM Unidad_de_Aprendizaje ua
        JOIN Unidad u ON ua.id_unidad_aprendizaje = u.id_unidad_aprendizaje
        LEFT JOIN Temas t ON u.id_unidad_tematica = t.id_unidad_tematica
        LEFT JOIN Subtema s ON t.id_tema = s.id_tema
        WHERE ua.unidad_aprendizaje = ?
        ORDER BY u.numero_unidad, t.numero_tema, s.numero_subtema;
    """
    cursor.execute(query, (nombre_materia,))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return []
    
    temario = []
    for row in rows:
        num_u, nom_u, num_t, nom_t, num_s, nom_s = row
        str_u = f"Unidad Temática {num_u}. {nom_u}"
        str_t = f"{num_u}.{num_t} {nom_t}" if nom_t else None
        str_s = f"{num_u}.{num_t}.{num_s} {nom_s}" if nom_s else None

        if not temario or temario[-1]["unidad"] != str_u:
            temario.append({"unidad": str_u, "temas": []})
        
        if str_t:
            if not temario[-1]["temas"] or temario[-1]["temas"][-1]["tema"] != str_t:
                temario[-1]["temas"].append({"tema": str_t, "subtemas": []})
            if str_s:
                temario[-1]["temas"][-1]["subtemas"].append(str_s)
    return temario

def obtener_presentaciones_por_materia(id_materia):
    """
    Recupera el nombre, ruta PPTX, ruta miniatura y estado de análisis.
    Retorna: [(nombre, ruta_pptx, ruta_miniatura, ya_analizada), ...]
    donde ya_analizada es 1 si el campo analisis no es NULL, 0 si lo es.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
        SELECT p.presentacion, hv.ruta, hv.ruta_miniatura, hv.analisis
        FROM Presentacion p
        JOIN Historial_de_Versiones hv ON p.id_presentacion = hv.id_presentacion
        WHERE p.id_unidad_aprendizaje = ? AND hv.numero_version = 1
    """
    cursor.execute(query, (id_materia,))
    resultados = cursor.fetchall()
    conn.close()
    return resultados