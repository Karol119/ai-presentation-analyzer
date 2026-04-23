#Definicion de complejidad
import sys
import os
import csv
import re
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import statistics
from colorama import init, Fore, Style

# Inicializar colores en consola
init(autoreset=True)

# Asegurar que el script encuentre la carpeta 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))) # Ajusta '..' si lo metes en una subcarpeta

# Importamos EXCLUSIVAMENTE las herramientas de extracción y conteo (Cero IA)
from app.core.logic.text_extractor import extract_pptx_data
from app.core.logic.metrics.text_counter import (
    preparar_texto_slide, contar_palabras, contar_silabas, segmentar_frases
)
from app.core.logic.metrics.lexical_density import _STOPWORDS

# Expresión regular rápida para tokenizar (solo letras)
_RE_TOKENS = re.compile(r'[a-záéíóúüñ]+', re.IGNORECASE)

def calcular_metricas_base(slide_data, nombre_archivo) -> dict:
    """Calcula el FSZ y la DL pura de una diapositiva sin sumas ponderadas."""
    texto = preparar_texto_slide(slide_data)
    
    palabras = contar_palabras(texto)
    # Descartamos diapositivas vacías, portadas o índices (menos de 10 palabras)
    if palabras < 10:
        return None

    silabas = contar_silabas(texto)
    frases = segmentar_frases(texto)
    num_frases = len(frases) if frases else 1
    
    # 1. Componentes de Flesch (FSZ)
    prom_sil_pal = silabas / palabras
    prom_pal_fra = palabras / num_frases
    fsz = 206.835 - (62.3 * prom_sil_pal) - prom_pal_fra
    
    # 2. Densidad Léxica (DL)
    tokens = [t.lower() for t in _RE_TOKENS.findall(texto)]
    total_tokens = len(tokens)
    if total_tokens < 5: 
        return None
        
    funcionales = sum(1 for t in tokens if t in _STOPWORDS)
    contenido = total_tokens - funcionales
    dl = (contenido / total_tokens) * 100
    
    return {
        "Archivo": nombre_archivo,
        "Slide": slide_data.get("slide_number"),
        "Palabras": palabras,
        "Prom_Silabas/Palabra": round(prom_sil_pal, 2),
        "Prom_Palabras/Frase": round(prom_pal_fra, 2),
        "FSZ_Puro": round(fsz, 2),
        "DL_Pura_%": round(dl, 2)
    }

def procesar_archivo(ruta_archivo) -> list:
    """Extrae un PPTX y evalúa todas sus diapositivas."""
    nombre = Path(ruta_archivo).name
    try:
        data = extract_pptx_data(str(ruta_archivo))
        resultados_slides = []
        for slide in data["slides"]:
            res = calcular_metricas_base(slide, nombre)
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
    carpeta = filedialog.askdirectory(title="Selecciona la carpeta con las presentaciones PPTX de Nivel Superior")
    return carpeta

def calcular_y_mostrar_estadisticas(datos: list):
    """Calcula los cuartiles (el rango ideal) para las métricas evaluadas."""
    if not datos:
        print(f"{Fore.RED}No se obtuvieron datos suficientes para hacer estadística.")
        return

    fsz_vals = [d["FSZ_Puro"] for d in datos]
    dl_vals = [d["DL_Pura_%"] for d in datos]
    pal_fra_vals = [d["Prom_Palabras/Frase"] for d in datos]
    sil_pal_vals = [d["Prom_Silabas/Palabra"] for d in datos]

    print(f"\n{Fore.WHITE}{Style.BRIGHT}{'='*60}")
    print(f" RESUMEN DE CALIBRACIÓN: NIVEL SUPERIOR (MUESTRA: {len(datos)} diapositivas)")
    print(f"{'='*60}\n")
    print(f"{Fore.YELLOW}¿Cómo leer esto? El rango entre Q1 (Percentil 25) y Q3 (Percentil 75)")
    print(f"{Fore.YELLOW}representa el 50% central de tus datos, es decir, 'LO NORMAL'.\n")

    def print_stat(nombre, lista):
        # quantiles(n=4) devuelve [Q1, Mediana, Q3]
        try:
            q = statistics.quantiles(lista, n=4)
            q1, med, q3 = round(q[0], 2), round(q[1], 2), round(q[2], 2)
            print(f"{Fore.CYAN}>> {nombre}:")
            print(f"   Rango Más Popular (Q1 a Q3): {Fore.GREEN}{Style.BRIGHT}[ {q1}  ---  {q3} ]")
            print(f"   Mediana (Punto Central)  : {med}")
            print(f"   Mínimo: {min(lista)} | Máximo: {max(lista)}\n")
        except statistics.StatisticsError:
            print(f"{Fore.RED}>> {nombre}: Datos insuficientes para estadística.\n")

    print_stat("Índice Flesch (FSZ)", fsz_vals)
    print_stat("Densidad Léxica (DL %)", dl_vals)
    print_stat("Palabras por Frase (Longitud de oraciones)", pal_fra_vals)
    print_stat("Sílabas por Palabra (Tecnicismo del lenguaje)", sil_pal_vals)

def exportar_a_csv(datos: list, ruta_carpeta: str):
    """Guarda todos los datos en un Excel (CSV) en la carpeta analizada."""
    if not datos: return
    
    ruta_csv = os.path.join(ruta_carpeta, "Reporte_Calibracion_Nivel_Superior.csv")
    columnas = list(datos[0].keys())
    
    with open(ruta_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(datos)
        
    print(f"{Fore.GREEN}{Style.BRIGHT}¡Éxito! Se ha guardado el archivo detallado en:")
    print(f"{Fore.WHITE}{ruta_csv}")
    print(f"{Fore.YELLOW}Abre este archivo en Excel para crear gráficas y ver el detalle.")

def ejecutar_test():
    carpeta = seleccionar_carpeta()
    if not carpeta:
        print(f"{Fore.RED}No se seleccionó ninguna carpeta. Saliendo...")
        return
        
    archivos_pptx = list(Path(carpeta).rglob('*.pptx'))
    if not archivos_pptx:
        print(f"{Fore.RED}No se encontraron archivos .pptx en la carpeta seleccionada.")
        return

    print(f"\n{Fore.CYAN}Encontrados {len(archivos_pptx)} archivos PPTX. Iniciando análisis multihilo...\n")
    
    resultados_globales = []
    
    # Procesar archivos en paralelo (Muy rápido)
    with ThreadPoolExecutor() as executor:
        resultados_futuros = executor.map(procesar_archivo, archivos_pptx)
        
        for res_slide_list in resultados_futuros:
            resultados_globales.extend(res_slide_list)

    # Imprimir consola y exportar
    calcular_y_mostrar_estadisticas(resultados_globales)
    exportar_a_csv(resultados_globales, carpeta)

if __name__ == "__main__":
    ejecutar_test()