import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

init(autoreset=True)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.logic.text_extractor import extraer_datos_pptx
from app.core.logic.slide_classifier import extraer_features, clasificar_diapositiva

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    ruta = filedialog.askopenfilename(
        title="Fase 2: Seleccionar Presentación para Clasificación",
        filetypes=[("PowerPoint Presentations", "*.pptx")],
        initialdir=os.getcwd()
    )
    root.destroy()
    return ruta

def ejecutar_auditoria_clasificacion():
    print(f"\n{Fore.CYAN}{'='*85}")
    print(f"{Fore.WHITE}{Style.BRIGHT} FASE 2: AUDITORÍA DEL MOTOR DE CLASIFICACIÓN Y FILTRADO LÓGICO ")
    print(f"{Fore.CYAN}{'='*85}\n")

    ruta = seleccionar_archivo()
    if not ruta: return

    datos = extraer_datos_pptx(ruta)
    for s in datos["slides"]:
        # Extracción de características vectoriales
        ft = extraer_features(s) # 
        # Inferencia por reglas y/o LLM
        res = clasificar_diapositiva(s) # [cite: 108]
        
        print(f"{Fore.YELLOW}Slide {s['slide_number']:02d}: {Fore.WHITE}'{s['title'][:35]}...'")
        print(f"  {Fore.CYAN}•{Fore.WHITE} Features: W={ft['W']}, B={ft['B']}, T={ft['W_titulo']}, Cita={ft['es_cita']}")
        print(f"  {Fore.CYAN}•{Fore.WHITE} Clasificación: {Fore.GREEN}{res['tipo'].upper()}")
        print(f"  {Fore.CYAN}•{Fore.WHITE} Método: {res['metodo']} | Confianza: {res['confianza']}")
        
        if res['reglas_disparadas']:
            print(f"  {Fore.CYAN}•{Fore.WHITE} Reglas: {Fore.BLACK}{Style.BRIGHT}{res['reglas_disparadas']}")
        
        status = f"{Fore.RED}OMITIDA" if res['excluir'] else f"{Fore.GREEN}EVALUABLE"
        print(f"  {Fore.CYAN}•{Fore.WHITE} Estado: {status}")
        print(f"{Fore.CYAN}{'-'*85}")

if __name__ == "__main__":
    ejecutar_auditoria_clasificacion()