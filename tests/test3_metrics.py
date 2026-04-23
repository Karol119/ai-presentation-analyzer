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
    root.attributes("-topmost", True)
    ruta = filedialog.askopenfilename(
        title="Fase 3: Auditoría de Métricas e Hilo Narrativo", 
        filetypes=[("PowerPoint", "*.pptx")],
        initialdir=os.getcwd()
    )
    root.destroy()
    return ruta

def ejecutar_auditoria_metricas():
    print(f"\n{Fore.CYAN}{'='*90}")
    print(f"{Fore.WHITE}{Style.BRIGHT} FASE 3: EVALUACIÓN CUANTITATIVA Y NARRATIVA (ICD, WPS, HSS, NTS) ")
    print(f"{Fore.CYAN}{'='*90}\n")

    ruta = seleccionar_archivo()
    if not ruta: 
        print(f"{Fore.YELLOW}[AVISO]: Selección cancelada.")
        return

    res = analizar_presentacion(ruta)
    sg = res["score_global"]

    print(f"{Fore.GREEN}[ARCHIVO]: {res['nombre']}")
    print(f"  {Fore.CYAN}Puntaje General: {Fore.YELLOW}{sg['score_global']} / 10.0")
    print(f"  {Fore.CYAN}Clasificación:   {Fore.YELLOW}{sg['zona_global'].upper()}")
    print(f"{Fore.CYAN}{'-'*45}")

    for s in res["slides"]:
        if s["omitida"]: 
            continue
        
        m = s["metricas_raw"]
        ss = s["score"]
        
        print(f"{Fore.YELLOW}DIAPOSITIVA {s['slide_number']:02d}: {Fore.WHITE}Score {ss['score']}")
        
        # Métricas de Diapositiva Única
        print(f"  {Fore.CYAN}•{Fore.WHITE} Complejidad (ICD): {m['icd']['icd']} - {m['icd']['zona']}")
        print(f"  {Fore.CYAN}•{Fore.WHITE} Extensión (WPS):   {m['wps']['palabras']} palabras")
        print(f"  {Fore.CYAN}•{Fore.WHITE} Estructura (HSS):  {m['hss']['coherencia']}")
        
        # Detalle de Hilo Narrativo (NTS)
        nts_data = m['nts']
        color_nts = Fore.GREEN if nts_data['estado'] == "relacionada" else Fore.RED
        
        print(f"  {Fore.CYAN}•{Fore.WHITE} Hilo Narrativo (NTS): {color_nts}{nts_data['estado'].upper()}")
        print(f"      {Fore.BLACK}{Style.BRIGHT}Similitud Anterior: {nts_data.get('sim_anterior', 'N/A')}")
        print(f"      {Fore.BLACK}{Style.BRIGHT}Similitud Siguiente: {nts_data.get('sim_siguiente', 'N/A')}")
        
        print(f"{Fore.CYAN}{'-'*90}")

    print(f"\n{Fore.GREEN}{Style.BRIGHT}[SISTEMA]: Evaluación de métricas completada.")

if __name__ == "__main__":
    ejecutar_auditoria_metricas()