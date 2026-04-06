import sys
import json
import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.controller.analyzer_controller import analizar_presentacion

PPTX_PRUEBA = "storage/presentaciones/prueba.pptx"


def seleccionar_archivo():
    """Abre el explorador de archivos para seleccionar estrictamente un PPTX."""
    root = tk.Tk()
    root.withdraw()  # Oculta la ventana principal gris de tkinter
    root.attributes('-topmost', True) # Asegura que la ventana salga por encima
    
    ruta_archivo = filedialog.askopenfilename(
        title="Selecciona la presentación PPTX",
        filetypes=[
            ("Presentaciones de PowerPoint", "*.pptx") # Solo permite .pptx
        ]
    )
    return ruta_archivo


def main():
    # 1. Elegir ruta por consola o por explorador
    if len(sys.argv) > 1:
        ruta = sys.argv[1]
    else:
        print("[test] Abriendo explorador de archivos...")
        ruta = seleccionar_archivo()
        
        # Si el usuario cierra la ventana, usa el archivo de prueba
        if not ruta:
            print(f"[test] No se seleccionó nada. Usando default: {PPTX_PRUEBA}")
            ruta = PPTX_PRUEBA

    # 2. Verificar que exista
    if not os.path.exists(ruta):
        print(f"[test] Error - No encontrado: {ruta}")
        sys.exit(1)

    print(f"[test] Analizando: {ruta}\n")
    
    # 3. Ejecutar análisis
    resultado = analizar_presentacion(ruta, usar_llm=True)

    icd = resultado["icd"]

    # 4. Imprimir resultados en consola
    print(f"\n{'='*55}")
    print(f" RESUMEN ICD — {resultado['filename']}")
    print(f"{'='*55}")
    print(f"  Promedio ICD  : {icd['icd_promedio']}  ({icd['zona_promedio']})")
    print(f"  Mínimo        : {icd['icd_minimo']}")
    print(f"  Máximo        : {icd['icd_maximo']}")
    print(f"  Slides ICD    : {icd['slides_calculadas']}")
    print(f"  Sin texto     : {icd['slides_sin_texto']}")

    # 5. Guardar el JSON
    os.makedirs("tests/resultados", exist_ok=True)
    nombre = Path(ruta).stem
    salida = f"tests/resultados/icd_{nombre}.json"

    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\n[test] JSON guardado: {salida}")


if __name__ == "__main__":
    main()