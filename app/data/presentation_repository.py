import os
import shutil
import json

def guardar_todo(ruta_origen, datos_json):

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