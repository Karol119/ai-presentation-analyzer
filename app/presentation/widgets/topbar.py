# app/presentation/widgets/topbar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

def build_topbar(comando_toggle, comando_analyze):
    """
    Construye la barra superior de la aplicación.
    Recibe las funciones a ejecutar (callbacks) para no acoplar la lógica aquí.
    """
    bar = ctk.CTkFrame(ui["root"], fg_color="white", corner_radius=0, height=56)
    bar.pack(fill="x")
    bar.pack_propagate(False)

    ctk.CTkLabel(
        bar, text="Prototipo 01. Cargar una presentación",
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color="#0F172A",
    ).pack(side="left", padx=24)

    # Botón de Toggle
    ui["toggle_btn"] = ctk.CTkButton(
        bar, text="☰  Contenido", font=ctk.CTkFont(size=12),
        fg_color="#EFF6FF", hover_color="#DBEAFE", text_color="#2563EB",
        border_width=1, border_color="#BFDBFE", corner_radius=8, height=32,
        command=comando_toggle,
    )
    ui["toggle_btn"].pack(side="right", padx=(8, 24), pady=12)

    # Botón de Analizar
    ui["analyze_btn"] = ctk.CTkButton(
        bar, text="Analizar presentación", font=ctk.CTkFont(size=13, weight="bold"),
        fg_color="#94A3B8", hover_color="#64748B", text_color="white",
        corner_radius=8, height=36, state="disabled", command=comando_analyze,
    )
    ui["analyze_btn"].pack(side="right", padx=(24, 4), pady=10)

    ctk.CTkFrame(ui["root"], height=1, fg_color="#E2E8F0", corner_radius=0).pack(fill="x")