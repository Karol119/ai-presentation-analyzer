# app/presentation/views/main_gui.py
import unicodedata
import customtkinter as ctk


def _normalizar_texto(texto: str) -> str:
    """
    Normaliza una cadena para búsquedas insensibles a acentos y mayúsculas.
    Ejemplos:
      'Cálculo'     -> 'calculo'
      'Análisis'    -> 'analisis'
      'Programación'-> 'programacion'
    """
    if not texto:
        return ""
    # NFD descompone los caracteres acentuados en base + combinador.
    # Luego filtramos los combinadores (categoría 'Mn' = Mark, Nonspacing).
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(
        c for c in descompuesto if unicodedata.category(c) != "Mn"
    )
    return sin_acentos.casefold().strip()

from app.core.controller.presentation_controller import (
    orquestar_proceso_completo,
    orquestar_eliminacion_presentacion,
)
from app.core.controller.subject_controller import (
    obtener_catalogo_materias_activas,
    obtener_materias_para_agregar,
    activar_materia,
    desactivar_materia,
    obtener_id_materia,
    obtener_archivos_materia,
    orquestar_desactivacion_materia,
)
from app.presentation.views.ui_state import estado, ui
from app.presentation.widgets.topbar import build_topbar
from app.presentation.widgets.sidebar import build_left_sidebar, refresh_sidebar_styles
from app.presentation.widgets.content_panel import build_content_area, show_panel
from app.presentation.widgets.right_panel import build_right_panel, refresh_right_panel

COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"
COLOR_ORO_HOVER    = "#9E7C4A"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")



def _toggle_right_panel():
    if estado["right_panel_visible"]:
        ui["right_panel"].pack_forget()
        ui["toggle_btn"].configure(
            fg_color="transparent",
            text_color="#64748B",
            border_color="#E2E8F0",
            text="☰   Contenido",
        )
    else:
        ui["right_panel"].pack(side="right", fill="y", padx=(0, 12), pady=12)
        ui["toggle_btn"].configure(
            fg_color=COLOR_ORO,
            text_color="white",
            border_color=COLOR_ORO,
            text="✕   Ocultar",
        )
    estado["right_panel_visible"] = not estado["right_panel_visible"]


def _actualizar_boton_analizar():
    pass  # El botón "Analizar" fue movido a las tarjetas; esta función se conserva como callback.


def _seleccionar_materia(name: str):
    estado["active"] = name
    id_materia = obtener_id_materia(name)
    if id_materia:
        estado["subject_files"][name] = obtener_archivos_materia(id_materia)
    refresh_sidebar_styles()
    show_panel(name)
    _actualizar_boton_analizar()
    refresh_right_panel(name)


