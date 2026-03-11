import os

def validar_tamano_archivo(ruta_archivo, limite_mb=30):
    """Verifica que el archivo no supere el peso definido (30MB por defecto)."""
    # Obtener peso en bytes y convertir a MB
    peso_bytes = os.path.getsize(ruta_archivo)
    peso_mb = peso_bytes / (1024 * 1024)
    
    if peso_mb > limite_mb:
        return False, f"El archivo es demasiado pesado ({peso_mb:.2f}MB). El límite es {limite_mb}MB."
    
    return True, "Tamaño válido."