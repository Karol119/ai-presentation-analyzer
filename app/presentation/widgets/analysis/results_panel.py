# app/presentation/widgets/analysis/results_panel.py
"""
Panel derecho de la vista de análisis.
Muestra los resultados de evaluación de la diapositiva activa.
"""

import customtkinter as ctk
from app.presentation.views.ui_state import ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"


def build_results_panel(subject: str, nombre_presentacion: str):
    """
    Construye el panel derecho de resultados de análisis.
    Placeholder — se implementará en el paso 5.
    """
    panel = ctk.CTkFrame(
        ui["analysis_body"],
        fg_color="white",
        corner_radius=14,
        width=320,
        border_width=1,
        border_color="#E8ECF2",
    )
    panel.pack(side="right", fill="y", padx=(6, 12), pady=12)
    panel.pack_propagate(False)
    ui["results_panel"] = panel

    # Placeholder visual hasta el paso 5
    ctk.CTkLabel(
        panel,
        text="📈  Resultados de análisis\n(Paso 5)",
        font=ctk.CTkFont(family="Segoe UI", size=16),
        text_color="#94A3B8",
    ).place(relx=0.5, rely=0.5, anchor="center")