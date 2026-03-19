# app/presentation/widgets/right_panel.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui
from app.data.queries import obtener_temario_materia

def build_right_panel():
    """
    Construye el panel derecho (Árbol de contenido del curso).
    """
    ui["right_panel"] = ctk.CTkFrame(
        ui["body"], fg_color="white", corner_radius=0, width=270,
        border_width=1, border_color="#E2E8F0",
    )
    ui["right_panel"].pack(side="right", fill="y")
    ui["right_panel"].pack_propagate(False)

    header = ctk.CTkFrame(ui["right_panel"], fg_color="transparent", height=46)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(
        header, text="Contenido del curso",
        font=ctk.CTkFont(size=13, weight="bold"), text_color="#0F172A",
    ).pack(side="left", padx=16, pady=12)

    ctk.CTkFrame(ui["right_panel"], height=1, fg_color="#E2E8F0",
                 corner_radius=0).pack(fill="x")

    ui["tree_scroll"] = ctk.CTkScrollableFrame(
        ui["right_panel"], fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    ui["tree_scroll"].pack(fill="both", expand=True)

    refresh_right_panel(estado["active"])

def refresh_right_panel(subject: str):
    """Recarga el árbol de contenido buscando la materia en la BD."""
    for w in ui["tree_scroll"].winfo_children():
        w.destroy()

    units = obtener_temario_materia(subject)

    if not units:
        ctk.CTkLabel(
            ui["tree_scroll"],
            text="Sin contenido registrado.",
            font=ctk.CTkFont(size=11), text_color="#94A3B8",
        ).pack(pady=20, padx=16)
        return

    for unit_data in units:
        _add_unit_row(unit_data)

# --- Funciones Privadas para construir el árbol ---

def _add_unit_row(unit_data: dict):
    expanded = {"v": True}

    children_frame = ctk.CTkFrame(ui["tree_scroll"], fg_color="transparent")

    unit_row = ctk.CTkFrame(ui["tree_scroll"], fg_color="transparent", height=28)
    unit_row.pack(fill="x", padx=8, pady=(4, 0))
    unit_row.pack_propagate(False)

    def toggle():
        expanded["v"] = not expanded["v"]
        arrow.configure(text="▾" if expanded["v"] else "▸")
        if expanded["v"]:
            children_frame.pack(fill="x", after=unit_row)
        else:
            children_frame.pack_forget()

    arrow = ctk.CTkLabel(
        unit_row, text="▾", width=16,
        font=ctk.CTkFont(size=11), text_color="#2563EB", cursor="hand2",
    )
    arrow.pack(side="left")
    arrow.bind("<Button-1>", lambda e: toggle())

    ctk.CTkLabel(
        unit_row,
        text=unit_data["unidad"],
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color="#0F172A", anchor="w", cursor="hand2",
    ).pack(side="left", fill="x", expand=True)

    children_frame.pack(fill="x")
    for tema_data in unit_data["temas"]:
        _add_tema_row(children_frame, tema_data)

def _add_tema_row(parent, tema_data: dict):
    expanded = {"v": True}
    sub_frame = ctk.CTkFrame(parent, fg_color="transparent")

    tema_row = ctk.CTkFrame(parent, fg_color="transparent", height=24)
    tema_row.pack(fill="x", padx=8, pady=(1, 0))
    tema_row.pack_propagate(False)

    def toggle():
        expanded["v"] = not expanded["v"]
        arrow.configure(text="▾" if expanded["v"] else "▸")
        if expanded["v"]:
            sub_frame.pack(fill="x", after=tema_row)
        else:
            sub_frame.pack_forget()

    ctk.CTkFrame(tema_row, width=20, fg_color="transparent").pack(side="left")

    arrow = ctk.CTkLabel(
        tema_row, text="▾", width=14,
        font=ctk.CTkFont(size=10), text_color="#64748B", cursor="hand2",
    )
    arrow.pack(side="left")
    arrow.bind("<Button-1>", lambda e: toggle())

    ctk.CTkLabel(
        tema_row,
        text=tema_data["tema"],
        font=ctk.CTkFont(size=12),
        text_color="#334155", anchor="w",
    ).pack(side="left", fill="x", expand=True)

    sub_frame.pack(fill="x")
    for sub in tema_data["subtemas"]:
        _add_subtema_row(sub_frame, sub)

def _add_subtema_row(parent, text: str):
    row = ctk.CTkFrame(parent, fg_color="transparent", height=22)
    row.pack(fill="x", padx=8, pady=(0, 0))
    row.pack_propagate(False)

    ctk.CTkFrame(row, width=42, fg_color="transparent").pack(side="left")

    ctk.CTkLabel(
        row, text="·", width=10,
        font=ctk.CTkFont(size=14), text_color="#94A3B8",
    ).pack(side="left")

    ctk.CTkLabel(
        row, text=text,
        font=ctk.CTkFont(size=11),
        text_color="#64748B", anchor="w",
    ).pack(side="left", fill="x", expand=True)