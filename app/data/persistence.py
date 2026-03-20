# app/data/persistence.py
import sqlite3
import uuid
import os
import shutil
from datetime import datetime
from app.data.database_manager import conectar_db
from app.core.logic.thumbnail_generator import generar_miniatura_aspose # Asegúrate de crear este archivo

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

        # --- NUEVO: Generación de Miniatura ---
        nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
        ruta_thumb = os.path.join(carpeta_destino, f"{nombre_sin_ext}_thumb.png")
        
        # Generamos la imagen de la primera diapositiva
        generar_miniatura_aspose(ruta_destino, ruta_thumb)
        # ---------------------------------------

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
            (id_version, id_presentacion, numero_version, fecha_carga, total_diapositivas, hash, ruta, ruta_miniatura)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, 1, fecha_actual, num_diapositivas, hash_unico, ruta_destino, ruta_thumb))

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
            SELECT hv.ruta, hv.ruta_miniatura 
            FROM Historial_de_Versiones hv
            JOIN Presentacion p ON hv.id_presentacion = p.id_presentacion
            WHERE p.presentacion = ? AND p.id_unidad_aprendizaje = ?
        """
        cursor.execute(query_rutas, (nombre_presentacion, id_materia))
        archivos = cursor.fetchall()

        # 2. Borrar de la base de datos
        # Al borrar de 'Presentacion', la FK con CASCADE borrará 'Historial_de_Versiones'
        cursor.execute("""
            DELETE FROM Presentacion 
            WHERE presentacion = ? AND id_unidad_aprendizaje = ?
        """, (nombre_presentacion, id_materia))
        
        # 3. Borrar archivos físicos del almacenamiento
        for ruta_pptx, ruta_thumb in archivos:
            if ruta_pptx and os.path.exists(ruta_pptx):
                os.remove(ruta_pptx)
            if ruta_thumb and os.path.exists(ruta_thumb):
                os.remove(ruta_thumb)

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar físicamente: {e}")
        return False
    finally:
        conn.close()