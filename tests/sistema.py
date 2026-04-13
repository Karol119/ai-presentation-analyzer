"""
Script de prueba CLI.
Responsabilidad única: seleccionar archivo e imprimir el resultado del análisis.
Toda la lógica vive en analyzer_controller.py.
"""
import sys
import time
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.controller.analyzer_controller import analizar_presentacion
inicio = time.time()

def seleccionar_archivo() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return filedialog.askopenfilename(filetypes=[("PowerPoint", "*.pptx")])


def imprimir_resultado(resultado: dict) -> None:
    sg = resultado["score_global"]

    print(f"\n{'='*85}")
    print(f" DIAGNÓSTICO INTEGRAL: {resultado['nombre']}")
    print(f"{'='*85}")

    for slide in resultado["slides"]:
        n = slide["slide_number"]

        if slide["omitida"]:
            print(f"\n[DIAPOSITIVA {n:02d}] - TIPO: {slide['tipo'].upper()} (Omitida)")
            continue

        ss       = slide["score"]
        mi       = slide["metricas_raw"]["icd"]
        mw       = slide["metricas_raw"]["wps"]
        feedback = slide["feedback"]

        print(f"\n┌─ EVALUACIÓN DIAPOSITIVA {n:02d} {'─'*30}")
        print(f"│ Score: {ss['score']} | Estado: {ss['zona'].upper()}")
        print(f"├{'─'*55}")

        if feedback:
            if "icd" in ss["aspectos_mejorar"]:
                print(f"│ 🧠 COMPLEJIDAD  (ICD: {mi.get('icd', 'N/A')})")
                print(f"│    {feedback.get('icd', '')}")

            if "wps" in ss["aspectos_mejorar"]:
                print(f"│ 📝 PALABRAS     (WPS: {mw.get('palabras', 'N/A')})")
                print(f"│    {feedback.get('wps', '')}")

            if "hss" in ss["aspectos_mejorar"]:
                print(f"│ 🏗️  ESTRUCTURA   (HSS)")
                print(f"│    {feedback.get('hss', '')}")

            if "nts" in ss["aspectos_mejorar"]:
                print(f"│ 🔗 NARRATIVA    (NTS)")
                print(f"│    {feedback.get('nts', '')}")

            # ── Preguntas para el docente ──────────────────────────────────
            preguntas = feedback.get("preguntas", [])
            if preguntas:
                print(f"│")
                print(f"│ ❓ PREGUNTAS PARA TUS ALUMNOS:")
                for i, q in enumerate(preguntas, 1):
                    print(f"│    {i}. {q}")

            # ── Datos curiosos ─────────────────────────────────────────────
            curiosos = feedback.get("datos_curiosos", [])
            if curiosos:
                print(f"│")
                print(f"│ 💡 DATOS CURIOSOS:")
                for dato in curiosos:
                    print(f"│    • {dato}")
        else:
            print(f"│ ✅ Diapositiva en rango óptimo. No se requieren ajustes.")

        print(f"└{'─'*55}")

    # ── Resumen final ──────────────────────────────────────────────────────────
    print(f"\n{'='*85}")
    print(f" RESUMEN FINAL DE LA PRESENTACIÓN")
    print(f"{'='*85}")
    print(f" SCORE GLOBAL : {sg['score_global']} / 10.0")
    print(f" ZONA GLOBAL  : {sg['zona_global'].upper()}")
    print(f"{'-'*85}")
    print(f" DESGLOSE PONDERADO:")
    print(f"  • ICD (35%): {sg['scores_metrica']['icd']} pts")
    print(f"  • WPS (25%): {sg['scores_metrica']['wps']} pts")
    print(f"  • HSS (25%): {sg['scores_metrica']['hss']} pts")
    print(f"  • NTS (15%): {sg['scores_metrica']['nts']} pts")
    print(f"{'='*85}\n")


def main():
    ruta = seleccionar_archivo()
    if not ruta:
        return
    resultado = analizar_presentacion(ruta)
    imprimir_resultado(resultado)


if __name__ == "__main__":
    main()
    
    fin = time.time()
    duracion = fin - inicio
    print(f"Duración del análisis: {duracion:.2f} segundos")