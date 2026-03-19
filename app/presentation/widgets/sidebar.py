# app/presentation/widgets/sidebar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

def build_left_sidebar(comando_abrir_modal, comando_seleccionar, comando_eliminar):
    """
    Construye la barra lateral izquierda (Lista de Materias).
    """
    ui["left_sidebar"] = ctk.CTkFrame(
        ui["body"], fg_color="white", corner_radius=0, width=210,
        border_width=1, border_color="#E2E8F0",
    )
    ui["left_sidebar"].pack(side="left", fill="y")
    ui["left_sidebar"].pack_propagate(False)

    ctk.CTkLabel(
        ui["left_sidebar"], text="MATERIAS",
        font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8",
    ).pack(anchor="w", padx=16, pady=(18, 8))

    ui["sidebar_list"] = ctk.CTkScrollableFrame(
        ui["left_sidebar"], fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    ui["sidebar_list"].pack(fill="both", expand=True, padx=8)

    for s in estado["subjects"]:
        create_sidebar_item(s, comando_seleccionar, comando_eliminar)

    ctk.CTkFrame(ui["left_sidebar"], height=1, fg_color="#E2E8F0",
                 corner_radius=0).pack(fill="x", pady=6)

    ctk.CTkButton(
        ui["left_sidebar"], text="＋  Agregar materia",
        font=ctk.CTkFont(size=12),
        fg_color="transparent", hover_color="#F1F5F9",
        text_color="#64748B", border_width=1, border_color="#CBD5E1",
        corner_radius=8, height=36, anchor="w",
        command=comando_abrir_modal,
    ).pack(fill="x", padx=10, pady=(0, 14))

def create_sidebar_item(name: str, comando_seleccionar, comando_eliminar):
    """Crea un elemento individual en la lista de la barra lateral."""
    is_active = name == estado["active"]
    row = ctk.CTkFrame(
        ui["sidebar_list"],
        fg_color="#EFF6FF" if is_active else "transparent",
        corner_radius=8, height=40, cursor="hand2",
    )
    row.pack(fill="x", pady=2)
    row.pack_propagate(False)

    indicator = ctk.CTkFrame(
        row, width=3,
        fg_color="#2563EB" if is_active else "transparent",
        corner_radius=2,
    )
    indicator.pack(side="left", fill="y", padx=(4, 0), pady=6)

    label = ctk.CTkLabel(
        row, text=name,
        font=ctk.CTkFont(size=13, weight="bold" if is_active else "normal"),
        text_color="#1D4ED8" if is_active else "#334155",
        anchor="w",
    )
    label.pack(side="left", fill="both", expand=True, padx=8)

    badge_var = ctk.StringVar(value="")
    badge = ctk.CTkLabel(
        row, textvariable=badge_var,
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color="white",
        fg_color="#2563EB" if is_active else "#CBD5E1",
        corner_radius=10, width=22, height=18,
    )
    badge.pack(side="right", padx=(0, 8))
    badge.pack_forget()

    close = ctk.CTkButton(
        row, text="✕", width=18, height=18,
        font=ctk.CTkFont(size=9),
        fg_color="transparent", hover_color="#FEE2E2",
        text_color="#94A3B8", corner_radius=9,
        command=lambda n=name: comando_eliminar(n),
    )
    close.pack(side="right", padx=(0, 4))

    row._indicator = indicator
    row._label = label
    row._badge = badge
    row._badge_var = badge_var

    for w in (row, label):
        w.bind("<Button-1>", lambda e, n=name: comando_seleccionar(n))

    ui["sidebar_btns"][name] = row
    refresh_badge(name)

def refresh_badge(name: str):
    """Actualiza el número de archivos mostrados en la insignia de la materia."""
    row = ui["sidebar_btns"].get(name)
    if not row:
        return
    count = len(estado["subject_files"].get(name, []))
    if count > 0:
        row._badge_var.set(str(count))
        row._badge.pack(side="right", padx=(0, 8))
    else:
        row._badge.pack_forget()

def refresh_sidebar_styles():
    """Actualiza visualmente cuál materia está activa en la barra lateral."""
    for n, row in ui["sidebar_btns"].items():
        a = n == estado["active"]
        row.configure(fg_color="#EFF6FF" if a else "transparent")
        row._indicator.configure(fg_color="#2563EB" if a else "transparent")
        row._label.configure(
            text_color="#1D4ED8" if a else "#334155",
            font=ctk.CTkFont(size=13, weight="bold" if a else "normal"),
        )
        row._badge.configure(fg_color="#2563EB" if a else "#CBD5E1")