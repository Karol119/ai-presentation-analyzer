# app/data/persistence.py
import sqlite3
import uuid
import os
import shutil
from datetime import datetime

# Asumo que tienes una función para conectar, si no, ajusta la ruta a tu generador
def conectar_db():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(base_dir, "storage", "db", "ai_analyzer.db")
    return sqlite3.connect(db_path)

def registrar_presentacion(ruta_origen, hash_unico, num_diapositivas, id_materia):
    """
    Guarda el archivo PPTX en el sistema de archivos y registra la metadata 
    en las tablas Presentacion e Historial_de_Versiones.
    """
    conn = conectar_db()
    cursor = conn.cursor()
    
    try:
        # 1. Obtener el nombre de la materia (Para crear la carpeta)
        cursor.execute("SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje WHERE id_unidad_aprendizaje = ?", (id_materia,))
        resultado = cursor.fetchone()
        if not resultado:
            return False, "Error: La materia no existe en la base de datos."
        
        nombre_materia = resultado[0]
        nombre_archivo = os.path.basename(ruta_origen)

        # 2. Manejo del Sistema de Archivos
        # Ruta dinámica a la raíz del proyecto -> storage/presentaciones/Nombre_Materia/
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        carpeta_destino = os.path.join(base_dir, "storage", "presentaciones", nombre_materia)
        
        # Crea la carpeta de la materia si es la primera vez que se sube un archivo
        os.makedirs(carpeta_destino, exist_ok=True)
        ruta_destino = os.path.join(carpeta_destino, nombre_archivo)
        
        # Copiamos el archivo físicamente
        shutil.copy2(ruta_origen, ruta_destino)

        # 3. Guardar en tabla: Presentacion
        id_presentacion = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Presentacion (id_presentacion, id_unidad_aprendizaje, presentacion)
            VALUES (?, ?, ?)
        """, (id_presentacion, id_materia, nombre_archivo))

        # 4. Guardar en tabla: Historial_de_Versiones
        id_version = str(uuid.uuid4())
        fecha_actual = datetime.now().strftime("%Y-%m-%d") # Formato DATE estándar
        
        # Los campos booleanos y valores por defecto (como analisis=0, calificacion=0.0) 
        # se llenan automáticamente por la definición de tu BD, aquí solo pasamos lo obligatorio
        cursor.execute("""
            INSERT INTO Historial_de_Versiones 
            (id_version, id_presentacion, numero_version, fecha_carga, total_diapositivas, hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (id_version, id_presentacion, 1, fecha_actual, num_diapositivas, hash_unico))

        # Confirmar la transacción completa
        conn.commit()
        return True, id_presentacion

    except Exception as e:
        # Si falla algo (ej. el archivo estaba abierto y no se pudo copiar), revertimos la BD
        conn.rollback()
        return False, f"Error interno: {str(e)}"
    finally:
        conn.close()