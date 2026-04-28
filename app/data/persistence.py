# app/data/persistence.py
import sqlite3
import uuid
import json
import os
import shutil
from datetime import datetime
from app.data.database_manager import conectar_db
from app.core.logic.slide_processor import generar_miniatura, generar_pdf

def registrar_presentacion(ruta_origen, hash_unico, num_diapositivas, id_materia):
    """Guarda el archivo PPTX, genera miniatura/PDF y registra en BD."""
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE id_unidad_aprendizaje = ?", (id_materia,))
        resultado = cursor.fetchone()
        if not resultado:
            return False, "Error: La materia no existe en la base de datos."
        
        nombre_materia = resultado[0]
        nombre_archivo = os.path.basename(ruta_origen)

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        shutil.copy2(ruta_origen, ruta_destino)

        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        ruta_thumb = os.path.join(carpeta_destino, f"{nombre_sin_ext}_thumb.png")
        generar_miniatura(ruta_destino, ruta_thumb)

        ruta_pdf = os.path.join(carpeta_destino, f"{nombre_sin_ext}.pdf")
        generar_pdf(ruta_destino, ruta_pdf)

        id_presentacion = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Presentacion (id_presentacion, id_unidad_aprendizaje, presentacion)
            VALUES (?, ?, ?)
        """, (id_presentacion, id_materia, nombre_archivo))

        id_version = str(uuid.uuid4())
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO Historial_de_Versiones 
            (id_version, id_presentacion, numero_version, fecha_carga, total_diapositivas, hash, ruta, ruta_miniatura, ruta_pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, 1, fecha_actual, num_diapositivas, hash_unico, ruta_destino, ruta_thumb, ruta_pdf))

        conn.commit()
        return True, id_presentacion

    except Exception as e:
        conn.rollback()
        return False, f"Error interno: {str(e)}"
    finally:
        conn.close()

def eliminar_presentacion_completa(nombre_presentacion, id_materia):
    """Borra la presentación respetando la jerarquía de llaves foráneas."""
    conn = conectar_db()
    if not conn: return False
    cursor = conn.cursor()
    
    try:
        # 1. Obtener ID y rutas de archivos
        cursor.execute("""
            SELECT p.id_presentacion, hv.ruta, hv.ruta_miniatura, hv.ruta_pdf
            FROM Presentacion p
            JOIN Historial_de_Versiones hv ON p.id_presentacion = hv.id_presentacion
            WHERE p.presentacion = ? AND p.id_unidad_aprendizaje = ?
        """, (nombre_presentacion, id_materia))
        resultado = cursor.fetchone()
        if not resultado: return False
        
        id_pres, ruta_pptx, ruta_thumb, ruta_pdf = resultado

        # 2. BORRADO EN CASCADA MANUAL (Orden inverso de dependencia)
        # A. Borrar análisis vinculados a las versiones de esta presentación
        cursor.execute("""
            DELETE FROM Analisis 
            WHERE id_version IN (SELECT id_version FROM Historial_de_Versiones WHERE id_presentacion = ?)
        """, (id_pres,))

        # B. Borrar vinculación con subtemas
        cursor.execute("DELETE FROM Presentacion_Subtema WHERE id_presentacion = ?", (id_pres,))

        # C. Borrar historial de versiones
        cursor.execute("DELETE FROM Historial_de_Versiones WHERE id_presentacion = ?", (id_pres,))

        # D. Borrar la presentación (Padre)
        cursor.execute("DELETE FROM Presentacion WHERE id_presentacion = ?", (id_pres,))

        # 3. Borrado de archivos físicos
        for ruta in (ruta_pptx, ruta_thumb, ruta_pdf):
            if ruta and os.path.exists(ruta):
                os.remove(ruta)

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar físicamente: {e}")
        return False
    finally:
        conn.close()

def registrar_analisis_completo(id_version, json_string):
    """Persiste el bloque JSON completo del análisis."""
    conn = conectar_db()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO Analisis (id_version, numero_diapositiva, resultado)
            VALUES (?, ?, ?)
        """, (id_version, 0, json_string))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al persistir análisis: {e}")
        return False
    finally:
        conn.close()

def actualizar_estado_analisis(nombre_presentacion, id_materia, estado_analisis=1):
    """Actualiza el bit de control de análisis."""
    conn = conectar_db()
    if not conn: return False
    try:
        cursor = conn.cursor()
        query = """
            UPDATE Historial_de_Versiones 
            SET analisis = ? 
            WHERE id_presentacion = (
                SELECT id_presentacion FROM Presentacion 
                WHERE presentacion = ? AND id_unidad_aprendizaje = ?
            ) AND numero_version = 1
        """
        cursor.execute(query, (estado_analisis, nombre_presentacion, id_materia))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error actualizando estado de análisis: {e}")
        return False
    finally:
        conn.close()

def actualizar_estado_materia(nombre_materia, estado_activo):
    """Activa o desactiva una materia y limpia sus datos si se desactiva."""
    conn = conectar_db()
    if not conn: return False
    try:
        cursor = conn.cursor()
        val = 1 if estado_activo else 0
        
        # Si se va a desactivar, primero ejecutamos el borrado en cascada de sus hijos
        if val == 0:
            cursor.execute("SELECT id_unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE unidad_aprendizaje = ?", (nombre_materia,))
            id_m = cursor.fetchone()[0]
            
            # Borrar de Analisis -> Historial -> Presentacion
            cursor.execute("""
                DELETE FROM Analisis WHERE id_version IN (
                    SELECT hv.id_version FROM Historial_de_Versiones hv
                    JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
                    WHERE p.id_unidad_aprendizaje = ?)
            """, (id_m,))
            cursor.execute("DELETE FROM Historial_de_Versiones WHERE id_presentacion IN (SELECT id_presentacion FROM Presentacion WHERE id_unidad_aprendizaje = ?)", (id_m,))
            cursor.execute("DELETE FROM Presentacion WHERE id_unidad_aprendizaje = ?", (id_m,))

        cursor.execute("UPDATE Unidad_de_Aprendizaje SET activa = ? WHERE unidad_aprendizaje = ?", (val, nombre_materia))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error en actualización de materia: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()