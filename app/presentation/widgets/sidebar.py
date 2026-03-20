# app/presentation/widgets/sidebar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

# Paleta IPN
COLOR_GUINDA = "#6A1B31"
COLOR_GUINDA_SUAVE = "#F4E7EA"  # Guinda con opacidad para fondo activo
COLOR_ORO = "#BC955C"
COLOR_BORDE = "#E2E8F0"

def build_left_sidebar(comando_abrir_modal, comando_seleccionar, comando_eliminar):
    """
    Construye la barra lateral izquierda (Lista de Materias - Estilo IPN).
    """
    ui["left_sidebar"] = ctk.CTkFrame(
        ui["body"], fg_color="white", corner_radius=0, width=220,
        border_width=1, border_color=COLOR_BORDE,
    )
    ui["left_sidebar"].pack(side="left", fill="y")
    ui["left_sidebar"].pack_propagate(False)

    # Título de sección
    ctk.CTkLabel(
        ui["left_sidebar"], text="MIS MATERIAS",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), 
        text_color="#94A3B8",
    ).pack(anchor="w", padx=20, pady=(20, 10))

    # Lista de materias con scroll
    ui["sidebar_list"] = ctk.CTkScrollableFrame(
        ui["left_sidebar"], fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#CBD5E1",
    )
    ui["sidebar_list"].pack(fill="both", expand=True, padx=8)

    # Generar items iniciales
    for s in estado["subjects"]:
        create_sidebar_item(s, comando_seleccionar, comando_eliminar)

    # Divisor inferior
    ctk.CTkFrame(ui["left_sidebar"], height=1, fg_color=COLOR_BORDE,
                 corner_radius=0).pack(fill="x", pady=10)

    # Botón Agregar Materia (Estilo institucional)
    add_btn = ctk.CTkButton(
        ui["left_sidebar"], text="＋  Agregar materia",
        font=ctk.CTkFont(size=12, weight="bold"),
        fg_color="transparent", hover_color="#F8FAFC",
        text_color=COLOR_GUINDA, border_width=1, border_color=COLOR_GUINDA,
        corner_radius=8, height=38, anchor="center",
        command=comando_abrir_modal,
    )
    add_btn.pack(fill="x", padx=15, pady=(0, 20))

def create_sidebar_item(name: str, comando_seleccionar, comando_eliminar):
    """Crea un elemento individual en la lista con lógica de estado activo."""
    is_active = (name == estado["active"])
    
    row = ctk.CTkFrame(
        ui["sidebar_list"],
        fg_color=COLOR_GUINDA_SUAVE if is_active else "transparent",
        corner_radius=8, height=44, cursor="hand2",
    )
    row.pack(fill="x", pady=3)
    row.pack_propagate(False)

    # Indicador vertical izquierdo (Guinda)
    indicator = ctk.CTkFrame(
        row, width=4,
        fg_color=COLOR_GUINDA if is_active else "transparent",
        corner_radius=2,
    )
    indicator.pack(side="left", fill="y", padx=(2, 0), pady=8)

    # Etiqueta de la materia
    label = ctk.CTkLabel(
        row, text=name,
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold" if is_active else "normal"),
        text_color=COLOR_GUINDA if is_active else "#475569",
        anchor="w",
    )
    label.pack(side="left", fill="both", expand=True, padx=12)

    # Insignia (Badge) de conteo (Oro)
    badge_var = ctk.StringVar(value="")
    badge = ctk.CTkLabel(
        row, textvariable=badge_var,
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color="white",
        fg_color=COLOR_ORO,
        corner_radius=10, width=24, height=18,
    )
    # El badge se muestra/oculta en refresh_badge
    badge.pack(side="right", padx=(0, 6))
    badge.pack_forget()

    # Botón de eliminación rápida
    close = ctk.CTkButton(
        row, text="✕", width=20, height=20,
        font=ctk.CTkFont(size=9, weight="bold"),
        fg_color="transparent", hover_color="#FEE2E2",
        text_color="#CBD5E1", corner_radius=10,
        command=lambda n=name: comando_eliminar(n),
    )
    close.pack(side="right", padx=(0, 6))

    # Guardar referencias para actualizaciones dinámicas
    row._indicator = indicator
    row._label = label
    row._badge = badge
    row._badge_var = badge_var

    # Eventos de clic
    for w in (row, label):
        w.bind("<Button-1>", lambda e, n=name: comando_seleccionar(n))

    ui["sidebar_btns"][name] = row
    refresh_badge(name)

def refresh_badge(name: str):
    """Actualiza el número de archivos usando los datos de la BD/Estado."""
    row = ui["sidebar_btns"].get(name)
    if not row: return
    
    count = len(estado["subject_files"].get(name, []))
    if count > 0:
        row._badge_var.set(str(count))
        row._badge.pack(side="right", padx=(0, 6))
    else:
        row._badge.pack_forget()

def refresh_sidebar_styles():
    """Refresca visualmente toda la sidebar cuando cambia la materia activa."""
    for n, row in ui["sidebar_btns"].items():
        a = (n == estado["active"])
        row.configure(fg_color=COLOR_GUINDA_SUAVE if a else "transparent")
        row._indicator.configure(fg_color=COLOR_GUINDA if a else "transparent")
        row._label.configure(
            text_color=COLOR_GUINDA if a else "#475569",
            font=ctk.CTkFont(size=13, weight="bold" if a else "normal"),
        )