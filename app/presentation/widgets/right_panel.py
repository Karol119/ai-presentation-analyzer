# app/presentation/widgets/right_panel.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui
# ✅ Arquitectura: Comunicación exclusiva con el controlador de negocio
from app.core.controller.subject_controller import obtener_temario_completo

# Colores Institucionales ESCOM/IPN
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"

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
    """Recarga el árbol de contenido asegurando que los elementos se apilen arriba."""
    for w in ui["tree_scroll"].winfo_children():
        w.destroy()

    if not subject:
        return

    # ✅ CONTENEDOR MAESTRO: Forzamos el anclaje al norte para eliminar espacios muertos
    master_container = ctk.CTkFrame(ui["tree_scroll"], fg_color="transparent")
    master_container.pack(fill="both", expand=True, anchor="n")

    # Obtención de datos a través de la Capa de Negocio
    units = obtener_temario_completo(subject)

    if not units:
        ctk.CTkLabel(
            master_container,
            text="Sin contenido registrado.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="#94A3B8",
        ).pack(pady=40, padx=16, anchor="n")
        return

    for unit_data in units:
        _add_unit_row(master_container, unit_data)


# --- Lógica de Filas Jerárquicas ---

def _add_unit_row(parent, unit_data):
    """Añade una Unidad Temática (Nivel 1)."""
    expanded = {"v": True}
    
    # Frame de grupo para mantener la unidad y sus hijos pegados
    group = ctk.CTkFrame(parent, fg_color="transparent")
    group.pack(fill="x", anchor="n")

    unit_row = ctk.CTkFrame(group, fg_color=COLOR_GUINDA_SUAVE, corner_radius=8, height=34)
    unit_row.pack(fill="x", pady=(4, 0), anchor="n")
    unit_row.pack_propagate(False)

    children_frame = ctk.CTkFrame(group, fg_color="transparent")
    children_frame.pack(fill="x", anchor="n")

    def toggle():
        expanded["v"] = not expanded["v"]
        arrow.configure(text="▼" if expanded["v"] else "▶")
        if expanded["v"]:
            children_frame.pack(fill="x", anchor="n")
        else:
            children_frame.pack_forget()

    arrow = ctk.CTkLabel(unit_row, text="▼", width=22, text_color=COLOR_ORO,
                         font=ctk.CTkFont(size=10, weight="bold"), cursor="hand2")
    arrow.pack(side="left", padx=(8, 0))
    arrow.bind("<Button-1>", lambda e: toggle())

    label = ctk.CTkLabel(unit_row, text=unit_data["unidad"], anchor="w", cursor="hand2",
                         font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                         text_color=COLOR_GUINDA)
    label.pack(side="left", fill="x", expand=True, padx=6)
    label.bind("<Button-1>", lambda e: toggle())

    for tema_data in unit_data["temas"]:
        _add_tema_row(children_frame, tema_data)


def _add_tema_row(parent, tema_data):
    """Añade un Tema (Nivel 2)."""
    expanded = {"v": True}
    
    group = ctk.CTkFrame(parent, fg_color="transparent")
    group.pack(fill="x", anchor="n")

    tema_row = ctk.CTkFrame(group, fg_color="transparent", height=28)
    tema_row.pack(fill="x", pady=(2, 0), anchor="n")
    tema_row.pack_propagate(False)

    sub_frame = ctk.CTkFrame(group, fg_color="transparent")
    sub_frame.pack(fill="x", anchor="n")

    def toggle():
        expanded["v"] = not expanded["v"]
        arrow.configure(text="▼" if expanded["v"] else "▶")
        if expanded["v"]:
            sub_frame.pack(fill="x", anchor="n")
        else:
            sub_frame.pack_forget()

    # Sangría y línea guía
    ctk.CTkFrame(tema_row, width=20, fg_color="transparent").pack(side="left")
    ctk.CTkFrame(tema_row, width=2, fg_color="#E8ECF2").pack(side="left", fill="y", pady=6)

    arrow = ctk.CTkLabel(tema_row, text="▼", width=18, text_color=COLOR_ORO,
                         font=ctk.CTkFont(size=9), cursor="hand2")
    arrow.pack(side="left", padx=(4, 0))
    arrow.bind("<Button-1>", lambda e: toggle())

    label = ctk.CTkLabel(tema_row, text=tema_data["tema"], anchor="w", cursor="hand2",
                         font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                         text_color="#334155")
    label.pack(side="left", fill="x", expand=True, padx=4)
    label.bind("<Button-1>", lambda e: toggle())

    for sub in tema_data["subtemas"]:
        _add_subtema_row(sub_frame, sub)


def _add_subtema_row(parent, text):
    """Añade un Subtema (Nivel 3)."""
    row = ctk.CTkFrame(parent, fg_color="transparent", height=24)
    row.pack(fill="x", pady=(1, 0), anchor="n")
    row.pack_propagate(False)

    # Sangría doble
    ctk.CTkFrame(row, width=44, fg_color="transparent").pack(side="left")
    
    # Indicador de punto (bullet)
    dot = ctk.CTkFrame(row, width=5, height=5, corner_radius=3, fg_color=COLOR_ORO)
    dot.pack(side="left", padx=(0, 8))

    ctk.CTkLabel(row, text=text, anchor="w", text_color="#64748B",
                 font=ctk.CTkFont(family="Segoe UI", size=10)).pack(side="left", fill="x")