# app/presentation/widgets/content_panel.py
import customtkinter as ctk
from tkinter import filedialog
import os
from PIL import Image

from app.presentation.views.ui_state import estado, ui
from app.core.controller.presentation_controller import (
    orquestar_proceso_completo,
    orquestar_eliminacion_presentacion,
)
from app.core.controller.subject_controller import (
    obtener_id_materia, 
    obtener_archivos_materia
)

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"

CARD_W = 175
CARD_H = 232

def build_content_area(comando_actualizar_boton):
    """Construye el contenedor principal y limpia registros previos."""
    ui["content_area"] = ctk.CTkFrame(
        ui["body"],
        fg_color="white",
        corner_radius=14,
        border_width=1,
        border_color="#E8ECF2",
    )
    ui["content_area"].pack(
        side="left", fill="both", expand=True, padx=(0, 10), pady=12
    )
    
    ui["panels"] = {} 
    
    for s in estado["subjects"]:
        create_panel(s, comando_actualizar_boton)

def create_panel(name: str, comando_actualizar_boton):
    """Crea el panel de una materia pero NO lo posiciona aún."""
    panel = ctk.CTkFrame(ui["content_area"], fg_color="transparent", corner_radius=0)

    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=26, pady=(22, 0))
    ctk.CTkLabel(
        header, text=name,
        font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(side="left")

    sub_header = ctk.CTkFrame(panel, fg_color="transparent")
    sub_header.pack(fill="x", padx=26, pady=(6, 0))
    ctk.CTkLabel(
        sub_header, text="📄  Mis Presentaciones",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        text_color="#475569",
    ).pack(side="left")

    ctk.CTkFrame(panel, height=1, fg_color="#F1F5F9").pack(fill="x", padx=26, pady=(10, 0))

    cards_scroll = ctk.CTkScrollableFrame(
        panel, fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#E2E8F0",
    )
    cards_scroll.pack(fill="both", expand=True, padx=26, pady=(16, 24))

    panel._cards_scroll = cards_scroll
    ui["panels"][name]   = panel
    rebuild_cards(name, comando_actualizar_boton)

def show_panel(name: str):
    for n, p in ui["panels"].items():
        if n == name:
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            p.place_forget()

# app/presentation/widgets/content_panel.py

def show_empty_state():
    """Muestra una vista de bienvenida cuando no hay materias activas."""
    # Ocultamos todos los paneles actuales
    for p in ui["panels"].values():
        p.place_forget()
        
    # Creamos o recuperamos el panel de estado vacío
    if "empty_view" not in ui:
        view = ctk.CTkFrame(ui["content_area"], fg_color="white", corner_radius=14)
        ui["empty_view"] = view
        
        container = ctk.CTkFrame(view, fg_color="transparent")
        container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Icono o Ilustración
        ctk.CTkLabel(
            container, text="📚", font=ctk.CTkFont(size=60)
        ).pack(pady=10)
        
        ctk.CTkLabel(
            container, 
            text="¡Bienvenido al Analizador!",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLOR_GUINDA
        ).pack()
        
        ctk.CTkLabel(
            container, 
            text="Aún no tienes materias activas.\nPresiona '+ Agregar materia' en el panel izquierdo para comenzar.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#64748B",
            justify="center"
        ).pack(pady=10)

    ui["empty_view"].place(relx=0, rely=0, relwidth=1, relheight=1)

def rebuild_cards(subject: str, comando_actualizar_boton):
    panel = ui["panels"].get(subject)
    if not panel: return

    scroll = panel._cards_scroll
    for w in scroll.winfo_children():
        w.destroy()

    wrap = ctk.CTkFrame(scroll, fg_color="transparent")
    wrap.pack(anchor="nw")

    for datos in estado["subject_files"].get(subject, []):
        nombre, ruta_thumb = datos[0], datos[2]
        _make_file_card(wrap, subject, nombre, ruta_thumb, comando_actualizar_boton)

    _make_upload_card(wrap, subject, comando_actualizar_boton)


def _make_file_card(parent, subject: str, name: str, ruta_thumb, comando_actualizar_boton):
    outer = ctk.CTkFrame(parent, fg_color="transparent", width=CARD_W, height=CARD_H)
    outer.pack(side="left", padx=(0, 18), pady=8)
    outer.pack_propagate(False)

    card = ctk.CTkFrame(
        outer, width=CARD_W - 6, height=CARD_H - 6,
        fg_color="white", border_width=1, border_color="#E2E8F0", corner_radius=16,
    )
    card.place(x=3, y=3)
    card.pack_propagate(False)

    # Cara Preview
    face_prev = ctk.CTkFrame(card, fg_color="transparent", corner_radius=0)
    face_prev.place(relx=0, rely=0, relwidth=1, relheight=1)

    try:
        if ruta_thumb and os.path.exists(ruta_thumb):
            img = Image.open(ruta_thumb)
            img_ctk = ctk.CTkImage(light_image=img, size=(130, 84))
            ctk.CTkLabel(face_prev, image=img_ctk, text="").pack(pady=(36, 0))
        else: raise FileNotFoundError
    except:
        icon_bg = ctk.CTkFrame(face_prev, fg_color="#FDF2F4", corner_radius=12, width=90, height=68)
        icon_bg.pack(pady=(36, 0))
        ctk.CTkLabel(icon_bg, text="📊", font=ctk.CTkFont(size=36), text_color=COLOR_GUINDA).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(face_prev, text=name, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                 text_color="#1E293B", wraplength=148, justify="center").pack(padx=8, pady=(8, 0), fill="x", expand=True)

    # Cara Menú
    face_menu = ctk.CTkFrame(card, fg_color="white", corner_radius=16)

    def toggle_menu(abrir=True):
        if abrir:
            face_prev.place_forget()
            face_menu.place(relx=0, rely=0, relwidth=1, relheight=1)
            card.configure(border_color=COLOR_ORO)
        else:
            face_menu.place_forget()
            face_prev.place(relx=0, rely=0, relwidth=1, relheight=1)
            card.configure(border_color="#E2E8F0")

    ctk.CTkButton(face_prev, text="☰  Ver opciones", height=30, fg_color="#F8FAFC", 
                  text_color="#475569", font=ctk.CTkFont(size=11, weight="bold"),
                  command=lambda: toggle_menu(True)).pack(fill="x", padx=12, pady=(0, 12), side="bottom")

    menu_header = ctk.CTkFrame(face_menu, fg_color=COLOR_GUINDA, height=42, corner_radius=0)
    menu_header.pack(fill="x")
    menu_header.pack_propagate(False)
    
    ctk.CTkLabel(menu_header, text="Opciones", text_color="white", font=ctk.CTkFont(size=10, weight="bold")).place(x=12, rely=0.5, anchor="w")
    ctk.CTkButton(menu_header, text="←", width=28, height=28, fg_color="transparent", text_color="white",
                  command=lambda: toggle_menu(False)).place(relx=1.0, x=-6, rely=0.5, anchor="e")

    items_frame = ctk.CTkFrame(face_menu, fg_color="transparent")
    items_frame.pack(fill="both", expand=True, padx=6, pady=(8, 4))

    opciones = [
        ("🖥   Presentar clase",  "#1E293B", _placeholder),
        ("📊   Ver análisis",     "#1E293B", _placeholder),
        ("🕓   Ver historial",    "#1E293B", _placeholder),
        ("📈   Ver rendimiento",  "#1E293B", _placeholder),
    ]

    for label, color, cmd in opciones:
        _menu_item(items_frame, label, color, cmd)

    ctk.CTkFrame(face_menu, height=1, fg_color="#F1F5F9").pack(fill="x", padx=10)

    def on_delete():
        toggle_menu(False)
        _remove_file(subject, name, comando_actualizar_boton)

    ctk.CTkButton(face_menu, text="🗑   Eliminar", fg_color="transparent", text_color="#EF4444", 
                  hover_color="#FEF2F2", font=ctk.CTkFont(size=11, weight="bold"),
                  anchor="w", command=on_delete).pack(fill="x", padx=6, pady=(4, 8), side="bottom")

def _menu_item(parent, text: str, color: str, command):
    """Crea un botón de opción dentro del menú de la tarjeta."""
    ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        fg_color="transparent",
        hover_color="#F8FAFC",
        text_color=color,
        corner_radius=8,
        height=30,
        anchor="w",
        command=command,
    ).pack(fill="x", pady=1)

