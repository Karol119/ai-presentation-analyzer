import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

# Inicializar colores en la consola
init(autoreset=True)

# Agregar la ruta raíz para que encuentre la carpeta 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Importamos solo lo necesario (Extractor + Métricas)
from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.metrics.icd import calculate_presentation_icd
from app.core.logic.metrics.word_count import calculate_presentation_wps
from app.core.logic.metrics.ai_batch_metrics import calculate_ai_metrics_batch

def seleccionar_archivo() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return filedialog.askopenfilename(title="Selecciona un PPTX para evaluar métricas", filetypes=[("PPTX", "*.pptx")])

def ejecutar_test():
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.WHITE}{Style.BRIGHT} TEST AISLADO: EVALUACIÓN DE DIAGNÓSTICO Y FEEDBACK ")
    print(f"{Fore.CYAN}{'='*80}\n")
    
    ruta = seleccionar_archivo()
    if not ruta:
        print(f"{Fore.RED}No se seleccionó ningún archivo.")
        return
        
    print(f"{Fore.YELLOW}>> Extrayendo texto de la presentación...")
    extracted_data = extract_pptx_data(ruta)
    todas_las_diapositivas = extracted_data["slides"]
    
    print(f"{Fore.YELLOW}>> Calculando métricas locales (CPU)...")
    res_icd = calculate_presentation_icd(todas_las_diapositivas)
    res_wps = calculate_presentation_wps(todas_las_diapositivas)
    
    print(f"{Fore.YELLOW}>> Solicitando evaluación de diagnósticos a la IA (Batch)...")
    ai_res = calculate_ai_metrics_batch(todas_las_diapositivas)
    
    res_hss = ai_res["hss"]
    res_nts = ai_res["nts"]
    clasificaciones_ia = ai_res.get("clasificaciones", {})

    print(f"\n{Fore.GREEN}{Style.BRIGHT}--- REPORTE DE RECOMENDACIONES POR DIAPOSITIVA ---\n")

    for slide in todas_las_diapositivas:
        num = slide["slide_number"]
        tipo_detectado = clasificaciones_ia.get(num, "contenido")
        
        print(f"{Fore.BLUE}{'-'*60}")
        print(f"{Fore.WHITE}{Style.BRIGHT}DIAPOSITIVA {num:02d} | Tipo: {tipo_detectado.upper()}")
        
        if tipo_detectado != "contenido":
            print(f"  {Fore.BLACK}{Style.BRIGHT}[Omitida] No se evalúan métricas para este tipo de diapositiva.")
            continue
            
        # Extraer métricas individuales
        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == num), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == num), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == num), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == num), {})

        # Imprimir Calificaciones
        print(f"\n  {Fore.CYAN}CALIFICACIONES:")
        print(f"  {Fore.WHITE}• ICD (Complejidad):  {mi.get('icd', 'N/A')} / 10.0")
        print(f"  {Fore.WHITE}• WPS (Cant. Pal):    {mw.get('wps_score', 'N/A')} / 10.0  ({mw.get('palabras')} palabras)")
        print(f"  {Fore.MAGENTA}• HSS (Título IA):    {mh.get('hss_score', 'N/A')} / 10.0")
        print(f"  {Fore.MAGENTA}• NTS (Hilo IA):      {mn.get('nts_score', 'N/A')} / 10.0")

        # Imprimir Recomendaciones
        print(f"\n  {Fore.YELLOW}RECOMENDACIONES (FEEDBACK):")
        if mi.get("feedback_local"): print(f"  {Fore.WHITE}ICD: {mi['feedback_local']}")
        if mw.get("feedback_local"): print(f"  {Fore.WHITE}WPS: {mw['feedback_local']}")
        if mh.get("feedback_ai"):    print(f"  {Fore.WHITE}HSS: {mh['feedback_ai']}")
        if mn.get("feedback_ai"):    print(f"  {Fore.WHITE}NTS: {mn['feedback_ai']}")
        print()

if __name__ == "__main__":
    ejecutar_test()