import os
import shutil
import json

from pptx.presentation import Presentation

#implementar: Extraer fecha de carga
#Implentar: Contador de numero de diapositivas
#Impmentar: Almacenar HASH

def guardar_todo(ruta_origen, datos_json):
    """
    Esta función guarda tanto el archivo PPTX como el JSON de vectorización en una carpeta específica dentro de "storage/presentaciones". La carpeta se nombra según el nombre del archivo PPTX sin su extensión.

    Args:
        ruta_origen (str): La ruta del archivo PPTX que se va a guardar.
        datos_json (dict): Un diccionario con los datos de vectorización que se guardarán en formato JSON.

    Returns:
        str: La ruta de la carpeta donde se guardaron el PPTX y el JSON.
    
    flujo:
        1. Se determina la ruta base de almacenamiento dentro de "storage/presentaciones".
        2. Se extrae el nombre del archivo PPTX sin su extensión para nombrar la carpeta final.
        3. Se crea la carpeta final si no existe.
        4. Se copia el archivo PPTX a la carpeta final.
        5. Se guarda el JSON de vectorización en la misma carpeta.
      
    """
    # Tu lógica de guardado que ya tenemos
    base_dir = os.path.dirname(os.path.abspath(__file__))
    storage_base = os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "presentaciones"))
    
    nombre_sin_ext = os.path.splitext(os.path.basename(ruta_origen))[0]
    carpeta_final = os.path.join(storage_base, nombre_sin_ext)
    
    if not os.path.exists(carpeta_final):
        os.makedirs(carpeta_final)
    
    # Copiar PPTX
    shutil.copy(ruta_origen, os.path.join(carpeta_final, os.path.basename(ruta_origen)))
    
    # Guardar JSON
    ruta_json = os.path.join(carpeta_final, "vectorization.json")
    with open(ruta_json, 'w', encoding='utf-8') as f:
        json.dump(datos_json, f, ensure_ascii=False, indent=4)
        
    return carpeta_final
