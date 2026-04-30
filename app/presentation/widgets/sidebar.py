# app/presentation/widgets/sidebar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

# Colores Institucionales del IPN y complementarios
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

# Ancho de envoltura del nombre de materia.
# Sidebar = 240 px. Restamos: indicador (4) + paddings + botón borrar (~28)
# + scrollbar y márgenes internos del scroll frame.
# Sin badge hay un poco más de espacio horizontal disponible.
WRAP_NAME = 135


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
    Crea una fila individual para una materia. Usa grid interno para que el
    nombre pueda envolverse en varias líneas y el botón de borrar quede
    siempre alineado a la derecha sin tapar el texto.
    """
    is_active = name == estado["active"]

    # Sin altura fija ni pack_propagate(False): la fila crece con el
    # contenido cuando el nombre necesita 2 líneas.
    row = ctk.CTkFrame(
        ui["sidebar_list"],
        fg_color=COLOR_GUINDA_SUAVE if is_active else "transparent",
        corner_radius=10,
        cursor="hand2",
    )
    row.pack(fill="x", pady=2)

    # Layout interno con grid:
    # col 0 = indicador (barra guinda izquierda)
    # col 1 = nombre (expansible, con wrap)
    # col 2 = botón borrar
    row.grid_columnconfigure(0, minsize=8)
    row.grid_columnconfigure(1, weight=1)
    row.grid_columnconfigure(2, minsize=0)

    # Indicador visual de selección (barra lateral izquierda)
    indicator = ctk.CTkFrame(
        row,
        width=4,
        height=28,
        fg_color=COLOR_GUINDA if is_active else "transparent",
        corner_radius=2,
    )
    indicator.grid(row=0, column=0, sticky="ns", padx=(4, 0), pady=8)

    # Nombre de la materia (con wraplength para nombres largos)
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
        justify="left",
        wraplength=WRAP_NAME,
    )
    label.grid(row=0, column=1, sticky="ew", padx=10, pady=8)

    # Botón de eliminar (🗑) - único, anclado a la derecha
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
    close.grid(row=0, column=2, padx=(0, 8), pady=8)

    # Guardar referencias en el objeto row para acceso rápido
    row._indicator = indicator
    row._label     = label
    row._close     = close

    # --- LÓGICA DE INTERACCIÓN (Selección) ---
    for w in (row, label):
        w.bind("<Button-1>", lambda e, n=name: comando_seleccionar(n))

    ui["sidebar_btns"][name] = row


def refresh_badge(name: str):
    """
    Stub conservado por compatibilidad: el badge contador fue removido
    de la interfaz. Se mantiene la firma para no romper llamadas externas
    que pudieran existir en otros módulos.
    """
    return


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