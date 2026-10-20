# app/presentation/widgets/dialogs.py
import customtkinter as ctk

# Colores Institucionales ESCOM/IPN
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"

def grab_seguro(win, espera_ms=100, intentos=20):
    """
    Establece grab_set tolerando las condiciones de carrera de Tk
    ('grab failed: window not viewable' → TclError). La ventana puede no ser
    todavía visible en el momento del grab (típico con cargas que dejan la
    UI ocupada): reintenta en lugar de morir con un error sin rastro.
    """
    def _intentar(restantes=intentos):
        try:
            if not win.winfo_exists():
                return
            win.grab_set()
        except Exception:
            if restantes > 1:
                win.after(espera_ms, _intentar, restantes - 1)
    _intentar()


def autoajustar_modal(win, min_ancho, min_alto):
    """
    Ajusta la ventana al tamaño NATURAL real de su contenido (respeta el
    escalado/DPI de Windows) y nunca por debajo del tamaño de diseño.

    Detalle clave: ctk.CTkToplevel.geometry("") NO devuelve el tamaño
    natural — mantiene el tamaño de diseño escalado, y con textos largos el
    botón quedaba reducido a 1x1 px («una línea guinda»). Por eso se mide
    el tamaño requerido real (winfo_req*) y se aplica en píxeles físicos
    vía wm geometry, que respeta exactamente el escalado de CTk.
    Se re-ejecuta en varias pasadas porque el texto envuelto (wraplength)
    termina de calcular su altura en pasadas posteriores.
    Debe llamarse DESPUÉS de crear los widgets del modal.
    """
    def _ajustar():
        try:
            if not win.winfo_exists():
                return  # La ventana ya se cerró; no hacer nada
            win.update_idletasks()   # Termina el layout interno (ej. envoltura del texto)
            req_w = win.winfo_reqwidth()
            req_h = win.winfo_reqheight()
            # Nunca dejar que rebase la pantalla (con pocas herramientas: cap)
            alto_pantalla = win.winfo_screenheight()
            if req_h > alto_pantalla - 20:
                req_h = alto_pantalla - 20
            # wm geometry trabaja en píxeles físicos ya escalados por CTk;
            # minsize (en unidades de diseño) protege contra encogerse menos.
            win.tk.call('wm', 'geometry', str(win), f'{req_w}x{req_h}')
            win.minsize(min_ancho, min_alto)
        except Exception:
            pass
    for retardo in (20, 180, 450):
        win.after(retardo, _ajustar)


def advertir_archivo_danado(parent, nombre_archivo):
    """
    Modal amigable que informa al usuario que el archivo PowerPoint (PPTX) está
    dañado o no se pudo abrir y explica en lenguaje simple las causas comunes
    y qué puede hacer para corregirlo.
    """
    win = ctk.CTkToplevel(parent)
    win.title("No se pudo cargar la presentación")
    win.geometry("470x540")   # Tamaño inicial generoso para evitar corte
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Auto-ajuste al contenido real (incl. escalado DPI 125%/150%):
    # el botón 'Entendido' siempre queda visible.
    autoajustar_modal(win, 470, 540)

    # Franja superior color guinda (coherente con los modales de alerta)
    ctk.CTkFrame(win, fg_color=COLOR_GUINDA, height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FEF2F2", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(18, 6))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="⚠️", font=ctk.CTkFont(size=32),
                 text_color="#EF4444").place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win,
        text="Presentación dañada o ilegible",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack()

    ctk.CTkLabel(
        win,
        text=f"El archivo '{nombre_archivo}' está dañado o incompleto,\n"
             "y la aplicación no puede abrirlo de forma segura.",
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color="#1E293B",
        justify="center",
    ).pack(pady=(6, 8))

    causas = (
        "• La descarga o la copia quedó incompleta.\n"
        "• Se creó o modificó con otra aplicación\n"
        "   (por ejemplo WPS Office o LibreOffice).\n"
        "• Problemas al guardar o sincronizar\n"
        "   (OneDrive, memoria USB o cierre inesperado).\n"
        "• Una imagen, tabla o diapositiva contiene\n"
        "   datos que no se pueden leer."
    )

    causa_frame = ctk.CTkFrame(win, fg_color="#F8FAFC", corner_radius=12)
    causa_frame.pack(fill="x", padx=24)
    ctk.CTkLabel(
        causa_frame,
        text="Causas más comunes:",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#64748B",
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=14, pady=(10, 2))
    ctk.CTkLabel(
        causa_frame,
        text=causas,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#475569",
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=14, pady=(0, 10))

    ctk.CTkLabel(
        win,
        text="Sugerencia: intenta abrir el archivo de nuevo en PowerPoint\n"
             "y guárdalo otra vez (Archivo → Guardar como). Si PowerPoint\n"
             "tampoco puede abrirlo, vuelve a descargarlo de su origen.",
        font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
        text_color="#64748B",
        justify="center",
    ).pack(pady=(10, 0))

    ctk.CTkButton(
        win,
        text="Entendido",
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        width=130,
        height=36,
        corner_radius=10,
    ).pack(pady=(14, 20))


