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
from app.infrastructure.ollama.diagnostic_service import generar_diagnostico_metrico
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

    # --- 1. CLASIFICACIÓN ---
    for s in datos["slides"]:
        s["clasificacion"] = clasificar_diapositiva(
            s,
            llm_fn=clasificar_tipo_diapositiva if llm_ok else None
        )

    slides_contenido = [s for s in datos["slides"] if not s.get("clasificacion", {}).get("excluir", False)]

    # --- 2. MÉTRICAS ---
    res_icd = calcular_icd_presentacion(slides_contenido)
    res_wps = calcular_wps_presentacion(slides_contenido)
    res_hss = calcular_hss_presentacion(slides_contenido, llm_fn=verificar_coherencia_titulo if llm_ok else None)
    res_nts = calcular_nts(slides_contenido, llm_fn=verificar_hilo_narrativo if llm_ok else None)

    sg = calcular_score_global(res_icd, res_wps, res_hss, res_nts)

    print(f"\n{'='*85}\n DIAGNÓSTICO INTEGRAL: {Path(ruta).name}\n{'='*85}")

    # --- 3. BUCLE DE DIAGNÓSTICO ---
    for idx, s in enumerate(slides_contenido):
        n    = s["slide_number"]
        clas = s.get("clasificacion", {})

        if clas.get("tipo") in ["portada", "indice", "referencias", "cierre"]:
            print(f"\n[DIAPOSITIVA {n:02d}] - TIPO: {clas['tipo'].upper()} (Omitida)")
            continue

        mi = next((r for r in res_icd["resultados"] if r["slide_number"] == n), {})
        mw = next((r for r in res_wps["resultados"] if r["slide_number"] == n), {})
        mh = next((r for r in res_hss["resultados"] if r["slide_number"] == n), {})
        mn = next((r for r in res_nts["resultados"] if r["slide_number"] == n), {})

        ss = calcular_score_slide(mi, mw, mh, mn)

        print(f"\n┌─ EVALUACIÓN DIAPOSITIVA {n:02d} {'─'*30}")
        print(f"│ Score: {ss['score']} | Estado: {ss['zona'].upper()}")
        print(f"├{'─'*55}")

        if ss['necesita_recomendacion'] and llm_ok:
            # Contexto NTS: texto plano de la slide anterior y siguiente (si existen)
            slide_prev_texto = (
                " ".join(slides_contenido[idx - 1].get("content", []))
                if idx > 0 else None
            )
            slide_next_texto = (
                " ".join(slides_contenido[idx + 1].get("content", []))
                if idx < len(slides_contenido) - 1 else None
            )

            # ✅ Una sola llamada por slide
            feedback = generar_diagnostico_metrico(
                slide_data = s,
                metricas   = ss['metricas'],
                slide_prev = slide_prev_texto,
                slide_next = slide_next_texto,
            )

            if "icd" in ss['aspectos_mejorar']:
                print(f"│ 🧠 COMPLEJIDAD  (ICD: {mi.get('icd', 'N/A')})")
                print(f"│    {feedback.get('icd', 'Ajustar nivel técnico.')}")

            if "wps" in ss['aspectos_mejorar']:
                print(f"│ 📝 PALABRAS     (WPS: {mw.get('palabras', 'N/A')})")
                print(f"│    {feedback.get('wps', 'Reducir texto.')}")

            if "hss" in ss['aspectos_mejorar']:
                print(f"│ 🏗️  ESTRUCTURA   (HSS)")
                print(f"│    {feedback.get('hss', 'Revisar título.')}")

            if "nts" in ss['aspectos_mejorar']:
                print(f"│ 🔗 NARRATIVA    (NTS)")
                print(f"│    {feedback.get('nts', 'Mejorar conexión temática.')}")
        else:
            print(f"│ ✅ Diapositiva en rango óptimo. No se requieren ajustes.")

        # ✅ El cierre va SIEMPRE al final, fuera del if/else
        print(f"└{'─'*55}")

    # --- 4. RESUMEN FINAL ---
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