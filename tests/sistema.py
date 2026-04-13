import sys
import os
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# Configuración de ruta para ESCOM
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logic.text_extractor import extraer_datos_pptx
from app.core.logic.slide_classifier import clasificar_diapositiva
from app.core.logic.metrics.icd import calcular_icd_presentacion
from app.core.logic.metrics.word_count import calcular_wps_presentacion
from app.core.logic.metrics.header_structure import calcular_hss_presentacion
from app.core.logic.metrics.narrative_thread import calcular_nts
from app.core.logic.presentation_score import calcular_score_global, calcular_score_slide
from app.infrastructure.ollama.ollama_service import verificar_conexion, clasificar_tipo_diapositiva
from app.infrastructure.ollama.coherencia_service import verificar_coherencia_titulo
from app.infrastructure.ollama.narrativa_service import verificar_hilo_narrativo

def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    return filedialog.askopenfilename(filetypes=[("PowerPoint", "*.pptx")])

def main():
    ruta = seleccionar_archivo()
    if not ruta: return

    llm_ok = verificar_conexion()
    datos = extraer_datos_pptx(ruta)
    
    slides_contenido = [s for s in datos["slides"] if not s.get("clasificacion", {}).get("excluir", False)]

    # 1. Definimos las funciones de Mistral si está activo
    fn_hss = verificar_coherencia_titulo if llm_ok else None
    fn_nts = verificar_hilo_narrativo if llm_ok else None
    
    # Ejecutar motores
    res_icd = calcular_icd_presentacion(slides_contenido)
    res_wps = calcular_wps_presentacion(slides_contenido)
    res_hss = calcular_hss_presentacion(slides_contenido, llm_fn=fn_hss) # <--- Agregar esto
    res_nts = calcular_nts(slides_contenido, llm_fn=fn_nts)

    sg = calcular_score_global(res_icd, res_wps, res_hss, res_nts)

    print(f"\n{'='*85}")
    print(f" DIAGNÓSTICO INTEGRAL: {Path(ruta).name}")
    print(f"{'='*85}")

    for s in slides_contenido:
        n = s["slide_number"]
        mi = next(r for r in res_icd["resultados"] if r["slide_number"] == n)
        mw = next(r for r in res_wps["resultados"] if r["slide_number"] == n)
        mh = next(r for r in res_hss["resultados"] if r["slide_number"] == n)
        # NUEVO: Extraer NTS individual
        mn = next(r for r in res_nts["resultados"] if r["slide_number"] == n)
        
        ss = calcular_score_slide(mi, mw, mh, mn)

        print(f"\n[DIAPOSITIVA {n:02d}] - Score: {ss['score']} ({ss['zona'].upper()})")
        print(f"  ├─ ICD: {mi['icd']} | Zona: {mi['zona']} (FSZ: {mi.get('fsz')})")
        print(f"  ├─ WPS: {mw['palabras']} / 75")
        print(f"  ├─ HSS: {mh['coherencia']} (Método: {mh['metodo_coherencia']})")
        
        # FIX: Uso de .get() para evitar errores si la clave falta por alguna razón
        sim_ant = mn.get('sim_anterior')
        print(f"  └─ NTS: {mn['estado']} (Puntos: {mn['nts_score']})")
        if sim_ant is not None:
            print(f"     (Lazo con anterior: {sim_ant})")

    print(f"\n{'='*85}")
    print(f" RESUMEN FINAL DE LA PRESENTACIÓN")
    print(f"{'='*85}")
    print(f" SCORE GLOBAL : {sg['score_global']} / 10.0")
    print(f" ZONA GLOBAL  : {sg['zona_global'].upper()}")
    print(f"{'-'*85}")
    print(f" DESGLOSE PONDERADO:")
    print(f"  • ICD (35%): {sg['scores_metrica']['icd']} pts")
    print(f"  • WPS (25%): {sg['scores_metrica']['wps']} pts")
    print(f"  • HSS (25%): {sg['scores_metrica']['hss']} pts")
    print(f"  • NTS (15%): {sg['scores_metrica']['nts']} pts")
    print(f"{'='*85}\n")

if __name__ == "__main__":
    main()