# app/presentation/widgets/right_panel.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui
# ✅ Arquitectura: Comunicación exclusiva con el controlador de negocio
from app.core.controller.subject_controller import obtener_temario_completo

# Colores Institucionales ESCOM/IPN
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

# Anchos de envoltura para texto (panel = 270 px)
WRAP_UNIT    = 210
WRAP_TEMA    = 195
WRAP_SUBTEMA = 180


def build_right_panel():
    """Construye el panel lateral derecho para visualizar el temario."""
    ui["right_panel"] = ctk.CTkFrame(
        ui["body"],
        fg_color="white",
        corner_radius=14,
        width=270,
        border_width=1,
        border_color="#E8ECF2",
    )
    ui["right_panel"].pack(side="right", fill="y", padx=(0, 12), pady=12)
    ui["right_panel"].pack_propagate(False)

    # --- Encabezado ---
    header = ctk.CTkFrame(ui["right_panel"], fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(16, 10))

    icon_bg = ctk.CTkFrame(header, fg_color=COLOR_GUINDA_SUAVE,
                           corner_radius=8, width=30, height=30)
    icon_bg.pack(side="left", padx=(0, 10))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="📖", font=ctk.CTkFont(size=14),
                 text_color=COLOR_GUINDA).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        header,
        text="Contenido del curso",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(side="left")

    ctk.CTkFrame(ui["right_panel"], height=1, fg_color="#F1F5F9").pack(
        fill="x", padx=16, pady=(0, 10)
    )

    # Scroll para el árbol de temas
    ui["tree_scroll"] = ctk.CTkScrollableFrame(
        ui["right_panel"],
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    ui["tree_scroll"].pack(fill="both", expand=True, padx=12, pady=(0, 14))

    refresh_right_panel(estado["active"])


def refresh_right_panel(subject: str):
    """Recarga el árbol de contenido (estático, sin expand/collapse)."""
    for w in ui["tree_scroll"].winfo_children():
        w.destroy()

    if not subject:
        return

    units = obtener_temario_completo(subject)

    if not units:
        ctk.CTkLabel(
            ui["tree_scroll"],
            text="Sin contenido registrado.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="#94A3B8",
        ).pack(pady=40, padx=16)
        return

    for unit_data in units:
        _add_unit_row(ui["tree_scroll"], unit_data)


# --- Filas estáticas (sin lógica de expand/collapse) ---


def _add_unit_row(parent, unit_data):
    """Añade una Unidad Temática (Nivel 1)."""
    # Píldora con fondo guinda suave
    unit_row = ctk.CTkFrame(parent, fg_color=COLOR_GUINDA_SUAVE, corner_radius=8)
    unit_row.pack(fill="x", pady=(6, 2))

    ctk.CTkLabel(
        unit_row,
        text=unit_data["unidad"],
        anchor="w",
        justify="left",
        wraplength=WRAP_UNIT,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(fill="x", padx=12, pady=6)

    # Los temas y subtemas se agregan al mismo parent (tree_scroll),
    # para que todo fluya de corrido sin contenedores anidados.
    for tema_data in unit_data["temas"]:
        _add_tema_row(parent, tema_data)


def _add_tema_row(parent, tema_data):
    """Añade un Tema (Nivel 2)."""
    tema_row = ctk.CTkFrame(parent, fg_color="transparent")
    tema_row.pack(fill="x", pady=(2, 0))
    # Col 0 = sangría; Col 1 = label expansible
    tema_row.grid_columnconfigure(0, minsize=14)
    tema_row.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        tema_row,
        text=tema_data["tema"],
        anchor="w",
        justify="left",
        wraplength=WRAP_TEMA,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#334155",
    ).grid(row=0, column=1, sticky="ew", padx=(4, 4), pady=2)

    for sub in tema_data["subtemas"]:
        _add_subtema_row(parent, sub)


def _add_subtema_row(parent, text):
    """Añade un Subtema (Nivel 3)."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=(1, 0))
    # Col 0 = sangría; Col 1 = bullet; Col 2 = label expansible
    row.grid_columnconfigure(0, minsize=28)
    row.grid_columnconfigure(1, minsize=14)
    row.grid_columnconfigure(2, weight=1)

    # Bullet con tamaño explícito (evita el default 200x200 de CTkFrame)
    dot = ctk.CTkFrame(row, width=5, height=5, corner_radius=3, fg_color=COLOR_ORO)
    dot.grid(row=0, column=1, sticky="nw", pady=(7, 0))

    ctk.CTkLabel(
        row,
        text=text,
        anchor="w",
        justify="left",
        wraplength=WRAP_SUBTEMA,
        text_color="#64748B",
        font=ctk.CTkFont(family="Segoe UI", size=10),
    ).grid(row=0, column=2, sticky="ew", padx=(0, 4), pady=1)