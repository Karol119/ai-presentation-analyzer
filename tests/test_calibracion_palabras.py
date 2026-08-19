import sys
import os
import csv
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import statistics
from colorama import init, Fore, Style

# Inicializar colores en consola
init(autoreset=True)

# Asegurar que el script encuentre la carpeta 'app'
# Ajusta '..' si metes este archivo dentro de la carpeta 'tests/'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) 

# Importamos las herramientas de extracción y conteo
from app.core.logic.text_extractor import extraer_datos_pptx
from app.core.logic.metrics.text_counter import contar_palabras

def calcular_palabras_contenido(slide_data, nombre_archivo) -> dict:
    """Extrae y cuenta SOLO las palabras del contenido (ignorando título y footer)."""
    
    # Extraemos exclusivamente el arreglo 'content'
    contenido_lista = slide_data.get("content", [])
    texto_contenido = " ".join(contenido_lista)
    
    # Contamos las palabras reales (ignorando números sueltos gracias a tu text_counter)
    palabras = contar_palabras(texto_contenido)
    
    # Descartamos diapositivas vacías, portadas o índices (menos de 5 palabras)
    if palabras < 5:
        return None
    
    return {
        "Archivo": nombre_archivo,
        "Slide": slide_data.get("slide_number"),
        "Palabras_Contenido": palabras
    }

def procesar_archivo(ruta_archivo) -> list:
    """Extrae un PPTX y evalúa el conteo de palabras de todas sus diapositivas."""
    nombre = Path(ruta_archivo).name
    try:
        data = extraer_datos_pptx(str(ruta_archivo))
        resultados_slides = []
        for slide in data["slides"]:
            res = calcular_palabras_contenido(slide, nombre)
            if res:
                resultados_slides.append(res)
        return resultados_slides
    except Exception as e:
        print(f"{Fore.RED}Error procesando {nombre}: {e}")
        return []

def seleccionar_carpeta() -> str:
    """Abre el diálogo para seleccionar una carpeta."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    print(f"{Fore.CYAN}Esperando selección de carpeta...")
    carpeta = filedialog.askdirectory(title="Selecciona la carpeta con las presentaciones PPTX")
    return carpeta

def calcular_y_mostrar_estadisticas(datos: list):
    """Calcula los cuartiles (el rango ideal) para el conteo de palabras."""
    if not datos:
        print(f"{Fore.RED}No se obtuvieron datos suficientes para hacer estadística.")
        return

    palabras_vals = [d["Palabras_Contenido"] for d in datos]

    print(f"\n{Fore.WHITE}{Style.BRIGHT}{'='*60}")
    print(f" RESUMEN DE CALIBRACIÓN: PALABRAS DE CONTENIDO (MUESTRA: {len(datos)} diapositivas)")
    print(f"{'='*60}\n")
    print(f"{Fore.YELLOW}¿Cómo leer esto? El rango entre Q1 (Percentil 25) y Q3 (Percentil 75)")
    print(f"{Fore.YELLOW}representa el 50% central de tus datos, es decir, 'LO NORMAL'.\n")

    try:
        # quantiles(n=4) devuelve [Q1, Mediana, Q3]
        q = statistics.quantiles(palabras_vals, n=4)
        q1, med, q3 = round(q[0], 2), round(q[1], 2), round(q[2], 2)
        
        print(f"{Fore.CYAN}>> Cantidad de Palabras por Diapositiva (Solo Contenido):")
        print(f"   Rango Más Popular (Q1 a Q3): {Fore.GREEN}{Style.BRIGHT}[ {q1}  ---  {q3} ]")
        print(f"   Mediana (Punto Central)  : {med}")
        print(f"   Mínimo: {min(palabras_vals)} | Máximo: {max(palabras_vals)}\n")
        
    except statistics.StatisticsError:
        print(f"{Fore.RED}>> Datos insuficientes para estadística.\n")

def exportar_a_csv(datos: list, ruta_carpeta: str):
    """Guarda todos los datos en un Excel (CSV) en la carpeta analizada."""
    if not datos: return
    
    ruta_csv = os.path.join(ruta_carpeta, "Reporte_Calibracion_WPS.csv")
    columnas = list(datos[0].keys())
    
    with open(ruta_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(datos)
        
    print(f"{Fore.GREEN}{Style.BRIGHT}¡Éxito! Se ha guardado el archivo detallado en:")
    print(f"{Fore.WHITE}{ruta_csv}")
    print(f"{Fore.YELLOW}Abre este archivo en Excel si deseas ver diapositiva por diapositiva.")

def ejecutar_test():
    carpeta = seleccionar_carpeta()
    if not carpeta:
        print(f"{Fore.RED}No se seleccionó ninguna carpeta. Saliendo...")
        return
        
    archivos_pptx = list(Path(carpeta).rglob('*.pptx'))
    if not archivos_pptx:
        print(f"{Fore.RED}No se encontraron archivos .pptx en la carpeta seleccionada.")
        return

    print(f"\n{Fore.CYAN}Encontrados {len(archivos_pptx)} archivos PPTX. Extrayendo palabras (multihilo)...\n")
    
    resultados_globales = []
    
    # Procesar archivos en paralelo (Súper rápido ya que no usa IA)
    with ThreadPoolExecutor() as executor:
        resultados_futuros = executor.map(procesar_archivo, archivos_pptx)
        
        for res_slide_list in resultados_futuros:
            resultados_globales.extend(res_slide_list)

    # Imprimir consola y exportar
    calcular_y_mostrar_estadisticas(resultados_globales)
    exportar_a_csv(resultados_globales, carpeta)

if __name__ == "__main__":
    ejecutar_test()