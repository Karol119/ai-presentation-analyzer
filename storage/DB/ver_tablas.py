import sqlite3
import json
import os

def exportar_analisis(ruta_db):
    if not os.path.exists(ruta_db):
        print(f"Error: No se encontró la base de datos en '{ruta_db}'.")
        return

    try:
        conexion = sqlite3.connect(ruta_db)
        cursor = conexion.cursor()

        # 1. Obtener las presentaciones que tienen análisis en la base de datos
        query_presentaciones = """
            SELECT DISTINCT v.id_version, p.presentacion, v.numero_version
            FROM Historial_de_Versiones v
            JOIN Presentacion p ON v.id_presentacion = p.id_presentacion
            JOIN Analisis a ON v.id_version = a.id_version
            ORDER BY p.presentacion, v.numero_version
        """
        cursor.execute(query_presentaciones)
        opciones = cursor.fetchall()

        if not opciones:
            print("No hay análisis disponibles en la base de datos para exportar.")
            return

        # 2. Mostrar opciones al usuario
        print("\n--- Presentaciones con Análisis Disponibles ---")
        for i, (id_version, nombre, version) in enumerate(opciones, start=1):
            print(f"[{i}] {nombre} (Versión: {version}) - ID: {id_version}")
        
        # 3. Solicitar al usuario que elija una opción
        seleccion = input("\nIngresa el número de la presentación que deseas exportar (o 'q' para salir): ")
        
        if seleccion.lower() == 'q':
            return
            
        try:
            indice = int(seleccion) - 1
            if indice < 0 or indice >= len(opciones):
                print("Selección inválida.")
                return
            
            id_version_seleccionada = opciones[indice][0]
            nombre_presentacion = opciones[indice][1]
        except ValueError:
            print("Por favor, ingresa un número válido.")
            return

        # 4. Extraer los datos de la presentación seleccionada
        cursor.execute("""
            SELECT numero_diapositiva, resultado 
            FROM Analisis 
            WHERE id_version = ?
            ORDER BY numero_diapositiva
        """, (id_version_seleccionada,))
        
        registros = cursor.fetchall()
        
        # 5. Formatear los datos para el documento
        datos_exportar = {
            "presentacion": nombre_presentacion,
            "id_version": id_version_seleccionada,
            "diapositivas": []
        }

        for num_diapositiva, resultado in registros:
            datos_diapositiva = {
                "numero_diapositiva": num_diapositiva,
                "analisis": None
            }
            
            if resultado:
                try:
                    datos_diapositiva["analisis"] = json.loads(resultado)
                except json.JSONDecodeError:
                    datos_diapositiva["analisis"] = "Error: El texto en la base de datos no es un JSON válido."
                    datos_diapositiva["texto_original"] = resultado
            
            datos_exportar["diapositivas"].append(datos_diapositiva)

        # 6. Exportar a un archivo JSON
        nombre_archivo = f"analisis_{nombre_presentacion.replace(' ', '_')}.json"
        
        with open(nombre_archivo, 'w', encoding='utf-8') as archivo:
            json.dump(datos_exportar, archivo, indent=4, ensure_ascii=False)
            
        print(f"\n¡Exportación exitosa! El archivo se guardó como: {nombre_archivo}")

    except sqlite3.Error as e:
        print(f"Error en la base de datos SQLite: {e}")
    finally:
        if 'conexion' in locals():
            conexion.close()

if __name__ == "__main__":
    ruta = "storage/DB/ai_analyzer.db"
    exportar_analisis(ruta)