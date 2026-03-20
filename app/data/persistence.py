# app/data/persistence.py
import sqlite3
import uuid
import os
import shutil
from datetime import datetime
from app.data.database_manager import conectar_db

def registrar_presentacion(ruta_origen, hash_unico, num_diapositivas, id_materia):
    """
    Guarda el archivo PPTX en storage/presentaciones/Nombre_Materia/ 
    y registra la metadata (incluyendo la ruta) en la BD.
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
        # Carpeta final: storage/presentaciones/Nombre_Materia
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        
        # Copiamos el archivo físicamente al storage
        shutil.copy2(ruta_origen, ruta_destino)

        # 3. Guardar en tabla: Presentacion
        id_presentacion = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Presentacion (id_presentacion, id_unidad_aprendizaje, presentacion)
            VALUES (?, ?, ?)
        """, (id_presentacion, id_materia, nombre_archivo))

        # 4. Guardar en tabla: Historial_de_Versiones (Incluyendo el campo 'ruta')
        id_version = str(uuid.uuid4())
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        # IMPORTANTE: Se añade 'ruta' a la consulta SQL
        cursor.execute("""
            INSERT INTO Historial_de_Versiones 
            (id_version, id_presentacion, numero_version, fecha_carga, total_diapositivas, hash, ruta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, 1, fecha_actual, num_diapositivas, hash_unico, ruta_destino))

        conn.commit()
        return True, id_presentacion

    except Exception as e:
        conn.rollback()
        return False, f"Error interno: {str(e)}"
    finally:
        conn.close()