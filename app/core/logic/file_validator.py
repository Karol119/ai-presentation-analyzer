# app/core/logic/file_validator.py
import os

def validar_tamano_archivo(ruta_archivo, limite_mb=50):
    """Valida que el archivo no exceda un tamaño específico en MB.

    Args:
        ruta_archivo (str): La ruta del archivo a validar.
        limite_mb (int, optional): El tamaño máximo en MB. Defaults to 30.

    Returns:
        tuple: Una tupla con un booleano indicando si es válido y un mensaje descriptivo.
        
    Ejemplo de uso:
        es_valido, mensaje = validar_tamano_archivo("ruta/a/archivo.pptx")
        if es_valido:
            print("Archivo válido.")
        else:
            print(f"Archivo no válido: {mensaje}")
    """
    # Obtener peso en bytes y convertir a MB
    peso_bytes = os.path.getsize(ruta_archivo)
    peso_mb = peso_bytes / (1024 * 1024)
    
    if peso_mb > limite_mb:
        return False, f"El archivo es demasiado pesado ({peso_mb:.2f}MB). El límite es {limite_mb}MB."
    
    return True, "Tamaño válido."