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
    ruta = filedialog.askopenfilename(title="Fase 5: Reestructuración", filetypes=[("PowerPoint", "*.pptx")])
    root.destroy()
    return ruta

def ejecutar_auditoria_restructura():
    print(f"\n{Fore.CYAN}{'='*85}")
    print(f"{Fore.WHITE}{Style.BRIGHT} FASE 5: PROPUESTA DE MEJORA Y REESTRUCTURACIÓN DE CONTENIDOS ")
    print(f"{Fore.CYAN}{'='*85}\n")

    ruta = seleccionar_archivo()
    if not ruta: return

    res = analizar_presentacion(ruta)
    for s in res["slides"]:
        if s["omitida"] or not s["restructura"]: continue
        
        re = s["restructura"] # [cite: 198]
        print(f"{Fore.YELLOW}DIAPOSITIVA ORIGINAL {s['slide_number']:02d}")
        print(f"  {Fore.RED}Estado: Requiere intervención por: {s['score']['aspectos_mejorar']}")
        print(f"  {Fore.GREEN}Propuesta de Reestructuración ({len(re['diapositivas'])} slides):")
        
        for i, nueva in enumerate(re["diapositivas"], 1):
            print(f"    {Fore.CYAN}Nueva Slide {i}: {Fore.WHITE}{nueva['titulo']}")
            for b in nueva['contenido']: print(f"      • {b}")
            
        if not re["exito"]:
            print(f"  {Fore.RED}Métricas Pendientes: {re['metricas_fallidas_final']}")
        print(f"{Fore.CYAN}{'-'*85}")

if __name__ == "__main__":
    ejecutar_auditoria_restructura()    