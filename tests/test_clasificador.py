import sys
import json
import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.controller.analyzer_controller import (
    analizar_presentacion,
    obtener_slides_contenido
)

PPTX_PRUEBA = "storage/presentaciones/prueba.pptx"


def seleccionar_archivo():
    """Abre el explorador de archivos para seleccionar un PPTX."""
    root = tk.Tk()
    root.withdraw()  # Oculta la ventana principal gris de tkinter
    root.attributes('-topmost', True) # Asegura que la ventana salga por encima de las demás
    
    ruta_archivo = filedialog.askopenfilename(
        title="Selecciona la presentación PPTX",
        filetypes=[
            ("Presentaciones de PowerPoint", "*.pptx"),
            ("Todos los archivos", "*.*")
        ]
    )
    return ruta_archivo


def main():
    # Si se pasa un argumento por consola (ej. python test.py mi_archivo.pptx), lo usa.
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        # Si no hay argumentos, abre el explorador
        print("[test] Abriendo explorador de archivos...")
        ruta = seleccionar_archivo()
        
        # Si el usuario cierra la ventana sin seleccionar nada, usamos el de prueba
        if not ruta:
            print(f"[test] No se seleccionó ningún archivo. Usando default: {PPTX_PRUEBA}")
            ruta = PPTX_PRUEBA

    if not os.path.exists(ruta):
        print(f"[test] Error - No encontrado: {ruta}")
        sys.exit(1)

    print(f"[test] Analizando: {ruta}\n")
    resultado = analizar_presentacion(ruta, usar_llm=True)

    resumen = resultado["resumen_clasificacion"]
    print(f"\nTotal       : {resultado['total_slides']}")
    print(f"Contenido   : {resumen['contenido']}")
    print(f"Excluidas   : {resumen['excluidas']}")
    print(f"Via LLM     : {resumen['por_llm']}")
    print(f"Inciertas   : {resumen['inciertas']}")

    slides_contenido = obtener_slides_contenido(resultado)
    print(f"\nSlides para ICD ({len(slides_contenido)}):")
    for s in slides_contenido:
        print(f"  [{s['slide_number']:02d}] {s['title'][:60]}")

    os.makedirs("tests/resultados", exist_ok=True)
    salida = f"tests/resultados/clasificacion_{Path(ruta).stem}.json"
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nJSON: {salida}")


if __name__ == "__main__":
    main()