# app/presentation/widgets/topbar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"
COLOR_ORO_HOVER    = "#9E7C4A"

# Referencias internas para los widgets intercambiables del topbar
_analysis_frame = None   # Frame con título + botón "Volver a inicio" (modo análisis)
_main_frame     = None   # Frame con botón "☰ Contenido" (modo principal)


def build_topbar(comando_toggle):
    """
    Construye el topbar completo. Crea ambos modos (principal y análisis)
    pero solo muestra el modo principal al arrancar.
    """
    global _analysis_frame, _main_frame

    bar = ctk.CTkFrame(ui["root"], fg_color="white", corner_radius=0, height=68)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    ui["topbar"] = bar  # Guardamos referencia para acceso externo

    # --- LADO IZQUIERDO: Logo IPN (siempre visible) ---
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

    # --- LADO DERECHO: Zona intercambiable según el modo activo ---

    # MODO PRINCIPAL: botón "☰ Contenido"
    _main_frame = ctk.CTkFrame(bar, fg_color="transparent")
    _main_frame.pack(side="right", padx=28)

    ui["toggle_btn"] = ctk.CTkButton(
        _main_frame,
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

    # MODO ANÁLISIS: título de la presentación + botón "Volver a inicio"
    # Se crea aquí pero permanece oculto hasta que se llame a set_modo_analisis()
    _analysis_frame = ctk.CTkFrame(bar, fg_color="transparent")
    # No se empaqueta aún — arranca oculto

    ui["analysis_title_label"] = ctk.CTkLabel(
        _analysis_frame,
        text="",   # Se rellena dinámicamente en set_modo_analisis()
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#475569",
    )
    ui["analysis_title_label"].pack(side="left", padx=(0, 20))

    ui["back_btn"] = ctk.CTkButton(
        _analysis_frame,
        text="← Volver a inicio",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        text_color="white",
        corner_radius=20,
        height=36,
        width=160,
        command=lambda: None,  # Se asigna dinámicamente en set_modo_analisis()
    )
    ui["back_btn"].pack(side="left")

    # Separador inferior (siempre visible)
    ctk.CTkFrame(ui["root"], height=1, fg_color="#E8ECF2").pack(fill="x")


def set_modo_analisis(nombre_presentacion: str, on_back):
    """
    Cambia el topbar al modo análisis:
    - Oculta el botón '☰ Contenido'
    - Muestra el título de la presentación y el botón 'Volver a inicio'
    """
    global _main_frame, _analysis_frame

    # Actualizar contenido dinámico antes de mostrarlo
    ui["analysis_title_label"].configure(text=f"Análisis · {nombre_presentacion}")
    ui["back_btn"].configure(command=on_back)

    # Intercambiar frames
    _main_frame.pack_forget()
    _analysis_frame.pack(side="right", padx=28)


def set_modo_principal():
    """
    Restaura el topbar al modo principal:
    - Oculta el título y botón 'Volver a inicio'
    - Muestra el botón '☰ Contenido'
    """
    global _main_frame, _analysis_frame

    _analysis_frame.pack_forget()
    _main_frame.pack(side="right", padx=28)