def _eliminar_materia(nombre_materia: str):
    """
    Muestra una alerta visual antes de proceder con el borrado 
    de la materia y sus archivos. Implementa un bloqueo de UI para evitar
    múltiples clics y peticiones.
    """
    # 1. VERIFICAR Y ACTIVAR CANDADO (Prevención de doble clic)
    if estado.get("bloqueo_ui"): 
        return
    estado["bloqueo_ui"] = True

    # Ventana modal de advertencia
    win = ctk.CTkToplevel(ui["root"])
    win.title("Confirmar eliminación")
    win.geometry("400x220")
    
    # --- FUNCIÓN DE LIMPIEZA / SALIDA ---
    def cerrar_modal():
        """Libera el candado y destruye la ventana modal."""
        estado["bloqueo_ui"] = False
        win.destroy()

    # 2. CAPTURAR CIERRE POR LA "X"
    # Esto asegura que si el usuario cierra la ventana sin pulsar botones, el candado se libere.
    win.protocol("WM_DELETE_WINDOW", cerrar_modal)

    win.grab_set() 
    win.after(10, lambda: win.focus_force())

    frame = ctk.CTkFrame(win, fg_color="white", corner_radius=15)
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ctk.CTkLabel(
        frame, 
        text="⚠ ¿Eliminar materia?",
        font=ctk.CTkFont(size=16, weight="bold"),
        text_color="#EF4444"
    ).pack(pady=(10, 5))

    ctk.CTkLabel(
        frame,
        text=f"Se borrarán permanentemente todos los archivos\ny el historial de '{nombre_materia}'.",
        font=ctk.CTkFont(size=12),
        text_color="#64748B"
    ).pack(pady=5)

    btn_row = ctk.CTkFrame(frame, fg_color="transparent")
    btn_row.pack(side="bottom", fill="x", pady=15)

    def confirmar():
        # Destruimos la ventana primero. El candado NO se libera aquí,
        # se liberará hasta que '_ejecutar_borrado_real_materia' termine su trabajo.
        win.destroy()
        _ejecutar_borrado_real_materia(nombre_materia)

    # BOTÓN ELIMINAR
    ctk.CTkButton(
        btn_row, text="Eliminar todo", command=confirmar,
        fg_color="#EF4444", hover_color="#DC2626", text_color="white",
        width=120, height=34, corner_radius=8
    ).pack(side="left", padx=15)

    # BOTÓN CANCELAR
    ctk.CTkButton(
        btn_row, text="Cancelar", command=cerrar_modal,
        fg_color="transparent", text_color="#64748B", border_width=1,
        border_color="#CBD5E1", width=120, height=34, corner_radius=8
    ).pack(side="right", padx=15)


def _ejecutar_borrado_real_materia(nombre_materia):
    """
    Realiza la eliminación física y lógica. El candado se libera
    estrictamente al finalizar todo el proceso.
    """
    try:
        # 1. Llamar al controlador para borrar archivos y registros en BD
        exito, mensaje = orquestar_desactivacion_materia(nombre_materia)
        
        if exito:
            # 2. Remover del estado global
            if nombre_materia in estado["subjects"]:
                estado["subjects"].remove(nombre_materia)
            
            if nombre_materia in estado["subject_files"]:
                del estado["subject_files"][nombre_materia]

            # 3. Limpiar diccionarios de UI y destruir widgets de la sidebar
            ui["sidebar_btns"] = {} 
            for widget in ui["sidebar_list"].winfo_children():
                widget.destroy()

            # 4. Manejo de la lógica según si quedan materias o no
            if not estado["subjects"]:
                estado["active"] = ""
                from app.presentation.widgets.content_panel import show_empty_state
                show_empty_state()
                refresh_right_panel("")
                _actualizar_boton_analizar()
            else:
                if estado["active"] == nombre_materia:
                    estado["active"] = estado["subjects"][0]
                
                from app.presentation.widgets.sidebar import create_sidebar_item
                for s in estado["subjects"]:
                    create_sidebar_item(s, _seleccionar_materia, _eliminar_materia)
                    
                refresh_sidebar_styles()
                show_panel(estado["active"])
                refresh_right_panel(estado["active"])

    finally:
        # 5. LIBERACIÓN FINAL DEL CANDADO
        # Garantiza que el sistema vuelva a estar disponible incluso si hubo un error en el borrado.
        estado["bloqueo_ui"] = False

