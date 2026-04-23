import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

init(autoreset=True)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.controller.analyzer_controller import analizar_presentacion

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    ruta = filedialog.askopenfilename(title="Fase 4: Diagnóstico Pedagógico", filetypes=[("PowerPoint", "*.pptx")])
    root.destroy()
    return ruta

def ejecutar_auditoria_feedback():
    print(f"\n{Fore.CYAN}{'='*85}")
    print(f"{Fore.WHITE}{Style.BRIGHT} FASE 4: AUDITORÍA DE DIAGNÓSTICO Y RETROALIMENTACIÓN (LLM) ")
    print(f"{Fore.CYAN}{'='*85}\n")

    ruta = seleccionar_archivo()
    if not ruta: return

    res = analizar_presentacion(ruta)
    for s in res["slides"]:
        if s["omitida"] or not s["feedback"]: continue
        
        fb = s["feedback"] # [cite: 171]
        print(f"{Fore.YELLOW}REPORTE DIAPOSITIVA {s['slide_number']:02d}")
        if fb.get("icd"): print(f"  {Fore.CYAN}[ICD]: {Fore.WHITE}{fb['icd']}")
        if fb.get("wps"): print(f"  {Fore.CYAN}[WPS]: {Fore.WHITE}{fb['wps']}")
        
        print(f"  {Fore.MAGENTA}Preguntas de Mediación:")
        for q in fb.get("preguntas", []): print(f"    - {q}")
        
        print(f"  {Fore.GREEN}Datos Curiosos:")
        for d in fb.get("datos_curiosos", []): print(f"    * {d}")
        print(f"{Fore.CYAN}{'-'*85}")

if __name__ == "__main__":
    ejecutar_auditoria_feedback()