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
    file_path = filedialog.askopenfilename(
        title="Seleccionar Presentación para Análisis Local",
        filetypes=[("PowerPoint Files", "*.pptx")]
    )
    root.destroy()
    return file_path

def print_progreso(mensaje: str) -> None:
    print(f"{Fore.CYAN}{mensaje}")

def ejecutar_test():
    print(f"\n{Fore.BLUE}{'='*80}")
    print(f"{Fore.WHITE}{Style.BRIGHT} TEST: MÉTRICAS LOCALES CON FEEDBACK INSTANTÁNEO ")
    print(f"{Fore.BLUE}{'='*80}\n")
    
    ruta_pptx = seleccionar_archivo()
    if not ruta_pptx:
        print(f"{Fore.YELLOW}[INFO] Selección cancelada.")
        return
        
    print(f"{Fore.GREEN}[ARCHIVO SELECCIONADO]: {ruta_pptx}\n")
    
    try:
        resultado = analyze_presentation(ruta_pptx, status_cb=print_progreso)
        
        print(f"\n{Fore.MAGENTA}{'='*80}")
        print(f"{Fore.WHITE}{Style.BRIGHT} RESULTADOS: {resultado['nombre']}")
        print(f"{Fore.MAGENTA}{'='*80}\n")
        
        for slide in resultado["slides"]:
            numero = slide["slide_number"]
            
            print(f"{Fore.YELLOW}{Style.BRIGHT}Diapositiva {numero:02d}")
            
            raw_icd = slide["metricas_raw"].get("icd", {})
            raw_wps = slide["metricas_raw"].get("wps", {})
            feedback = slide.get("feedback", {})
            
            # --- IMPRESIÓN DE COMPLEJIDAD (ICD) ---
            if raw_icd.get("calculable"):
                icd_val = raw_icd.get("icd")
                icd_zona = raw_icd.get("zona")
                color_icd = Fore.GREEN if 4.0 <= icd_val <= 6.5 else Fore.RED
                print(f"  {Fore.WHITE}• Complejidad (ICD) : {color_icd}{icd_val} ({icd_zona})")
                print(f"    - Índice Flesch: {raw_icd.get('fsz')} | Densidad Léxica: {raw_icd.get('dl')}%")
                
                # Mostrar el Feedback Local de ICD si existe
                if feedback.get("icd"):
                    print(f"    {Fore.CYAN}>> Sugerencia Pedagógica: {Fore.WHITE}{feedback['icd']}")
            else:
                print(f"  {Fore.WHITE}• Complejidad (ICD) : {Fore.BLACK}{Style.BRIGHT}No calculable")
                
            # --- IMPRESIÓN DE PALABRAS (WPS) ---
            wps_val = raw_wps.get("palabras", 0)
            wps_zona = raw_wps.get("zona")
            color_wps = Fore.GREEN if wps_val <= 75 else Fore.RED
            print(f"  {Fore.WHITE}• Palabras (WPS)    : {color_wps}{wps_val} ({wps_zona})")
            
            # Mostrar el Feedback Local de WPS si existe
            if feedback.get("wps"):
                print(f"    {Fore.CYAN}>> Sugerencia Pedagógica: {Fore.WHITE}{feedback['wps']}")
            print()

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR FATAL]: {str(e)}")

if __name__ == "__main__":
    ejecutar_test()