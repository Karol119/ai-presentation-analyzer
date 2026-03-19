import sqlite3
import os

def actualizar_base_de_datos():
    # Buscamos la base de datos en la misma ruta de tu script original
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "db", "ai_analyzer.db"))
    
    # Verificamos que el archivo realmente exista antes de intentar modificarlo
    if not os.path.exists(db_path):
        print(f"❌ No se encontró la base de datos en: {db_path}")
        print("Asegúrate de que la ruta sea correcta o de haber creado la base primero.")
        return

    try:
        # Nos conectamos a la base de datos existente
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # --- 1. ACTUALIZAR MATERIAS EXISTENTES ---
        cursor.execute("UPDATE Unidad_de_Aprendizaje SET activa = 0;")
        filas_actualizadas = cursor.rowcount
        print(f"✔️ Se actualizaron {filas_actualizadas} unidades de aprendizaje a estado inactivo (0).")

        # --- 2. AGREGAR COLUMNA RUTA ---
        # Usamos un bloque try-except específico por si ejecutas este script dos veces
        try:
            cursor.execute("ALTER TABLE Historial_de_Versiones ADD COLUMN ruta TEXT;")
            print("✔️ Se agregó la columna 'ruta' a Historial_de_Versiones exitosamente.")
        except sqlite3.OperationalError as e:
            # SQLite arroja este error si la columna ya existe
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠️ La columna 'ruta' ya existía en la base de datos. No se hicieron cambios en la estructura.")
            else:
                raise e # Si es otro error de base de datos, lo mostramos

        # Guardamos los cambios
        conn.commit()
        print("\n🚀 ¡Actualización de la base de datos completada con éxito!")

    except sqlite3.Error as e:
        print(f"❌ Ocurrió un error general con SQLite: {e}")
    finally:
        # Siempre es buena práctica cerrar la conexión
        if conn:
            conn.close()

if __name__ == "__main__":
    actualizar_base_de_datos()