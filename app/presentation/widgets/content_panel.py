# app/presentation/widgets/content_panel.py
import customtkinter as ctk
from tkinter import filedialog
import os
from app.presentation.views.ui_state import estado, ui

def build_content_area(comando_actualizar_boton):
    """
    Construye el área central principal donde se muestran las presentaciones.
    """
    ui["content_area"] = ctk.CTkFrame(ui["body"], fg_color="#F1F5F9", corner_radius=0)
    ui["content_area"].pack(side="left", fill="both", expand=True)
    
    for s in estado["subjects"]:
        create_panel(s, comando_actualizar_boton)

def create_panel(name: str, comando_actualizar_boton):
    """Crea un panel contenedor para las tarjetas de una materia específica."""
    panel = ctk.CTkFrame(ui["content_area"], fg_color="#F1F5F9", corner_radius=0)

    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=32, pady=(26, 4))
    ctk.CTkLabel(
        header, text=name,
        font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
        text_color="#0F172A",
    ).pack(side="left")

    section = ctk.CTkFrame(panel, fg_color="transparent")
    section.pack(fill="x", padx=32, pady=(12, 10))
    ctk.CTkLabel(section, text="▶", font=ctk.CTkFont(size=11),
                 text_color="#94A3B8").pack(side="left", padx=(0, 6))
    ctk.CTkLabel(
        section, text="Mis Presentaciones",
        font=ctk.CTkFont(size=14, weight="bold"), text_color="#1E293B",
    ).pack(side="left")

    cards_scroll = ctk.CTkScrollableFrame(
        panel, fg_color="transparent", corner_radius=0,
        scrollbar_button_color="#CBD5E1",
    )
    cards_scroll.pack(fill="both", expand=True, padx=32, pady=(0, 24))

    panel._cards_scroll = cards_scroll
    ui["panels"][name] = panel
    rebuild_cards(name, comando_actualizar_boton)

def show_panel(name: str):
    """Muestra el panel de la materia seleccionada y oculta los demás."""
    for n, p in ui["panels"].items():
        if n == name:
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            p.place_forget()

def rebuild_cards(subject: str, comando_actualizar_boton):
    """Reconstruye visualmente las tarjetas de archivos subidos y el botón de subir."""
    panel = ui["panels"].get(subject)
    if not panel:
        return
    scroll = panel._cards_scroll
    
    # Limpiar tarjetas existentes
    for w in scroll.winfo_children():
        w.destroy()
        
    wrap = ctk.CTkFrame(scroll, fg_color="transparent")
    wrap.pack(anchor="nw")
    
    # Dibujar tarjetas de archivos
    for fname, ruta in estado["subject_files"][subject]:
        _make_file_card(wrap, subject, fname, comando_actualizar_boton)
        
    # Dibujar la tarjeta para subir nuevo
    _make_upload_card(wrap, subject, comando_actualizar_boton)

# --- Funciones Auxiliares (Privadas) del Widget ---

def _make_file_card(parent, subject: str, name: str, comando_actualizar_boton):
    short = name if len(name) <= 20 else name[:17] + "…"
    outer = ctk.CTkFrame(parent, fg_color="transparent", width=152, height=174)
    outer.pack(side="left", padx=(0, 16), pady=4)
    outer.pack_propagate(False)

    card = ctk.CTkFrame(
        outer, width=144, height=164,
        fg_color="white", border_width=1, border_color="#BFDBFE",
        corner_radius=14,
    )
    card.place(x=0, y=6)
    card.pack_propagate(False)

    ctk.CTkLabel(card, text="📄", font=ctk.CTkFont(size=40)).pack(pady=(20, 6))
    ctk.CTkLabel(
        card, text=short, font=ctk.CTkFont(size=11),
        text_color="#1E40AF", wraplength=124, justify="center",
    ).pack(padx=10)

    ctk.CTkButton(
        outer, text="✕", width=24, height=24,
        font=ctk.CTkFont(size=10, weight="bold"),
        fg_color="#EF4444", hover_color="#DC2626",
        text_color="white", corner_radius=12,
        command=lambda n=name, s=subject: _remove_file(s, n, comando_actualizar_boton),
    ).place(x=122, y=0)

def _make_upload_card(parent, subject: str, comando_actualizar_boton):
    card = ctk.CTkFrame(
        parent, width=144, height=164,
        fg_color="white", border_width=2, border_color="#CBD5E1",
        corner_radius=14, cursor="hand2",
    )
    card.pack(side="left", padx=(0, 16), pady=4)
    card.pack_propagate(False)

    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(inner, text="＋", font=ctk.CTkFont(size=32),
                 text_color="#94A3B8").pack()
    ctk.CTkLabel(
        inner, text="Subir nueva\npresentación",
        font=ctk.CTkFont(size=12), text_color="#64748B", justify="center",
    ).pack(pady=(4, 0))

    def pick(e=None, s=subject):
        _pick_files(s, comando_actualizar_boton)

    for w in [card, inner] + inner.winfo_children():
        w.bind("<Button-1>", pick)
    card.bind("<Enter>", lambda e: card.configure(fg_color="#F8FAFC"))
    card.bind("<Leave>", lambda e: card.configure(fg_color="white"))

def _pick_files(subject: str, comando_actualizar_boton):
    paths = filedialog.askopenfilenames(
        title=f"Subir presentaciones — {subject}",
        filetypes=[
            ("Presentaciones", "*.pptx *.ppt *.pdf"),
            ("Todos los archivos", "*.*"),
        ],
    )
    existing = {n for n, _ in estado["subject_files"][subject]}
    for p in paths:
        name = os.path.basename(p)
        if name not in existing:
            estado["subject_files"][subject].append((name, p))
            existing.add(name)
            
    rebuild_cards(subject, comando_actualizar_boton)
    
    # Necesitamos actualizar el badge en la sidebar, 
    # importamos la funcion solo para este uso local y evitar importaciones circulares en modulos
    from app.presentation.widgets.sidebar import refresh_badge
    refresh_badge(subject)
    
    comando_actualizar_boton()

def _remove_file(subject: str, name: str, comando_actualizar_boton):
    # Aquí podríamos usar un modal de confirmación, por simplicidad en la separación se elimina directo, 
    # o puedes mandar a llamar un modal desde main_gui
    estado["subject_files"][subject] = [
        (n, f) for n, f in estado["subject_files"][subject] if n != name
    ]
    rebuild_cards(subject, comando_actualizar_boton)
    
    from app.presentation.widgets.sidebar import refresh_badge
    refresh_badge(subject)
    
    comando_actualizar_boton()