def _abrir_modal_agregar_materia():
    """Modal con buscador en vivo y lista de tarjetas seleccionables."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Agregar materia")
    win.geometry("520x620")
    win.resizable(False, False)
    win.grab_set()
    win.configure(fg_color="white")

    # Centrar la ventana relativa a la principal
    win.after(10, lambda: win.focus_force())

    # --- FRANJA SUPERIOR DECORATIVA ---
    ctk.CTkFrame(win, fg_color=COLOR_GUINDA, height=6, corner_radius=0).pack(fill="x")

    # --- ENCABEZADO ---
    header = ctk.CTkFrame(win, fg_color="transparent")
    header.pack(fill="x", padx=28, pady=(20, 4))

    icon_bg = ctk.CTkFrame(header, fg_color="#FDF2F4", corner_radius=10,
                           width=40, height=40)
    icon_bg.pack(side="left", padx=(0, 12))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="📚", font=ctk.CTkFont(size=20),
                 text_color=COLOR_GUINDA).place(relx=0.5, rely=0.5, anchor="center")

    title_box = ctk.CTkFrame(header, fg_color="transparent")
    title_box.pack(side="left", fill="x", expand=True)

    ctk.CTkLabel(
        title_box,
        text="Agregar materia",
        font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
        text_color=COLOR_GUINDA,
        anchor="w",
    ).pack(fill="x", anchor="w")

    ctk.CTkLabel(
        title_box,
        text="Selecciona una materia del catálogo ESCOM",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#64748B",
        anchor="w",
    ).pack(fill="x", anchor="w")

    available = obtener_materias_para_agregar()

    if not available:
        ctk.CTkLabel(
            win,
            text="✓ Todas las materias ya están agregadas.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_GUINDA,
        ).pack(pady=40)
        ctk.CTkButton(
            win, text="Cerrar", command=win.destroy,
            fg_color=COLOR_GUINDA, hover_color=COLOR_GUINDA_HOVER,
            corner_radius=10, width=140, height=36,
        ).pack(pady=(0, 24))
        return

    # --- BARRA DE BÚSQUEDA ---
    search_box = ctk.CTkFrame(
        win, fg_color="#F8FAFC", corner_radius=10,
        border_width=1, border_color="#E2E8F0",
    )
    search_box.pack(fill="x", padx=28, pady=(18, 6))

    ctk.CTkLabel(search_box, text="🔍", font=ctk.CTkFont(size=14),
                 text_color="#94A3B8").pack(side="left", padx=(12, 4), pady=8)

    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(
        search_box,
        textvariable=search_var,
        placeholder_text="Buscar materia…",
        fg_color="transparent",
        border_width=0,
        text_color="#0F172A",
        font=ctk.CTkFont(family="Segoe UI", size=12),
        height=32,
    )
    search_entry.pack(side="left", fill="x", expand=True, padx=(2, 10), pady=4)

    # Contador de resultados
    count_lbl = ctk.CTkLabel(
        win, text=f"{len(available)} materias disponibles",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        text_color="#94A3B8", anchor="w",
    )
    count_lbl.pack(fill="x", padx=28, pady=(0, 6))

    # --- LISTA DESPLAZABLE DE TARJETAS ---
    list_container = ctk.CTkFrame(
        win, fg_color="#FAFBFC", corner_radius=12,
        border_width=1, border_color="#E8ECF2",
    )
    list_container.pack(fill="both", expand=True, padx=28, pady=(0, 14))

    list_scroll = ctk.CTkScrollableFrame(
        list_container,
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color="#CBD5E1",
        scrollbar_button_hover_color="#94A3B8",
    )
    list_scroll.pack(fill="both", expand=True, padx=4, pady=4)

    # Estado de selección compartido entre callbacks
    selection = {"name": None, "row": None}

    # Botón "Agregar" — referencia para habilitar/deshabilitar
    add_btn_ref = {"btn": None}

    def _set_selected(name, row_widget):
        """Marca visualmente la tarjeta seleccionada."""
        # Restaurar la tarjeta anterior
        prev = selection["row"]
        if prev is not None and prev.winfo_exists():
            prev.configure(
                fg_color="white",
                border_color="#E2E8F0",
                border_width=1,
            )
            prev._label.configure(text_color="#1E293B",
                                  font=ctk.CTkFont(family="Segoe UI",
                                                   size=12, weight="normal"))
            prev._check.configure(text="")

        # Activar la nueva
        row_widget.configure(
            fg_color=COLOR_GUINDA_SUAVE,
            border_color=COLOR_GUINDA,
            border_width=2,
        )
        row_widget._label.configure(
            text_color=COLOR_GUINDA,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        )
        row_widget._check.configure(text="✓")

        selection["name"] = name
        selection["row"] = row_widget

        if add_btn_ref["btn"] is not None:
            add_btn_ref["btn"].configure(
                state="normal",
                fg_color=COLOR_GUINDA,
                text_color="white",
            )

    def _make_row(parent, name):
        """Crea una tarjeta clickeable para una materia."""
        row = ctk.CTkFrame(
            parent, fg_color="white", corner_radius=10,
            border_width=1, border_color="#E2E8F0",
            cursor="hand2",
        )
        row.pack(fill="x", padx=6, pady=3)
        # Col 0 = label expansible, Col 1 = check
        row.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            row, text=name, anchor="w", justify="left",
            wraplength=380,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#1E293B",
            cursor="hand2",
        )
        label.grid(row=0, column=0, sticky="ew", padx=14, pady=10)

        check = ctk.CTkLabel(
            row, text="", width=20,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_GUINDA,
        )
        check.grid(row=0, column=1, sticky="e", padx=(0, 12), pady=10)

        row._label = label
        row._check = check

        def on_click(_e=None):
            _set_selected(name, row)

        def on_enter(_e=None):
            if selection["row"] is not row:
                row.configure(border_color="#E2C5CF")

        def on_leave(_e=None):
            if selection["row"] is not row:
                row.configure(border_color="#E2E8F0")

        for w in (row, label, check):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return row

    # Almacena las tarjetas creadas para poder filtrarlas
    rows_index = []

    def _build_rows(filter_text=""):
        # Limpiar contenido actual
        for w in list_scroll.winfo_children():
            w.destroy()
        rows_index.clear()

        ft = _normalizar_texto(filter_text)
        if ft:
            matches = [n for n in available if ft in _normalizar_texto(n)]
        else:
            matches = available

        if not matches:
            ctk.CTkLabel(
                list_scroll,
                text="Sin coincidencias para tu búsqueda.",
                font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
                text_color="#94A3B8",
            ).pack(pady=30)
            count_lbl.configure(text="0 resultados")
            return

        for n in matches:
            row = _make_row(list_scroll, n)
            rows_index.append((n, row))
            # Restaurar el resaltado si esta materia ya estaba seleccionada
            if selection["name"] == n:
                _set_selected(n, row)

        if ft:
            count_lbl.configure(
                text=f"{len(matches)} de {len(available)} resultados"
            )
        else:
            count_lbl.configure(text=f"{len(available)} materias disponibles")

    # Filtro en vivo
    search_var.trace_add("write", lambda *_: _build_rows(search_var.get()))

    _build_rows()

    # --- BOTONES INFERIORES ---
    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(fill="x", padx=28, pady=(0, 22))

    def confirm():
        name = selection["name"]
        if not name:
            return
        if activar_materia(name):
            estado["subjects"].append(name)
            estado["subject_files"][name] = []
            from app.presentation.widgets.sidebar import create_sidebar_item
            from app.presentation.widgets.content_panel import create_panel
            create_sidebar_item(name, _seleccionar_materia, _eliminar_materia)
            create_panel(name, _actualizar_boton_analizar)
            _seleccionar_materia(name)
        win.destroy()

    ctk.CTkButton(
        btn_row,
        text="Cancelar",
        command=win.destroy,
        fg_color="transparent",
        text_color="#64748B",
        hover_color="#F1F5F9",
        border_width=1,
        border_color="#E2E8F0",
        width=160,
        height=40,
        corner_radius=10,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
    ).pack(side="left")

    add_btn = ctk.CTkButton(
        btn_row,
        text="Agregar materia",
        command=confirm,
        fg_color="#CBD5E1",          # Gris hasta que haya selección
        hover_color=COLOR_GUINDA_HOVER,
        text_color="#94A3B8",
        width=180,
        height=40,
        corner_radius=10,
        state="disabled",
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
    )
    add_btn.pack(side="right")
    add_btn_ref["btn"] = add_btn

    # Foco en la búsqueda al abrir
    win.after(120, lambda: search_entry.focus_set())


def _analyze():
    subject      = estado["active"]
    id_materia   = obtener_id_materia(subject)
    if not id_materia:
        return

    resultados = []
    for datos in estado["subject_files"][subject]:
        nombre, ruta_pptx = datos[0], datos[1]
        if ruta_pptx:
            exito, mensaje = orquestar_proceso_completo(ruta_pptx, id_materia)
            icono = "✅" if exito else "❌"
            resultados.append(f"{icono} {nombre}:\n   {mensaje}")

    mensaje_final = (
        "\n\n".join(resultados) if resultados else "Cargue una presentación para analizar."
    )

    win = ctk.CTkToplevel(ui["root"])
    win.title("Resultados del Análisis")
    win.geometry("520x420")
    win.grab_set()
    win.configure(fg_color="white")

    accent = ctk.CTkFrame(win, fg_color=COLOR_GUINDA, height=6, corner_radius=0)
    accent.pack(fill="x")

    ctk.CTkLabel(
        win,
        text=f"Análisis: {subject}",
        font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack(pady=(22, 12))

    scroll = ctk.CTkScrollableFrame(
        win,
        fg_color="#F8FAFC",
        height=200,
        border_width=1,
        border_color="#E8ECF2",
        corner_radius=10,
    )
    scroll.pack(fill="both", expand=True, padx=28)

    ctk.CTkLabel(
        scroll,
        text=mensaje_final,
        font=ctk.CTkFont(size=12),
        text_color="#334155",
        justify="left",
        wraplength=400,
    ).pack(anchor="w", padx=14, pady=14)

    ctk.CTkButton(
        win,
        text="Finalizar",
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        corner_radius=10,
        width=130,
        height=38,
    ).pack(pady=22)



def mostrar_modal_exito(mensaje):
    win = ctk.CTkToplevel(ui["root"])
    win.title("Éxito")
    win.geometry("400x260")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FDF8F0", corner_radius=40,
                           width=72, height=72)
    icon_bg.pack(pady=(24, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="✔", font=ctk.CTkFont(size=32, weight="bold"),
                 text_color=COLOR_ORO).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win,
        text=mensaje,
        font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        text_color=COLOR_GUINDA,
        wraplength=340,
    ).pack(pady=(0, 20))

    ctk.CTkButton(
        win,
        text="Cerrar",
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        width=130,
        height=36,
        corner_radius=10,
    ).pack(pady=(0, 24))

# Agrega esta función en main_gui.py (puedes ponerla cerca de mostrar_modal_exito)

def mostrar_modal_advertencia(mensaje):
    """Muestra un modal de advertencia para casos como archivos duplicados."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Atención")
    win.geometry("400x260")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Franja superior color Oro para advertencias
    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FFFBEB", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(24, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="⚠️", font=ctk.CTkFont(size=32), text_color=COLOR_ORO).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win,
        text=mensaje,
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#1E293B",
        wraplength=340,
        justify="center"
    ).pack(pady=(0, 20))

    ctk.CTkButton(
        win,
        text="Entendido",
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        width=130,
        height=36,
        corner_radius=10,
    ).pack(pady=(0, 24))


