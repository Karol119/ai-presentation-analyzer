# app/presentation/widgets/sidebar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

# Colores Institucionales del IPN y complementarios
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

def build_left_sidebar(comando_abrir_modal, comando_seleccionar, comando_eliminar):
    """
    Construye la barra lateral izquierda que contiene el catálogo de materias activas.
    """
    ui["left_sidebar"] = ctk.CTkFrame(
        ui["body"],
        fg_color="white",
        corner_radius=14,
        width=240,
        border_width=1,
        border_color="#E8ECF2",
    )
    ui["left_sidebar"].pack(side="left", fill="y", padx=12, pady=12)
    ui["left_sidebar"].pack_propagate(False)

    # --- ENCABEZADO "MIS MATERIAS" ---
    header = ctk.CTkFrame(ui["left_sidebar"], fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(18, 8))
    ctk.CTkLabel(
        header,
        text="MIS MATERIAS",
        font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
        text_color="#94A3B8",
    ).pack(anchor="w")

    ctk.CTkFrame(ui["left_sidebar"], height=1, fg_color="#F1F5F9").pack(
        fill="x", padx=16, pady=(0, 6)
    )

    # --- LISTA DESPLAZABLE DE MATERIAS ---
    ui["sidebar_list"] = ctk.CTkScrollableFrame(
        ui["left_sidebar"],
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color="#E2E8F0",
        border_width=0,
    )
    ui["sidebar_list"].pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # Generar items para cada materia en el estado
    for s in estado["subjects"]:
        create_sidebar_item(s, comando_seleccionar, comando_eliminar)

    # --- BOTÓN INFERIOR PARA AGREGAR MATERIA ---
    ctk.CTkFrame(ui["left_sidebar"], height=1, fg_color="#F1F5F9").pack(
        fill="x", padx=16, pady=(0, 10)
    )
    add_btn = ctk.CTkButton(
        ui["left_sidebar"],
        text="＋  Agregar materia",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        fg_color="transparent",
        hover_color=COLOR_GUINDA_SUAVE,
        text_color=COLOR_GUINDA,
        border_width=1,
        border_color="#E2C5CF",
        corner_radius=10,
        height=38,
        command=comando_abrir_modal,
    )
    add_btn.pack(fill="x", padx=14, pady=(0, 14))


def create_sidebar_item(name, comando_seleccionar, comando_eliminar):
    """
    Crea una fila individual para una materia con soporte de hover para eliminación.
    """
    is_active = name == estado["active"]

    row = ctk.CTkFrame(
        ui["sidebar_list"],
        fg_color=COLOR_GUINDA_SUAVE if is_active else "transparent",
        corner_radius=10,
        height=44,
        cursor="hand2",
    )
    row.pack(fill="x", pady=2)
    row.pack_propagate(False)

    # Indicador visual de selección (barra lateral izquierda)
    indicator = ctk.CTkFrame(
        row,
        width=4,
        fg_color=COLOR_GUINDA if is_active else "transparent",
        corner_radius=2,
    )
    indicator.pack(side="left", fill="y", padx=(4, 0), pady=10)

    # Badge contador de presentaciones
    badge_var = ctk.StringVar(value="")
    badge = ctk.CTkLabel(
        row,
        textvariable=badge_var,
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color="white",
        fg_color=COLOR_ORO,
        corner_radius=10,
        width=22,
        height=18,
    )
    # El badge se empaqueta si hay archivos (refresh_badge se encarga)
    badge.pack(side="right", padx=(0, 4))
    badge.pack_forget()

    # Botón de eliminar (🗑) - Siempre visible, anclado a la derecha
    close = ctk.CTkButton(
        row,
        text="🗑",
        width=28,
        height=28,
        font=ctk.CTkFont(size=13),
        fg_color="#FEF2F2",
        hover_color="#FECACA",
        text_color="#F87171",
        border_width=1,
        border_color="#FECACA",
        corner_radius=8,
        command=lambda n=name: comando_eliminar(n),
    )
    # Se empaqueta ANTES del label para que el layout reserve su espacio
    close.pack(side="right", padx=(0, 8))

    # Nombre de la materia
    label = ctk.CTkLabel(
        row,
        text=name,
        font=ctk.CTkFont(
            family="Segoe UI",
            size=13,
            weight="bold" if is_active else "normal",
        ),
        text_color=COLOR_GUINDA if is_active else "#475569",
        anchor="w",
    )
    label.pack(side="left", fill="both", expand=True, padx=10)

    # Botón de eliminar (🗑) - Siempre visible, anclado a la derecha
    close = ctk.CTkButton(
        row,
        text="🗑",
        width=28,
        height=28,
        font=ctk.CTkFont(size=13),
        fg_color="#FEF2F2",
        hover_color="#FECACA",
        text_color="#F87171",
        border_width=1,
        border_color="#FECACA",
        corner_radius=8,
        command=lambda n=name: comando_eliminar(n),
    )
    # Se empaqueta ANTES del label para que el layout reserve su espacio
    close.pack(side="right", padx=(0, 8))

    # Guardar referencias en el objeto row para acceso rápido
    row._indicator = indicator
    row._label     = label
    row._badge     = badge
    row._badge_var = badge_var
    row._close     = close

    # --- LÓGICA DE INTERACCIÓN (Selección) ---
    for w in (row, label):
        w.bind("<Button-1>", lambda e, n=name: comando_seleccionar(n))

    ui["sidebar_btns"][name] = row
    refresh_badge(name)


def refresh_badge(name: str):
    """Actualiza el número de presentaciones mostrado en el badge de la materia."""
    row = ui["sidebar_btns"].get(name)
    if not row:
        return
    # Contar archivos en el estado global
    count = len(estado["subject_files"].get(name, []))
    if count > 0:
        row._badge_var.set(str(count))
        # Asegurar que el badge sea visible
        row._badge.pack(side="right", padx=(0, 6))
    else:
        row._badge.pack_forget()


def refresh_sidebar_styles():
    """Actualiza los colores de toda la lista para reflejar la materia activa."""
    for n, row in ui["sidebar_btns"].items():
        active = n == estado["active"]
        row.configure(fg_color=COLOR_GUINDA_SUAVE if active else "transparent")
        row._indicator.configure(
            fg_color=COLOR_GUINDA if active else "transparent"
        )
        row._label.configure(
            text_color=COLOR_GUINDA if active else "#475569",
            font=ctk.CTkFont(
                family="Segoe UI",
                size=13,
                weight="bold" if active else "normal",
            ),
        )