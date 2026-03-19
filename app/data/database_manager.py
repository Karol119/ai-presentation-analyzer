import sqlite3
import os

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
        return conn
    except sqlite3.Error as e:
        print(f"Error de conexión: {e}")
        return None