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