def confirmar_eliminacion(nombre, subject, callback_confirmar):
    win = ctk.CTkToplevel(ui["root"])
    win.title("Confirmar eliminación")
    win.geometry("460x300")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    ctk.CTkFrame(win, fg_color="#EF4444", height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FEF2F2", corner_radius=40,
                           width=64, height=64)
    icon_bg.pack(pady=(22, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="🗑", font=ctk.CTkFont(size=28),
                 text_color="#EF4444").place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win,
        text="¿Eliminar esta presentación?",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack()

    ctk.CTkLabel(
        win,
        text=nombre,
        font=ctk.CTkFont(size=12, slant="italic"),
        text_color="#64748B",
    ).pack(pady=(2, 6))

    ctk.CTkLabel(
        win,
        text="Se eliminarán todos los datos, versiones y análisis previos.",
        font=ctk.CTkFont(size=11),
        text_color="#94A3B8",
        justify="center",
        wraplength=360,
    ).pack(padx=20, pady=(0, 16))

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=(0, 20))

    def proceder():
        callback_confirmar()
        win.destroy()

    ctk.CTkButton(
        btn_row,
        text="Eliminar",
        command=proceder,
        fg_color="#EF4444",
        hover_color="#DC2626",
        text_color="white",
        width=130,
        height=36,
        corner_radius=10,
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        btn_row,
        text="Cancelar",
        command=win.destroy,
        fg_color="transparent",
        text_color="#64748B",
        border_width=1,
        border_color="#E2E8F0",
        width=130,
        height=36,
        corner_radius=10,
    ).pack(side="right", padx=10)

