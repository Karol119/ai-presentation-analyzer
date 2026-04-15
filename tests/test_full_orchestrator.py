import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

init(autoreset=True)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.controller.analyzer_controller import analyze_presentation

def seleccionar_archivo() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return filedialog.askopenfilename(title="Test de Orquestador con IA", filetypes=[("PPTX", "*.pptx")])

def print_progreso(mensaje: str) -> None:
    print(f"{Fore.YELLOW}>> {mensaje}")

def ejecutar_test():
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.WHITE}{Style.BRIGHT} TEST INTEGRAL: HILOS DE RENDIMIENTO + IA AUMENTADA ")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    ruta = seleccionar_archivo()
    if not ruta: return
    
    try:
        resultado = analyze_presentation(ruta, status_cb=print_progreso)
        
        print(f"\n{Fore.GREEN}{Style.BRIGHT}RESULTADO GLOBAL: {resultado['score_global']['score_global']} / 10.0")
        print(f"{Fore.WHITE}Zona: {resultado['score_global']['zona_global'].upper()}\n")

        for s in resultado["slides"]:
            print(f"{Fore.BLUE}{'-'*40}")
            print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {s['slide_number']:02d}")
            
            raw = s["metricas_raw"]
            
            # Métricas Locales
            print(f"  {Fore.WHITE}• ICD: {raw['icd'].get('icd', 'N/A')} | WPS: {raw['wps'].get('palabras', 0)}")
            
            # Métricas de IA (El "juicio" del modelo)
            print(f"  {Fore.MAGENTA}{Style.BRIGHT}• Juicio IA HSS (Título): {Fore.WHITE}{raw['hss'].get('hss_score')} - {raw['hss'].get('coherencia')}")
            print(f"  {Fore.MAGENTA}{Style.BRIGHT}• Juicio IA NTS (Hilo):   {Fore.WHITE}{raw['nts'].get('nts_score')} - {raw['nts'].get('estado')}")
            
            if s["feedback"]["icd"]:
                print(f"  {Fore.CYAN}Recomendación ICD: {Fore.WHITE}{s['feedback']['icd']}")
            
    except Exception as e:
        print(f"\n{Fore.RED}[ERROR]: {str(e)}")

if __name__ == "__main__":
    ejecutar_test()