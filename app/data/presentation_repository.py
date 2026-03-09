import os
import shutil

def crear_carpeta_y_copiar(ruta_origen):
    # Definir ruta base de storage
    base_dir = os.path.dirname(os.path.abspath(__file__))
    storage_base = os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "presentaciones"))
    
    # Obtener nombres
    nombre_con_ext = os.path.basename(ruta_origen)
    nombre_sin_ext = os.path.splitext(nombre_con_ext)[0]
    
    # Crear subcarpeta específica
    ruta_carpeta_final = os.path.join(storage_base, nombre_sin_ext)
    
    if not os.path.exists(ruta_carpeta_final):
        os.makedirs(ruta_carpeta_final)
    
    # Copiar archivo
    destino = os.path.join(ruta_carpeta_final, nombre_con_ext)
    shutil.copy(ruta_origen, destino)
    
    return destino