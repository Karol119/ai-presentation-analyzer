# app/presentation/widgets/dialogs.py
import customtkinter as ctk

# Colores importados para mantener consistencia
COLOR_GUINDA = "#6A1B31"
COLOR_GUINDA_HOVER = "#4D1324"
COLOR_ORO = "#BC955C"

def mostrar_modal_exito(parent, mensaje):
    win = ctk.CTkToplevel(parent)
    win.title("Éxito")
    win.geometry("400x260")
    win.grab_set()
    win.configure(fg_color="white")
    
    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")
    
    icon_bg = ctk.CTkFrame(win, fg_color="#FDF8F0", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(24, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="✔", font=ctk.CTkFont(size=32, weight="bold"), text_color=COLOR_ORO).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(win, text=mensaje, font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"), text_color=COLOR_GUINDA, wraplength=340).pack(pady=(0, 20))
    ctk.CTkButton(win, text="Cerrar", command=win.destroy, fg_color=COLOR_GUINDA, hover_color=COLOR_GUINDA_HOVER, width=130, height=36, corner_radius=10).pack(pady=(0, 24))

def mostrar_modal_advertencia(parent, mensaje):
    win = ctk.CTkToplevel(parent)
    win.title("Atención")
    win.geometry("420x280")
    win.grab_set()
    win.configure(fg_color="white")

    ctk.CTkFrame(win, fg_color=COLOR_ORO, height=6, corner_radius=0).pack(fill="x")

    icon_bg = ctk.CTkFrame(win, fg_color="#FFFBEB", corner_radius=40, width=72, height=72)
    icon_bg.pack(pady=(24, 8))
    icon_bg.pack_propagate(False)
    ctk.CTkLabel(icon_bg, text="⚠️", font=ctk.CTkFont(size=32), text_color=COLOR_ORO).place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(win, text=mensaje, font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color="#1E293B", wraplength=360, justify="center").pack(pady=(0, 20))
    ctk.CTkButton(win, text="Entendido", command=win.destroy, fg_color=COLOR_GUINDA, hover_color=COLOR_GUINDA_HOVER, width=130, height=36, corner_radius=10).pack(pady=(0, 24))

def confirmar_accion_peligrosa(parent, titulo, mensaje, callback_confirmar):
    """Genérico para eliminar presentaciones o materias."""
    win = ctk.CTkToplevel(parent)
    win.title("Confirmar")
    win.geometry("460x300")
    win.grab_set()
    win.configure(fg_color="white")

    ctk.CTkFrame(win, fg_color="#EF4444", height=6, corner_radius=0).pack(fill="x")
    
    ctk.CTkLabel(win, text="⚠️", font=ctk.CTkFont(size=40)).pack(pady=(20, 10))
    ctk.CTkLabel(win, text=titulo, font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=COLOR_GUINDA).pack()
    ctk.CTkLabel(win, text=mensaje, font=ctk.CTkFont(size=12), text_color="#64748B", wraplength=380, justify="center").pack(pady=10)

    btn_row = ctk.CTkFrame(win, fg_color="transparent")
    btn_row.pack(pady=20)

    def proceder():
        callback_confirmar()
        win.destroy()

    ctk.CTkButton(btn_row, text="Confirmar", command=proceder, fg_color="#EF4444", hover_color="#DC2626", width=120).pack(side="left", padx=10)
    ctk.CTkButton(btn_row, text="Cancelar", command=win.destroy, fg_color="transparent", text_color="#64748B", border_width=1).pack(side="right", padx=10)