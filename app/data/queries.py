# app/data/queries.py
from app.data.database_manager import conectar_db

def existe_hash_en_db(hash_archivo):
    """Verifica si el hash de una presentación ya existe (Lectura)."""
    conn = conectar_db()
    if not conn: return False
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM Historial_de_Versiones WHERE hash = ?", (hash_archivo,))
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def obtener_todas_las_materias():
    """Devuelve los nombres de las materias activas."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE activa = 1")
    materias = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return materias

def obtener_materias_disponibles():
    """Devuelve los nombres de las materias inactivas para el catálogo."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE activa = 0")
    materias = [fila[0] for fila in cursor.fetchall()]
    conn.close()
    return materias

def obtener_id_materia(nombre):
    """Obtiene el ID numérico de una materia por su nombre."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id_unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE unidad_aprendizaje = ?", (nombre,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def obtener_presentaciones_por_materia(id_materia):
    """Recupera la última versión de cada presentación de una materia."""
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
        SELECT p.presentacion, hv.ruta, hv.ruta_miniatura, hv.analisis, hv.ruta_pdf
        FROM Presentacion p
        JOIN Historial_de_Versiones hv ON p.id_presentacion = hv.id_presentacion
        WHERE p.id_unidad_aprendizaje = ? 
        AND hv.numero_version = (
            SELECT MAX(numero_version) 
            FROM Historial_de_Versiones 
            WHERE id_presentacion = p.id_presentacion
        )
    """
    cursor.execute(query, (id_materia,))
    resultados = cursor.fetchall()
    conn.close()
    return resultados

def obtener_id_version_actual(nombre_presentacion, id_materia):
    """Busca el UUID de la versión más reciente de una presentación."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hv.id_version 
        FROM Historial_de_Versiones hv
        JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
        WHERE p.presentacion = ? AND p.id_unidad_aprendizaje = ? 
        ORDER BY hv.numero_version DESC LIMIT 1
    """, (nombre_presentacion, id_materia))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def obtener_analisis_desde_db(id_version):
    """Recupera el JSON de análisis almacenado para una versión."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT resultado FROM Analisis WHERE id_version = ?", (id_version,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def obtener_rutas_archivos_materia(id_materia):
    """Lista todas las rutas físicas de los archivos de una materia para limpieza."""
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT hv.ruta, hv.ruta_miniatura, hv.ruta_pdf
        FROM Historial_de_Versiones hv
        JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
        WHERE p.id_unidad_aprendizaje = ?
    """, (id_materia,))
    rutas = cursor.fetchall()
    conn.close()
    return rutas

def obtener_temario_materia(nombre_materia):
    """Consulta el temario jerárquico (Unidad -> Tema -> Subtema) de una materia."""
    conn = conectar_db()
    cursor = conn.cursor()
    query = """
        SELECT u.numero_unidad, u.nombre_unidad_tematica, 
               t.numero_tema, t.nombre_tema, 
               s.numero_subtema, s.nombre_subtema
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

        # Agrupar por Unidad
        if not temario or temario[-1]["unidad"] != str_u:
            temario.append({"unidad": str_u, "temas": []})
        
        # Agrupar por Tema
        if str_t:
            temas_lista = temario[-1]["temas"]
            if not temas_lista or temas_lista[-1]["tema"] != str_t:
                temas_lista.append({"tema": str_t, "subtemas": []})
            
            # Agregar Subtema
            if str_s:
                temas_lista[-1]["subtemas"].append(str_s)
                
    return temario