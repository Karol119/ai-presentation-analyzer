import sqlite3
import os

def mostrar_esquema_sqlite():
    # Ruta exacta de tu base de datos
    db_path = r"C:\Users\Aldai\OneDrive\Documentos\CODIGOS\TT\ai-presentation-analyzer\storage\DB\ai_analyzer.db"

    # Verificar si el archivo existe
    if not os.path.exists(db_path):
        print(f"[ERROR] No se encontró el archivo de la base de datos en:\n{db_path}")
        return

    try:
        # 1. Establecer conexión
        conexion = sqlite3.connect(db_path)
        cursor = conexion.cursor()

        # 2. Obtener la lista de todas las tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tablas = cursor.fetchall()

        # 3. Mostrar las tablas y sus columnas con tipos de datos
        if tablas:
            print(f"\n=== ESQUEMA DE LA BASE DE DATOS: '{os.path.basename(db_path)}' ===\n")
            
            for tabla in tablas:
                nombre_tabla = tabla[0]
                
                # Ignorar las tablas internas que SQLite crea automáticamente
                if nombre_tabla.startswith("sqlite_"):
                    continue
                    
                print(f"📦 Tabla: {nombre_tabla}")
                
                # PRAGMA table_info devuelve: (cid, name, type, notnull, dflt_value, pk)
                cursor.execute(f"PRAGMA table_info('{nombre_tabla}');")
                columnas = cursor.fetchall()
                
                for col in columnas:
                    col_nombre = col[1]
                    col_tipo = col[2]
                    es_pk = " (PRIMARY KEY)" if col[5] == 1 else ""
                    
                    print(f"   ├─ {col_nombre}: {col_tipo}{es_pk}")
                
                print("-" * 40)
        else:
            print("[AVISO] La base de datos no tiene ninguna tabla creada todavía.")

    except sqlite3.Error as error:
        print(f"[ERROR SQLITE] Ocurrió un problema al leer la base de datos: {error}")
    
    finally:
        # 4. Cerrar la conexión
        if 'conexion' in locals():
            conexion.close()

if __name__ == "__main__":
    mostrar_esquema_sqlite()