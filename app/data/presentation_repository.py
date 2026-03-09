import os
import shutil
from tkinter import filedialog, Tk

def seleccionar_y_guardar_archivo():
    # 1. Selección del archivo
    root = Tk()
    root.withdraw()
    ruta_origen = filedialog.askopenfilename(
        title="Seleccionar Presentación para el TT",
        filetypes=[("PowerPoint", "*.pptx"), ("PDF", "*.pdf")]
    )
    root.destroy()

    if not ruta_origen:
        return None

    # 2. Preparar las rutas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Carpeta base: storage/presentaciones
    storage_base = os.path.abspath(os.path.join(base_dir, "..", "..", "storage", "presentaciones"))
    
    # Obtener nombre con y sin extensión
    nombre_con_extension = os.path.basename(ruta_origen)
    nombre_sin_extension = os.path.splitext(nombre_con_extension)[0] # "Tema_1"
    
    # 3. CREAR LA SUB-CARPETA ESPECÍFICA
    # Ruta final: storage/presentaciones/Tema_1/
    carpeta_especifica = os.path.join(storage_base, nombre_sin_extension)
    
    if not os.path.exists(carpeta_especifica):
        os.makedirs(carpeta_especifica)
        print(f"Directorio creado: {nombre_sin_extension}")

    # 4. Copiar el archivo dentro de su propia carpeta
    destino_final = os.path.join(carpeta_especifica, nombre_con_extension)
    shutil.copy(ruta_origen, destino_final)
    
    return destino_final