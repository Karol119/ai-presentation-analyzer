#app/data/database_manager.py

import sqlite3
import os

def _migrar_columna_visible(conn):
    """Agrega la columna 'visible' a Presentacion si no existe (modo ocultar)."""
    try:
        cols = [fila[1] for fila in conn.execute("PRAGMA table_info(Presentacion)")]
        if "visible" not in cols:
            conn.execute("ALTER TABLE Presentacion ADD COLUMN visible INTEGER NOT NULL DEFAULT 1")
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error en migración de columna 'visible': {e}")

def obtener_ruta_db():
    """Retorna la ruta absoluta de la base de datos."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "db", "ai_analyzer.db"))

def conectar_db():
    """Crea y configura una conexión limpia a SQLite."""
    try:
        ruta = obtener_ruta_db()
        conn = sqlite3.connect(ruta)
        # Activar llaves foráneas para que respete tu diagrama de BD
        conn.execute("PRAGMA foreign_keys = ON;")
        _migrar_columna_visible(conn)
        return conn
    except sqlite3.Error as e:
        print(f"Error de conexión: {e}")
        return None