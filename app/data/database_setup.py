import sqlite3
import os

def crear_base_de_datos():
    # Ruta de almacenamiento
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "db", "ai_analyzer.db"))
    
    # Crear carpetas si no existen
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Activar llaves foráneas en SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # --- TABLAS DE LA ESTRUCTURA ACADÉMICA ---
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Unidad_de_Aprendizaje (
            id_unidad_aprendizaje INTEGER PRIMARY KEY AUTOINCREMENT,
            unidad_aprendizaje VARCHAR(50),
            activa BOOLEAN
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Unidad (
            id_unidad_tematica INTEGER PRIMARY KEY AUTOINCREMENT,
            id_unidad_aprendizaje INTEGER,
            nombre_unidad_tematica VARCHAR(50),
            numero_unidad INT,
            FOREIGN KEY (id_unidad_aprendizaje) REFERENCES Unidad_de_Aprendizaje(id_unidad_aprendizaje)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Temas (
            id_tema INTEGER PRIMARY KEY AUTOINCREMENT,
            id_unidad_tematica INTEGER,
            nombre_tema VARCHAR(50),
            numero_tema INT,
            FOREIGN KEY (id_unidad_tematica) REFERENCES Unidad(id_unidad_tematica)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Subtema (
            id_subtema INTEGER PRIMARY KEY AUTOINCREMENT,
            id_tema INTEGER,
            nombre_subtema VARCHAR(50),
            numero_subtema INT,
            embedding BLOB, -- SQLite usa BLOB para arreglos de floats/datos binarios
            FOREIGN KEY (id_tema) REFERENCES Temas(id_tema)
        )
    ''')

    # --- TABLAS DE PRESENTACIONES Y ANÁLISIS ---

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Presentacion (
            id_presentacion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_unidad_aprendizaje INTEGER,
            presentacion VARCHAR(50),
            FOREIGN KEY (id_unidad_aprendizaje) REFERENCES Unidad_de_Aprendizaje(id_unidad_aprendizaje)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Presentacion_Subtema (
            id_presentacion INTEGER,
            id_subtema INTEGER,
            PRIMARY KEY (id_presentacion, id_subtema),
            FOREIGN KEY (id_presentacion) REFERENCES Presentacion(id_presentacion),
            FOREIGN KEY (id_subtema) REFERENCES Subtema(id_subtema)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Historial_de_Versiones (
            id_version INTEGER PRIMARY KEY AUTOINCREMENT,
            id_presentacion INTEGER,
            numero_version INT,
            analisis BOOLEAN,
            fecha_carga DATE,
            tiempo_estimado TIME,
            total_diapositivas INT,
            hash VARCHAR(300),
            calificacion_presentacion FLOAT,
            temas_unidad_aprendizaje INT,
            recomendacion_presentacion TEXT,
            FOREIGN KEY (id_presentacion) REFERENCES Presentacion(id_presentacion)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Analisis (
            id_version INTEGER,
            numero_diapositiva INT,
            resultado TEXT,
            PRIMARY KEY (id_version, numero_diapositiva),
            FOREIGN KEY (id_version) REFERENCES Historial_de_Versiones(id_version)
        )
    ''')

    conn.commit()
    conn.close()
    return db_path

if __name__ == "__main__":
    path = crear_base_de_datos()
    print(f"✅ Base de Datos creada según el diagrama en: {path}")