# app/core/logic/file_validator.py
import os

def validar_tamano_archivo(ruta_archivo, limite_mb=30):
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


def validar_ruta_destino(ruta_archivo, nombre_materia, longitud_extra=0, limite_ruta=248):
    """
    Valida que el NOMBRE del archivo quepa en las rutas que el sistema
    realmente generará al registrar la presentación.

    La app guarda en storage el PPTX, más una miniatura ('_thumb.png'), un
    PDF y un JSON de análisis junto al archivo. Windows (API Win32) falla
    cuando la RUTA COMPLETA supera los 260 caracteres, así que un nombre de
    217 caracteres permitido por el explorador puede reventar el proceso a
    mitad de la carga. Esta validación rechaza el archivo ANTES de empezar
    con un mensaje claro y accionable para el usuario.

    Returns:
        tuple: (es_valido, mensaje_controlado)
    """
    # Raíz del proyecto: app/core/logic/file_validator.py -> proyecto (4 niveles)
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    carpeta = os.path.join(raiz, "storage", "presentaciones", nombre_materia)

    nombre_archivo = os.path.basename(ruta_archivo)

    prefix_len = len(os.path.join(carpeta, ""))
    # El archivo "derivado" más largo que se genera es <base>_thumb.png.
    # longitud_extra cubre sufijos como '_v2' en nuevas versiones.
    longitud_peor_caso = prefix_len + len(nombre_archivo) + len("_thumb.png") + max(longitud_extra, 0)

    if longitud_peor_caso > limite_ruta:
        # El nombre se cuenta CON extensión (así lo usa la condición de arriba)
        nombre_maximo = limite_ruta - prefix_len - len("_thumb.png") - max(longitud_extra, 0)
        nombre_maximo = max(nombre_maximo, 1)
        return False, (
            "El nombre del archivo es demasiado largo "
            f"({len(nombre_archivo)} caracteres) para las rutas internas de "
            "Windows (las rutas completas no pueden pasar de 260 caracteres).\n\n"
            f"Reduce el nombre a {nombre_maximo} caracteres o menos "
            "(contando la extensión) y vuelve a cargar la presentación."
        )

    return True, "Rutas de destino válidas."