def informar_reparacion_pptx(parent, datos):
    """
    Modal informativo (positivo) que avisa que el archivo llegó con problemas,
    fue REPARADO automáticamente y explica qué se hizo y qué puede hacer el
    usuario ahora. `datos` = {"nombre":..., "diap": int|None, "elem": int|None}
    """
    nombre = datos.get("nombre", "el archivo")
    diap_elim = datos.get("diap") or 0
    elem_elim = datos.get("elem") or 0

    acciones = []
    if diap_elim:
        acciones.append(f"• Se quitaron {diap_elim} diapositiva(s) dañada(s).")
    if elem_elim:
        acciones.append(f"• Se quitaron {elem_elim} elemento(s) ilegible(s)\n"
                        "   (imágenes, tablas o texto dañado).")
    if not acciones:
        acciones.append("• Se reconstruyó y guardó el archivo de forma segura.")

    win = ctk.CTkToplevel(parent)
    win.title("Presentación reparada")
    win.geometry("470x470")
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Franja superior color Oro (éxito con precaución · Identidad ESCOM)
    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FFFBEB", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(18, 6))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="✔", font=ctk.CTkFont(size=30, weight="bold"),
                 text_color=COLOR_ORO).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(
        win,
        text="Presentación reparada",
        font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        text_color=COLOR_GUINDA,
    ).pack()

    ctk.CTkLabel(
        win,
        text=(f"El archivo '{nombre}' llegó con elementos dañados y fue\n"
              "reparado automáticamente al cargarlo."),
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color="#1E293B",
        justify="center",
    ).pack(pady=(6, 8))

    acciones_frame = ctk.CTkFrame(win, fg_color="#F8FAFC", corner_radius=12)
    acciones_frame.pack(fill="x", padx=24)
    ctk.CTkLabel(
        acciones_frame,
        text="Qué se hizo:",
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        text_color="#64748B",
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=14, pady=(10, 2))
    ctk.CTkLabel(
        acciones_frame,
        text="\n".join(acciones),
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color="#475569",
        anchor="w",
        justify="left",
    ).pack(fill="x", padx=14, pady=(0, 10))

    ctk.CTkLabel(
        win,
        text=("Qué sigue: revisa la presentación cargada y verifica que\n"
              "todo su contenido esté completo. Si falta algo importante,\n"
              "abre tu archivo original en PowerPoint y vuelve a\n"
              "guardarlo (Archivo → Guardar como), luego súbilo de nuevo."),
        font=ctk.CTkFont(family="Segoe UI", size=11, slant="italic"),
        text_color="#64748B",
        justify="center",
    ).pack(pady=(10, 0))

    ctk.CTkButton(
        win,
        text="Entendido",
        command=win.destroy,
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER,
        width=130,
        height=36,
        corner_radius=10,
    ).pack(pady=(14, 20))

    # Auto-ajuste al contenido real (incl. escalado DPI)
    autoajustar_modal(win, 470, 470)

def advertir_presentacion_existente(parent, mensaje):
    """
    Muestra un modal específico para notificar que una o varias 
    presentaciones ya se encuentran registradas en el sistema.
    """
    win = ctk.CTkToplevel(parent)
    win.title("Archivo Duplicado")
    win.geometry("420x280")
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Auto-ajuste por si el mensaje es largo o el DPI escala el contenido
    autoajustar_modal(win, 420, 280)

    # Franja superior color Oro (Identidad ESCOM)
    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    # Contenedor del Icono
    icon_bg = ctk.CTkFrame(win, fg_color="#FFFBEB", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(24, 8))
    icon_bg.pack_propagate(False)
    
    ctk.CTkLabel(
        icon_bg, 
        text="⚠️", 
        font=ctk.CTkFont(size=32), 
        text_color=COLOR_ORO
    ).place(relx=0.5, rely=0.5, anchor="center")

    # Mensaje de error
    ctk.CTkLabel(
        win, 
        text=mensaje, 
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#1E293B", 
        wraplength=360, 
        justify="center"
    ).pack(pady=(0, 20))

    # Botón de confirmación
    ctk.CTkButton(
        win, 
        text="Entendido", 
        command=win.destroy, 
        fg_color=COLOR_GUINDA,
        hover_color=COLOR_GUINDA_HOVER, 
        width=130, 
        height=36, 
        corner_radius=10
    ).pack(pady=(0, 24))

