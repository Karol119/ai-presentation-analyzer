import sqlite3
import os

def ver_esquema_bd(ruta_db):
    if not os.path.exists(ruta_db):
        print(f"Error: No se encontró el archivo en la ruta '{ruta_db}'.")
        return

    try:
        # 1. Conectar a la base de datos
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()

        # 2. Consultar las tablas existentes (excluyendo tablas internas de sqlite)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tablas = cursor.fetchall()

        if not tablas:
            print("No se encontraron tablas en la base de datos.")
            return

        print(f"=== Base de datos: {ruta_db} ===")
        print(f"Total de tablas: {len(tablas)}\n")

        # 3. Iterar por cada tabla para ver sus columnas y tipos de datos
        for tabla in tablas:
            nombre_tabla = tabla[0]
            print(f"Tabla: {nombre_tabla}")
            print("-" * 55)
            print(f"{'Nombre de la Columna':<25} | {'Tipo de Dato':<15} | {'Llave Primaria'}")
            print("-" * 55)
            
            # PRAGMA table_info devuelve: (cid, name, type, notnull, dflt_value, pk)
            cursor.execute(f"PRAGMA table_info('{nombre_tabla}');")
            columnas = cursor.fetchall()
            
            for col in columnas:
                col_nombre = col[1]
                col_tipo = col[2]
                es_pk = "Sí" if col[5] > 0 else ""
                
                print(f"{col_nombre:<25} | {col_tipo:<15} | {es_pk}")
            
            print("\n")

    except sqlite3.Error as e:
        print(f"Error en la base de datos SQLite: {e}")
    finally:
        if 'conexion' in locals():
            conexion.close()

if __name__ == "__main__":
    # De acuerdo a tu árbol, tienes la base de datos en dos lugares. 
    # Selecciona la que utilices activamente:
    
    # Opcion 1: Raíz del proyecto
    # ruta = "ai_analyzer.db"
    
    # Opcion 2: Carpeta de almacenamiento (recomendado según tu estructura)
    ruta = "storage/DB/ai_analyzer.db" 
    
    ver_esquema_bd(ruta)