def confirmar_eliminacion_materia(nombre, callback_confirmar):
    """Muestra un modal de advertencia institucional para el borrado de la materia."""
    win = ctk.CTkToplevel(ui["root"])
    win.title("Confirmar eliminación de materia")
    win.geometry("460x320")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Franja de advertencia roja
    ctk.CTkFrame(win, fg_color="#EF4444", height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FEF2F2", corner_radius=40, width=64, height=64)
    icon_bg.pack(pady=(22, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="⚠️", font=ctk.CTkFont(size=28), text_color="#EF4444").place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win, text="¿Eliminar materia completa?",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color=COLOR_GUINDA
    ).pack()

    ctk.CTkLabel(
        win, text=nombre,
        font=ctk.CTkFont(size=12, slant="italic"),
        text_color="#64748B"
    ).pack(pady=(2, 6))

    ctk.CTkLabel(
        win, 
        text="Esta acción desactivará la materia y ELIMINARÁ permanentemente\ntodas sus presentaciones, miniaturas y análisis del disco duro.",
        font=ctk.CTkFont(size=11), text_color="#94A3B8", justify="center", wraplength=380
    ).pack(padx=20, pady=(0, 20))

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=(0, 20))

    def proceder():
        callback_confirmar()
        win.destroy()

    ctk.CTkButton(
        btn_row, text="Eliminar todo", command=proceder,
        fg_color="#EF4444", hover_color="#DC2626", text_color="white",
        width=140, height=36, corner_radius=10
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        btn_row, text="Cancelar", command=win.destroy,
        fg_color="transparent", text_color="#64748B", border_width=1,
        border_color="#E2E8F0", width=140, height=36, corner_radius=10
    ).pack(side="right", padx=10)



def iniciar_aplicacion():
    ui["root"] = ctk.CTk()
    ui["root"].title("AI Presentation Analyzer · IPN ESCOM")
    ui["root"].geometry("1300x820")
    ui["root"].minsize(1100, 700)
    ui["root"].configure(fg_color="#EEF2F7")

    all_active_subjects = obtener_catalogo_materias_activas()
    estado["subjects"]  = all_active_subjects

    estado["subject_files"] = {}
    for s in estado["subjects"]:
        id_materia = obtener_id_materia(s)
        estado["subject_files"][s] = obtener_archivos_materia(id_materia)

    estado["active"] = estado["subjects"][0] if estado["subjects"] else ""

    build_topbar(_toggle_right_panel)

    ui["body"] = ctk.CTkFrame(ui["root"], fg_color="transparent", corner_radius=0)
    ui["body"].pack(fill="both", expand=True)

    build_left_sidebar(_abrir_modal_agregar_materia, _seleccionar_materia, _eliminar_materia)
    build_content_area(_actualizar_boton_analizar)
    build_right_panel()

    if estado["active"]:
        _seleccionar_materia(estado["active"])

    ui["root"].mainloop()