import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

# Inicializar colores para la terminal
init(autoreset=True)

# Agregar la raíz del proyecto al sys.path para poder importar 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.controller.analyzer_controller import analyze_presentation

def seleccionar_archivo() -> str:
    """Abre un diálogo nativo del sistema para seleccionar un archivo PPTX."""
    root = tk.Tk()
    root.withdraw()  # Ocultamos la ventana principal pequeña de Tkinter
    root.attributes("-topmost", True)  # Forzamos que la ventana salga al frente
    
    file_path = filedialog.askopenfilename(
        title="Seleccionar Presentación para Análisis de Métricas Locales",
        filetypes=[("PowerPoint Files", "*.pptx")]
    )
    
    root.destroy()
    return file_path

def print_progreso(mensaje: str) -> None:
    """Callback para que el orquestador nos informe de su progreso."""
    print(f"{Fore.CYAN}{mensaje}")

def ejecutar_test():
    print(f"\n{Fore.BLUE}{'='*80}")
    print(f"{Fore.WHITE}{Style.BRIGHT} TEST: ORQUESTADOR Y MÉTRICAS LOCALES (ICD Y WPS) CON HILOS")
    print(f"{Fore.BLUE}{'='*80}\n")
    
    ruta_pptx = seleccionar_archivo()
    
    if not ruta_pptx:
        print(f"{Fore.YELLOW}[INFO] Selección de archivo cancelada.")
        return
        
    print(f"{Fore.GREEN}[ARCHIVO SELECCIONADO]: {ruta_pptx}\n")
    
    try:
        # Llamamos a nuestro orquestador y le pasamos el callback de consola
        resultado = analyze_presentation(ruta_pptx, status_cb=print_progreso)
        
        print(f"\n{Fore.MAGENTA}{'='*80}")
        print(f"{Fore.WHITE}{Style.BRIGHT} RESULTADOS DE LA PRESENTACIÓN: {resultado['nombre']}")
        print(f"{Fore.MAGENTA}{'='*80}\n")
        
        print(f"{Fore.GREEN}Score Global del documento: {resultado['score_global']['score_global']} / 10.0\n")
        
        for slide in resultado["slides"]:
            numero = slide["slide_number"]
            tipo = slide["tipo"]
            
            print(f"{Fore.YELLOW}{Style.BRIGHT}Diapositiva {numero:02d} | Tipo: {tipo.upper()}")
            
            if slide["omitida"]:
                print(f"  {Fore.BLACK}{Style.BRIGHT}[!] Diapositiva omitida de las métricas (es portada, índice, etc.)\n")
                continue
                
            # Accedemos a los datos crudos extraídos por el Hilo Local
            raw_icd = slide["metricas_raw"].get("icd", {})
            raw_wps = slide["metricas_raw"].get("wps", {})
            
            # Mostrar datos de Complejidad (ICD)
            if raw_icd.get("calculable"):
                icd_val = raw_icd.get("icd")
                icd_zona = raw_icd.get("zona")
                print(f"  {Fore.WHITE}• Complejidad (ICD) : {Fore.GREEN if 4.0 <= icd_val <= 6.5 else Fore.RED}{icd_val} ({icd_zona})")
                print(f"    - Índice Flesch: {raw_icd.get('fsz')} | Densidad Léxica: {raw_icd.get('dl')}%")
            else:
                print(f"  {Fore.WHITE}• Complejidad (ICD) : {Fore.BLACK}{Style.BRIGHT}No calculable (texto insuficiente)")
                
            # Mostrar datos de Cantidad de Palabras (WPS)
            wps_val = raw_wps.get("palabras", 0)
            wps_zona = raw_wps.get("zona")
            print(f"  {Fore.WHITE}• Palabras (WPS)    : {Fore.GREEN if wps_val <= 75 else Fore.RED}{wps_val} ({wps_zona})\n")

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR FATAL]: {str(e)}")

if __name__ == "__main__":
    ejecutar_test()