# app/presentation/widgets/sidebar.py
import customtkinter as ctk
from app.presentation.views.ui_state import estado, ui

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_SUAVE = "#FDF2F4"
COLOR_ORO          = "#BC955C"


def build_left_sidebar(comando_abrir_modal, comando_seleccionar, comando_eliminar):
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

    ui["sidebar_list"] = ctk.CTkScrollableFrame(
        ui["left_sidebar"],
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color="#E2E8F0",
        border_width=0,
    )
    ui["sidebar_list"].pack(fill="both", expand=True, padx=8, pady=(0, 8))

    for s in estado["subjects"]:
        create_sidebar_item(s, comando_seleccionar, comando_eliminar)

    ctk.CTkFrame(ui["left_sidebar"], height=1, fg_color="#F1F5F9").pack(
        fill="x", padx=16, pady=(0, 10)
    )
    add_btn = ctk.CTkButton(
        ui["left_sidebar"],
        text="＋  Agregar materia",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        fg_color="transparent",
        hover_color="#FDF2F4",
        text_color=COLOR_GUINDA,
        border_width=1,
        border_color="#E2C5CF",
        corner_radius=10,
        height=38,
        command=comando_abrir_modal,
    )
    add_btn.pack(fill="x", padx=14, pady=(0, 14))


def create_sidebar_item(name, comando_seleccionar, comando_eliminar):
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

    indicator = ctk.CTkFrame(
        row,
        width=4,
        fg_color=COLOR_GUINDA if is_active else "transparent",
        corner_radius=2,
    )
    indicator.pack(side="left", fill="y", padx=(4, 0), pady=10)

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
    badge.pack(side="right", padx=(0, 8))
    badge.pack_forget()

    close = ctk.CTkButton(
        row,
        text="✕",
        width=22,
        height=22,
        font=ctk.CTkFont(size=10, weight="bold"),
        fg_color="transparent",
        hover_color="#FEE2E2",
        text_color="#CBD5E1",
        corner_radius=11,
        command=lambda n=name: comando_eliminar(n),
    )
    close.pack(side="right", padx=(0, 8))
    close.pack_forget()

    row._indicator = indicator
    row._label     = label
    row._badge     = badge
    row._badge_var = badge_var
    row._close     = close

    def on_enter(e):
        close.pack(side="right", padx=(0, 8))
        close.lift()

    def on_leave(e):
        close.pack_forget()

    for w in (row, label):
        w.bind("<Enter>", on_enter)
        w.bind("<Leave>", on_leave)
        w.bind("<Button-1>", lambda e, n=name: comando_seleccionar(n))

    ui["sidebar_btns"][name] = row
    refresh_badge(name)


def refresh_badge(name: str):
    """Actualiza el contador de archivos en el badge."""
    row = ui["sidebar_btns"].get(name)
    if not row:
        return
    count = len(estado["subject_files"].get(name, []))
    if count > 0:
        row._badge_var.set(str(count))
        row._badge.pack(side="right", padx=(0, 6))
    else:
        row._badge.pack_forget()


def refresh_sidebar_styles():
    """Refresca los estilos visuales al cambiar la materia activa."""
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