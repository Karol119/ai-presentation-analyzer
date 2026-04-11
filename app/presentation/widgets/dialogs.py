# app/presentation/widgets/dialogs.py
import customtkinter as ctk

# Colores Institucionales ESCOM/IPN
COLOR_GUINDA       = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO          = "#BC955C"

def advertir_presentacion_existente(parent, mensaje):
    """
    Muestra un modal específico para notificar que una o varias 
    presentaciones ya se encuentran registradas en el sistema.
    """
    win = ctk.CTkToplevel(parent)
    win.title("Archivo Duplicado")
    win.geometry("420x280")
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

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
    win.grab_set()
    win.configure(fg_color="white")
    win.resizable(False, False)

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

    ctk.CTkButton(btn_row, text="Eliminar", command=proceder, fg_color="#EF4444", hover_color="#DC2626", text_color="white", width=130, height=36, corner_radius=10).pack(side="left", padx=10)
    ctk.CTkButton(btn_row, text="Cancelar", command=win.destroy, fg_color="transparent", text_color="#64748B", border_width=1, border_color="#E2E8F0", width=130, height=36, corner_radius=10).pack(side="right", padx=10)

def mostrar_modal_cargando(parent, mensaje="Procesando presentación(es)..."):
    """
    Crea un modal visual que indica que el sistema está cargando/procesando.
    Retorna la ventana para que pueda ser destruida externamente.
    """
    win = ctk.CTkToplevel(parent)
    win.title("Cargando")
    win.geometry("360x180")
    win.grab_set()  # Bloquea interacción con la ventana principal
    win.configure(fg_color="white")
    win.resizable(False, False)
    
    # Franja superior color Oro (Identidad)
    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")
    
    # Contenedor para centrar
    container = ctk.CTkFrame(win, fg_color="transparent")
    container.place(relx=0.5, rely=0.5, anchor="center")
    
    # Icono o Texto de carga
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
    
    # ✅ Barra de progreso indeterminada (se mueve constantemente)
    progress = ctk.CTkProgressBar(
        container, 
        orientation="horizontal",
        mode="indefinite", # Modo carga
        width=280, 
        height=10, 
        corner_radius=5,
        progress_color=COLOR_GUINDA, 
        fg_color="#F1F5F9"
    )
    progress.pack()
    progress.start() # Inicia la animación
    
    return win # Retornamos la ventana para poder cerrarla después