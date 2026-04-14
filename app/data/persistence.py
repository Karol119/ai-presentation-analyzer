# app/data/persistence.py
import sqlite3
import uuid
import os
import shutil
from datetime import datetime
from app.data.database_manager import conectar_db
from app.core.logic.slide_processor import generar_miniatura, generar_pdf

def registrar_presentacion(ruta_origen, hash_unico, num_diapositivas, id_materia):
    """
    Guarda el archivo PPTX, genera su miniatura y registra ambas rutas en la BD.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener el nombre de la materia para la subcarpeta
        cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE id_unidad_aprendizaje = ?", (id_materia,))
        resultado = cursor.fetchone()
        if not resultado:
            return False, "Error: La materia no existe en la base de datos."
        
        nombre_materia = resultado[0]
        nombre_archivo = os.path.basename(ruta_origen)

        # 2. Manejo del Sistema de Archivos
        # Buscamos la raíz: prototipo/ai-presentation-analyzer/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        
        # Copiamos el archivo físicamente al storage
        shutil.copy2(ruta_origen, ruta_destino)

        # --- Generación de Miniatura ---
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        ruta_thumb = os.path.join(carpeta_destino, f"{nombre_sin_ext}_thumb.png")
        generar_miniatura(ruta_destino, ruta_thumb)

        # --- Generación de PDF (para visor y modo presentación) ---
        ruta_pdf = os.path.join(carpeta_destino, f"{nombre_sin_ext}.pdf")
        generar_pdf(ruta_destino, ruta_pdf)
        # -----------------------------------------------------------

        # 3. Guardar en tabla: Presentacion
        id_presentacion = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Presentacion (id_presentacion, id_unidad_aprendizaje, presentacion)
            VALUES (?, ?, ?)
        """, (id_presentacion, id_materia, nombre_archivo))

        # 4. Guardar en tabla: Historial_de_Versiones
        id_version = str(uuid.uuid4())
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        # Se incluye 'ruta' y la nueva columna 'ruta_miniatura'
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
    """
    Borra la presentación de la BD y sus archivos físicos asociados.
    """
    conn = conectar_db()
    if not conn: return False
    cursor = conn.cursor()
    
    try:
        # 1. Obtener las rutas de los archivos antes de borrar el registro
        query_rutas = """
            SELECT hv.ruta, hv.ruta_miniatura, hv.ruta_pdf
            FROM Historial_de_Versiones hv
            JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
            WHERE p.presentacion = ? AND p.id_unidad_aprendizaje = ?
        """
        cursor.execute(query_rutas, (nombre_presentacion, id_materia))
        archivos = cursor.fetchall()

        cursor.execute("""
            DELETE FROM Presentacion 
            WHERE presentacion = ? AND id_unidad_aprendizaje = ?
        """, (nombre_presentacion, id_materia))

        for ruta_pptx, ruta_thumb, ruta_pdf in archivos:
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