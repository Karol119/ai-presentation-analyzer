# app/presentation/widgets/analysis/presentation_panel.py
"""
Panel izquierdo de la vista de análisis.
Muestra las diapositivas de la presentación y permite navegar entre ellas.
"""

import customtkinter as ctk
from app.presentation.views.ui_state import ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"


def build_presentation_panel(subject: str, nombre_presentacion: str):
    """
    Construye el panel izquierdo del visor de diapositivas.
    Placeholder — se implementará en el paso 4.
    """
    panel = ctk.CTkFrame(
        ui["analysis_body"],
        fg_color="white",
        corner_radius=14,
        border_width=1,
        border_color="#E8ECF2",
    )
    panel.pack(side="left", fill="both", expand=True, padx=(12, 6), pady=12)
    ui["presentation_panel"] = panel

    # Placeholder visual hasta el paso 4
    ctk.CTkLabel(
        panel,
        text="📊  Visor de diapositivas\n(Paso 4)",
        font=ctk.CTkFont(family="Segoe UI", size=16),
        text_color="#94A3B8",
    ).place(relx=0.5, rely=0.5, anchor="center")