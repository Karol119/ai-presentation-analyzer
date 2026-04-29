import sys
import os
import json
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

init(autoreset=True)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importamos la función ya traducida al español
from app.core.controller.analyzer_controller import analizar_presentacion

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
        # Usamos el nuevo nombre de la función y su parámetro en español
        resultado = analizar_presentacion(ruta, callback_estado=print_progreso)
        
        score_data = resultado.get('score_global_presentacion', {})
        tiempo_total = resultado.get('tiempo_total_formateado', 'N/A')
        total_slides = resultado.get('total_diapositivas', 0)

        print(f"\n{Fore.GREEN}{Style.BRIGHT}==================================================")
        print(f"{Fore.GREEN}{Style.BRIGHT}  REPORTE FINAL DE LA PRESENTACIÓN")
        print(f"{Fore.GREEN}{Style.BRIGHT}==================================================")
        print(f"  {Fore.WHITE}• Total de diapositivas: {total_slides}")
        print(f"  {Fore.WHITE}• Score Global: {score_data.get('score_global', 0)} / 10.0 ({score_data.get('zona_global', '').upper()})")
        print(f"  {Fore.WHITE}• Tiempo Total Estimado: {tiempo_total}")
        print(f"{Fore.GREEN}{Style.BRIGHT}==================================================\n")

        # --- IMPRIMIR EL DESGLOSE DE MÉTRICAS GLOBALES ---
        scores_m = score_data.get('scores_metrica', {})
        if scores_m:
            print(f"{Fore.CYAN}  DESGLOSE GLOBAL POR MÉTRICAS:")
            print(f"  {Fore.WHITE}• ICD Global (Complejidad): {scores_m.get('icd')} / 10.0")
            print(f"  {Fore.WHITE}• WPS Global (Cant. Pal)  : {scores_m.get('wps')} / 10.0")
            print(f"  {Fore.WHITE}• HSS Global (Títulos)    : {scores_m.get('hss')} / 10.0")
            print(f"  {Fore.WHITE}• NTS Global (Hilo)       : {scores_m.get('nts')} / 10.0\n")

        # --- IMPRIMIR EL DESGLOSE DE PESOS ---
        desglose = score_data.get('desglose', {})
        pesos = score_data.get('pesos', {})
        if desglose:
            print(f"{Fore.MAGENTA}  INFLUENCIA DE LOS PESOS (APORTACIÓN AL SCORE):")
            for k, p in pesos.items():
                p_real = desglose.get(f"{k}_pond", 0)
                print(f"  {Fore.WHITE}• {k.upper()}: Aporta {p_real} puntos (Peso: {int(p*100)}%)")
            print()

        for s in resultado["slides"]:
            print(f"{Fore.BLUE}{'-'*60}")
            
            tiempo_slide = s.get('tiempo_exposicion', 'N/A')
            
            if s.get("omitida"):
                print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {s['slide_number']:02d} | CLASIFICACIÓN IA: {s.get('tipo', 'desconocido').upper()} | Tiempo: {tiempo_slide} seg")
                print(f"  {Fore.BLACK}{Style.BRIGHT}[!] Omitida de la evaluación (No es contenido evaluable)")
                continue
                
            # Título de diapositiva con su score individual y tiempo
            print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {s['slide_number']:02d} | Score: {s['score_slide']} ({s['zona_slide'].upper()}) | Tiempo: {tiempo_slide} seg")
            
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

        # --- EL BLOQUE FINAL: VOLCADO DE JSON PARA BASE DE DATOS ---
        print(f"\n\n{Fore.MAGENTA}{Style.BRIGHT}{'='*30} JSON FINAL (OBJETO DE BASE DE DATOS) {'='*30}")
        
        # Convertimos el diccionario a un string JSON con formato
        json_final = json.dumps(resultado, indent=2, ensure_ascii=False)
        
        print(Fore.WHITE + json_final)
        
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}{'='*80}\n")
        print(f"{Fore.CYAN}[INFO] El objeto anterior es exactamente lo que se enviará a la tabla de Persistencia.")
            
    except Exception as e:
        print(f"\n{Fore.RED}[ERROR]: {str(e)}")
        
if __name__ == "__main__":
    ejecutar_test()