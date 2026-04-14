# app/presentation/views/analysis_gui.py
"""
Vista de análisis de presentaciones.

Espejo de main_gui.py para la pantalla de análisis.
Se construye bajo ui["root"] al mismo nivel que ui["body"],
pero solo es visible cuando el navigator lo activa.

Estructura:
    ui["analysis_body"]
        ├── presentation_panel  (izquierda: visor de diapositivas)
        └── results_panel       (derecha: resultados del análisis)
"""

import customtkinter as ctk
from app.presentation.views.ui_state import ui
from app.presentation.widgets.analysis.presentation_panel import build_presentation_panel, cerrar_pdf
from app.presentation.widgets.analysis.results_panel import build_results_panel

def mostrar_vista_analisis(subject: str, nombre_presentacion: str, ruta_pdf: str):
    """
    Construye y empaqueta la vista de análisis completa.
    Llamado exclusivamente por navigator.ir_a_analisis().
    """
    ui["analysis_body"] = ctk.CTkFrame(
        ui["root"],
        fg_color="#EEF2F7",
        corner_radius=0,
    )
    ui["analysis_body"].pack(fill="both", expand=True)

    build_presentation_panel(subject, nombre_presentacion, ruta_pdf)
    build_results_panel(subject, nombre_presentacion)


def ocultar_vista_analisis():
    """
    Destruye la vista de análisis y libera sus recursos.
    Llamado exclusivamente por navigator.ir_a_principal().
    """
    # 1. Liberamos el archivo PDF de la memoria de Windows
    cerrar_pdf()
    
    # 2. Destruimos los componentes visuales
    if "analysis_body" in ui and ui["analysis_body"].winfo_exists():
        ui["analysis_body"].destroy()
        del ui["analysis_body"]