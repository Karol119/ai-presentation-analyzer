# app/presentation/widgets/topbar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

# Paleta Institucional IPN
COLOR_GUINDA = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO = "#BC955C"
COLOR_ORO_HOVER = "#9E7C4A"
COLOR_BORDE = "#E2E8F0"

def build_topbar(comando_toggle, comando_analyze):
    """
    Construye la barra superior de la aplicación con estilo ESCOM/IPN.
    """
    # Contenedor principal de la barra
    bar = ctk.CTkFrame(ui["root"], fg_color="white", corner_radius=0, height=60)
    bar.pack(fill="x")
    bar.pack_propagate(False)

    # Título del Prototipo
    ctk.CTkLabel(
        bar, text="AI Presentation Analyzer — Prototipo 01",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color=COLOR_GUINDA, # Texto en Guinda
    ).pack(side="left", padx=24)

    # Botón de Toggle Contenido (Estilo Oro)
    ui["toggle_btn"] = ctk.CTkButton(
        bar, text="☰   Contenido", 
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        fg_color="transparent", 
        hover_color="#F8FAFC", 
        text_color="#64748B",
        border_width=1, 
        border_color="#CBD5E1", 
        corner_radius=8, 
        height=34,
        command=comando_toggle,
    )
    ui["toggle_btn"].pack(side="right", padx=(12, 24), pady=12)

    # Botón de Analizar (Estilo Guinda)
    ui["analyze_btn"] = ctk.CTkButton(
        bar, text="Analizar presentación", 
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        fg_color=COLOR_GUINDA, 
        hover_color=COLOR_GUINDA_HOVER, 
        text_color="white",
        corner_radius=8, 
        height=38, 
        state="disabled", 
        command=comando_analyze,
    )
    ui["analyze_btn"].pack(side="right", padx=(24, 0), pady=10)

    # Línea divisoria inferior
    ctk.CTkFrame(ui["root"], height=1, fg_color=COLOR_BORDE, corner_radius=0).pack(fill="x")