# app/presentation/widgets/topbar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"
COLOR_ORO_HOVER    = "#9E7C4A"


def build_topbar(comando_toggle):
    bar = ctk.CTkFrame(ui["root"], fg_color="white", corner_radius=0, height=68)
    bar.pack(fill="x")
    bar.pack_propagate(False)

    logo_frame = ctk.CTkFrame(bar, fg_color="transparent")
    logo_frame.pack(side="left", padx=28, pady=0)

    pill = ctk.CTkFrame(logo_frame, fg_color=COLOR_GUINDA, corner_radius=8,
                        width=42, height=28)
    pill.pack(side="left", padx=(0, 12))
    pill.pack_propagate(False)
    ctk.CTkLabel(pill, text="IPN",
                 font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                 text_color="white").place(relx=0.5, rely=0.5, anchor="center")

    text_col = ctk.CTkFrame(logo_frame, fg_color="transparent")
    text_col.pack(side="left")
    ctk.CTkLabel(text_col,
                 text="AI Presentation Analyzer",
                 font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
                 text_color="#1E293B").pack(anchor="w")
    ctk.CTkLabel(text_col,
                 text="ESCOM · Prototipo 1: Análisis de presentaciones",
                 font=ctk.CTkFont(family="Segoe UI", size=10),
                 text_color="#94A3B8").pack(anchor="w")

    btn_frame = ctk.CTkFrame(bar, fg_color="transparent")
    btn_frame.pack(side="right", padx=28)

    ui["toggle_btn"] = ctk.CTkButton(
        btn_frame,
        text="☰   Contenido",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        fg_color="transparent",
        hover_color="#F1F5F9",
        text_color="#64748B",
        border_width=1,
        border_color="#E2E8F0",
        corner_radius=20,
        height=36,
        width=130,
        command=comando_toggle,
    )
    ui["toggle_btn"].pack(side="left", padx=(0, 10))

    ctk.CTkFrame(ui["root"], height=1, fg_color="#E8ECF2").pack(fill="x")