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
    
    # Cambiamos INTEGER a TEXT para soportar UUIDs generados en Python
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Unidad_de_Aprendizaje (
            id_unidad_aprendizaje TEXT PRIMARY KEY, 
            unidad_aprendizaje TEXT NOT NULL UNIQUE,
            activa BOOLEAN NOT NULL DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Unidad (
            id_unidad_tematica TEXT PRIMARY KEY,
            id_unidad_aprendizaje TEXT NOT NULL,
            nombre_unidad_tematica TEXT NOT NULL,
            numero_unidad INTEGER NOT NULL,
            FOREIGN KEY (id_unidad_aprendizaje) REFERENCES Unidad_de_Aprendizaje(id_unidad_aprendizaje)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Temas (
            id_tema TEXT PRIMARY KEY,
            id_unidad_tematica TEXT NOT NULL,
            nombre_tema TEXT NOT NULL,
            numero_tema INTEGER NOT NULL,
            FOREIGN KEY (id_unidad_tematica) REFERENCES Unidad(id_unidad_tematica)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Subtema (
            id_subtema TEXT PRIMARY KEY,
            id_tema TEXT NOT NULL,
            nombre_subtema TEXT NOT NULL,
            numero_subtema INTEGER NOT NULL,
            embedding BLOB, -- Puede ser NULL hasta que la IA lo genere
            FOREIGN KEY (id_tema) REFERENCES Temas(id_tema)
        )
    ''')

    # --- TABLAS DE PRESENTACIONES Y ANÁLISIS ---

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Presentacion (
            id_presentacion TEXT PRIMARY KEY,
            id_unidad_aprendizaje TEXT NOT NULL,
            presentacion TEXT NOT NULL,
            FOREIGN KEY (id_unidad_aprendizaje) REFERENCES Unidad_de_Aprendizaje(id_unidad_aprendizaje)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Presentacion_Subtema (
            id_presentacion TEXT NOT NULL,
            id_subtema TEXT NOT NULL,
            PRIMARY KEY (id_presentacion, id_subtema),
            FOREIGN KEY (id_presentacion) REFERENCES Presentacion(id_presentacion),
            FOREIGN KEY (id_subtema) REFERENCES Subtema(id_subtema)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Historial_de_Versiones (
            id_version TEXT PRIMARY KEY,
            id_presentacion TEXT NOT NULL,
            numero_version INTEGER NOT NULL DEFAULT 1,
            analisis BOOLEAN NOT NULL DEFAULT 0,
            fecha_carga DATE NOT NULL DEFAULT CURRENT_DATE,
            tiempo_estimado TIME DEFAULT '00:00:00',
            total_diapositivas INTEGER NOT NULL,
            hash TEXT NOT NULL,
            calificacion_presentacion FLOAT DEFAULT 0.0,
            temas_unidad_aprendizaje INTEGER DEFAULT 0,
            recomendacion_presentacion TEXT DEFAULT 'Pendiente de análisis',
            FOREIGN KEY (id_presentacion) REFERENCES Presentacion(id_presentacion)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Analisis (
            id_version TEXT NOT NULL,
            numero_diapositiva INTEGER NOT NULL,
            resultado TEXT NOT NULL,
            PRIMARY KEY (id_version, numero_diapositiva),
            FOREIGN KEY (id_version) REFERENCES Historial_de_Versiones(id_version)
        )
    ''')

    conn.commit()
    conn.close()
    return db_path

if __name__ == "__main__":
    path = crear_base_de_datos()
    print(f"✅ Base de Datos robusta (UUID + No Nulos) creada en: {path}")