def _placeholder():
    pass

def _make_upload_card(parent, subject, comando_actualizar_boton):
    card = ctk.CTkFrame(parent, width=CARD_W-6, height=CARD_H-6, fg_color="#FAFBFD", 
                        border_width=2, border_color="#E2E8F0", corner_radius=16, cursor="hand2")
    card.pack(side="left", padx=(0, 18), pady=8)
    card.pack_propagate(False)

    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(inner, text="＋", font=ctk.CTkFont(size=24), text_color=COLOR_ORO).pack()
    ctk.CTkLabel(inner, text="Subir presentación", font=ctk.CTkFont(size=11, weight="bold"), text_color="#64748B").pack()

    def pick(e=None): _pick_files(subject, comando_actualizar_boton)
    card.bind("<Button-1>", pick)
    for w in inner.winfo_children(): w.bind("<Button-1>", pick)

def _pick_files(subject, comando_actualizar_boton):
    paths = filedialog.askopenfilenames(filetypes=[("PPTX", "*.pptx")])
    if not paths: return
    id_m = obtener_id_materia(subject)
    for p in paths:
        orquestar_proceso_completo(p, id_m)
    
    estado["subject_files"][subject] = obtener_archivos_materia(id_m)
    rebuild_cards(subject, comando_actualizar_boton)
    comando_actualizar_boton()

def _remove_file(subject, name, comando_actualizar_boton):
    from app.presentation.views.main_gui import confirmar_eliminacion
    def on_confirm():
        id_m = obtener_id_materia(subject)
        if orquestar_eliminacion_presentacion(name, id_m):
            estado["subject_files"][subject] = obtener_archivos_materia(id_m)
            rebuild_cards(subject, comando_actualizar_boton)
            comando_actualizar_boton()
    confirmar_eliminacion(name, subject, on_confirm)