def confirmar_eliminacion_archivo(parent, nombre_archivo, callback_confirmar):
    """
    Modal de seguridad para confirmar la eliminación de una presentación específica.
    """
    win = ctk.CTkToplevel(parent)
    win.title("Confirmar eliminación")
    win.geometry("460x300")
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Auto-ajuste por si el nombre del archivo es largo o el DPI escala contenido
    autoajustar_modal(win, 460, 300)

    # Franja de advertencia roja
    ctk.CTkFrame(win, fg_color="#EF4444", height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FEF2F2", corner_radius=40, width=64, height=64)
    icon_bg.pack(pady=(22, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="🗑", font=ctk.CTkFont(size=28), text_color="#EF4444").place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(win, text="¿Eliminar esta presentación?", font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"), text_color=COLOR_GUINDA).pack()
    ctk.CTkLabel(win, text=nombre_archivo, font=ctk.CTkFont(size=12, slant="italic"), text_color="#64748B").pack(pady=(2, 6))

    ctk.CTkLabel(
        win, 
        text="Se eliminarán todos los datos, versiones y análisis previos de este archivo.",
        font=ctk.CTkFont(size=11), text_color="#94A3B8", justify="center", wraplength=360
    ).pack(padx=20, pady=(0, 16))

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=(0, 20))

    def proceder():
        callback_confirmar()
        win.destroy()

    ctk.CTkButton(btn_row, text="Eliminar", command=proceder, fg_color="#6A1B31", hover_color="#4D1324", text_color="white", width=130, height=36, corner_radius=10).pack(side="left", padx=10)
    ctk.CTkButton(btn_row, text="Cancelar", command=win.destroy, fg_color="transparent", text_color="#64748B", border_width=1, border_color="#E2E8F0", width=130, height=36, corner_radius=10).pack(side="right", padx=10)

def mostrar_modal_cargando(parent, mensaje="Procesando presentación(es)..."):
    """
    Crea un modal visual que indica que el sistema está cargando/procesando.
    No tiene barra de título ni botón de cerrar — el usuario no puede cancelarlo.
    Retorna la ventana para que pueda ser destruida externamente.
    """
    win = ctk.CTkToplevel(parent)
    win.geometry("360x180")
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # 🔒 Blindaje extra por si acaso
    win.protocol("WM_DELETE_WINDOW", lambda: None)
    win.bind("<Escape>",  lambda e: "break")
    win.bind("<Alt-F4>",  lambda e: "break")

    # 🔒 Quita la barra de título y centra sobre la ventana padre.
    # Usa el tamaño REAL del contenido (respetando el escalado/DPI de Windows)
    # para que el icono, el texto y la barra nunca queden cortados.
    def _preparar_ventana():
        win.update_idletasks()
        ancho = max(360, container.winfo_reqwidth() + 24)
        alto  = max(180, container.winfo_reqheight() + 28)
        x = parent.winfo_rootx() + (parent.winfo_width()  // 2) - (ancho // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (alto  // 2)
        win.geometry(f"{ancho}x{alto}+{x}+{y}")
        # overrideredirect/focus_force pueden fallar según el estado
        # momento de la ventana (TclError intermitente): nunca matar la carga.
        try:
            win.overrideredirect(True)
        except Exception:
            pass
        try:
            win.focus_force()
        except Exception:
            pass

    win.after(20, _preparar_ventana)

    # Marco contenedor con borde sutil (reemplaza visualmente la barra de título)
    marco = ctk.CTkFrame(win, fg_color="white", border_width=1, border_color="#E2E8F0", corner_radius=0)
    marco.pack(fill="both", expand=True)

    # Franja superior color Oro (Identidad ESCOM)
    ctk.CTkFrame(marco, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    # Contenedor para centrar
    container = ctk.CTkFrame(marco, fg_color="transparent")
    container.place(relx=0.5, rely=0.5, anchor="center")

    # Icono de carga
    ctk.CTkLabel(
        container,
        text="⏳",
        font=ctk.CTkFont(size=32)
    ).pack(pady=(0, 10))

    # Texto descriptivo
    ctk.CTkLabel(
        container,
        text=mensaje,
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color="#1E293B",
        wraplength=320,
        justify="center"
    ).pack(pady=(0, 15))

    # Barra de progreso indeterminada
    progress = ctk.CTkProgressBar(
        container,
        orientation="horizontal",
        mode="indefinite",
        width=280,
        height=10,
        corner_radius=5,
        progress_color=COLOR_GUINDA,
        fg_color="#F1F5F9"
    )
    progress.pack()
    progress.start()

    return win

def mostrar_modal_advertencia(parent, mensaje, titulo="Atención"):
    """Muestra un modal genérico para advertencias (ej. Errores de IA o red)."""
    win = ctk.CTkToplevel(parent)
    win.title(titulo)
    win.geometry("400x260")
    grab_seguro(win)
    win.configure(fg_color="white")
    win.resizable(False, False)

    # Auto-ajuste: los mensajes de error pueden ser largos; sin esto el botón
    # puede quedar fuera de la ventana según el DPI.
    autoajustar_modal(win, 400, 260)

    # Franja superior color Oro (Identidad ESCOM)
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