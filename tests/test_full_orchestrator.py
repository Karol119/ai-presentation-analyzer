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
        
        # Extracción del nuevo objeto global
        score_data = resultado.get('score_global_presentacion', {})
        print(f"\n{Fore.GREEN}{Style.BRIGHT}==================================================")
        print(f"{Fore.GREEN}{Style.BRIGHT}  SCORE GLOBAL: {score_data.get('score_global', 0)} / 10.0  ({score_data.get('zona_global', '').upper()})")
        print(f"{Fore.GREEN}{Style.BRIGHT}==================================================\n")

        for s in resultado["slides"]:
            print(f"{Fore.BLUE}{'-'*60}")
            
            if s.get("omitida"):
                print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {s['slide_number']:02d} | CLASIFICACIÓN IA: {s.get('tipo', 'desconocido').upper()}")
                print(f"  {Fore.BLACK}{Style.BRIGHT}[!] Omitida de la evaluación (No es contenido evaluable)")
                continue
                
            # Título de diapositiva con su score individual
            print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {s['slide_number']:02d} | Score: {s['score_slide']} ({s['zona_slide'].upper()})")
            
            metricas = s.get("metricas", {})
            if metricas:
                print(f"\n  {Fore.CYAN}ESTADO DE MÉTRICAS:")
                
                # Función auxiliar para pintar de rojo lo que hay que mejorar
                def format_metric(name, data):
                    color = Fore.RED if data['estado'] == 'MEJORAR' else Fore.GREEN
                    return f"  {Fore.WHITE}• {name}: {data['valor']}  [{color}{data['estado']}{Fore.WHITE}]"
                
                print(format_metric("ICD (Complejidad)", metricas['icd']))
                print(format_metric("WPS (Cant. Pal)  ", metricas['wps']))
                print(format_metric("HSS (Título IA)  ", metricas['hss']))
                print(format_metric("NTS (Hilo IA)    ", metricas['nts']))
                
                print(f"\n  {Fore.YELLOW}FEEDBACK PEDAGÓGICO:")
                if metricas["icd"]["feedback"]: print(f"  {Fore.CYAN}ICD: {Fore.WHITE}{metricas['icd']['feedback']}")
                if metricas["wps"]["feedback"]: print(f"  {Fore.CYAN}WPS: {Fore.WHITE}{metricas['wps']['feedback']}")
                if metricas["hss"]["feedback"]: print(f"  {Fore.CYAN}HSS: {Fore.WHITE}{metricas['hss']['feedback']}")
                if metricas["nts"]["feedback"]: print(f"  {Fore.CYAN}NTS: {Fore.WHITE}{metricas['nts']['feedback']}")
            
            print(f"\n  {Fore.CYAN}{Style.BRIGHT}MATERIAL DIDÁCTICO:")
            for p in s.get('preguntas', []): print(f"    - {Fore.WHITE}{p}")
            for d in s.get('datos_curiosos', []): print(f"    - {Fore.WHITE}{d}")

            reest = s.get("reestructuracion")
            if reest and reest.get("diapositivas_generadas"):
                print(f"\n  {Fore.GREEN}{Style.BRIGHT}--- REESTRUCTURACIÓN GENERADA ({len(reest['diapositivas_generadas'])} partes) ---")
                for idx, nueva_slide in enumerate(reest['diapositivas_generadas'], 1):
                    print(f"\n    {Fore.GREEN}[DIAPOSITIVA {s['slide_number']}.{idx}] {nueva_slide.get('titulo_sugerido')}")
                    print(f"    {Fore.WHITE}{nueva_slide.get('contenido_optimizado')}")
            else:
                print(f"\n  {Fore.GREEN}{Style.BRIGHT}✓ Sin reestructuración (Cumple con los parámetros de calidad).")
            print()
            
    except Exception as e:
        print(f"\n{Fore.RED}[ERROR]: {str(e)}")
        
if __name__ == "__main__":
    ejecutar_test()