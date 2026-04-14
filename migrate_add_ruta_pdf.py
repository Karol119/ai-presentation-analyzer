# migrate_add_ruta_pdf.py
# Ejecutar UNA sola vez desde la raíz del proyecto:
#   python migrate_add_ruta_pdf.py

import sqlite3
import os

def obtener_ruta_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(base_dir, "storage", "db", "ai_analyzer.db"))

def migrar():
    ruta = obtener_ruta_db()
    print(f"Conectando a: {ruta}")

    conn = sqlite3.connect(ruta)
    conn.execute("PRAGMA foreign_keys = OFF;")

    try:
        cursor = conn.cursor()

        # Verificar si la columna ya existe para evitar error en segunda ejecución
        cursor.execute("PRAGMA table_info(Historial_de_Versiones)")
        columnas = [col[1] for col in cursor.fetchall()]

        if "ruta_pdf" in columnas:
            print("⚠️  La columna 'ruta_pdf' ya existe. No se realizaron cambios.")
            return

        cursor.execute("""
            ALTER TABLE Historial_de_Versiones
            ADD COLUMN ruta_pdf TEXT
        """)

        conn.commit()
        print("✅ Columna 'ruta_pdf' agregada a Historial_de_Versiones.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error durante la migración: {e}")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.close()

if __name__ == "__main__":
    migrar()