import sys
import os
import tkinter as tk
from tkinter import filedialog
from colorama import init, Fore, Style

# Inicializar colores
init(autoreset=True)

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.logic.text_extractor import extraer_datos_pptx

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Seleccionar Presentación para Análisis",
        filetypes=[("PowerPoint Files", "*.pptx")],
        initialdir=os.path.join(os.getcwd(), "storage/presentaciones")
    )
    root.destroy()
    return file_path

def ejecutar_test_extraccion():
    print(f"\n{Fore.CYAN}{'='*80}")
    print(f"{Fore.WHITE}{Style.BRIGHT} MÓDULO DE EXTRACCIÓN: VALIDACIÓN DE CONTENIDO ESTRUCTURADO ")
    print(f"{Fore.CYAN}{'='*80}\n")

    ruta = seleccionar_archivo()
    if not ruta:
        print(f"{Fore.YELLOW}Selección cancelada.")
        return

    try:
        datos = extraer_datos_pptx(ruta)
        print(f"{Fore.GREEN}[ARCHIVO]: {datos['filename']}\n")

        for s in datos["slides"]:
            num = s['slide_number']
            titulo = s['title'] if s['title'] else "SIN TÍTULO DETECTADO"
            
            # Encabezado de Diapositiva con Título
            print(f"{Fore.YELLOW}{Style.BRIGHT}Diapositiva {num:02d}: {Fore.WHITE}{titulo}")
            
            # Estadísticas rápidas
            print(f"  {Fore.CYAN}•{Fore.WHITE} Bloques de contenido: {len(s['content'])}")
            print(f"  {Fore.CYAN}•{Fore.WHITE} Imágenes/Gráficos:   {len(s['images'])}")
            
            # Metadatos / Footer
            footer_str = str(s['footer']) if s['footer'] else "[]"
            print(f"  {Fore.CYAN}•{Fore.WHITE} Metadatos (Footer):  {Fore.BLACK}{Style.BRIGHT}{footer_str}")
            # --- NUEVA SECCIÓN: CONTENIDO EXTRAÍDO ---
            if s['content']:
                print(f"  {Fore.CYAN}•{Fore.WHITE} Texto Extraído:")
                for i, bloque in enumerate(s['content'], 1):
                    # Limpiamos el texto para que no rompa el formato de la terminal
                    texto_limpio = bloque.replace('\n', ' ').strip()
                    print(f"      {Fore.BLACK}{Style.BRIGHT}[Bloque {i}]: {Fore.WHITE}{texto_limpio}")
            
            if s['tiene_solo_imagen']:
                print(f"  {Fore.MAGENTA}[INFO]: Diapositiva identificada como puramente visual.")
            
            print(f"{Fore.CYAN}{'-'*80}")

        print(f"\n{Fore.GREEN}{Style.BRIGHT}[ÉXITO]: Ingesta de datos completada.")

    except Exception as e:
        print(f"\n{Fore.RED}[ERROR]: {str(e)}")

if __name__ == "__main__":
    ejecutar_test_extraccion()