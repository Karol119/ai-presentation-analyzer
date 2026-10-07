# app/presentation/widgets/progreso_modal.py
# Ventana modal bloqueante con barra de progreso para procesos en segundo plano.
import customtkinter as ctk
from app.presentation.views.ui_state import ui, estado


class ProgresoModal:
    """
    Muestra una ventana modal con barra de progreso indeterminada.
    Bloquea clics fuera de ella y marca estado["bloqueo_ui"] = True,
    evitando que el usuario salga, regrese al menú o cierre la app
    (el cierre real de la app debe respetar estado["bloqueo_ui"]).
    """

    def __init__(self, mensaje: str = "Procesando..."):
        self._ventana = ctk.CTkToplevel(ui["root"])
        self._ventana.title("Procesando")
        self._ventana.geometry("420x140")
        self._ventana.resizable(False, False)
        self._ventana.transient(ui["root"])
        self._ventana.grab_set()
        self._ventana.attributes("-topmost", True)
        self._ventana.configure(fg_color="white")

        # Evitar que el usuario cierre la ventana modal con la X
        self._ventana.protocol("WM_DELETE_WINDOW", lambda: None)

        ctk.CTkLabel(
            self._ventana,
            text=mensaje,
            font=("Inter", 13, "bold"),
            text_color="#1E293B",
            wraplength=360,
            justify="center",
        ).pack(pady=(25, 10), padx=20)

        self._barra = ctk.CTkProgressBar(self._ventana, mode="indeterminate", width=320)
        self._barra.pack(pady=(0, 15))
        self._barra.start()

        estado["bloqueo_ui"] = True

    def actualizar(self, mensaje: str):
        """Permite cambiar el texto mientras sigue bloqueado."""
        for hijo in self._ventana.winfo_children():
            if isinstance(hijo, ctk.CTkLabel):
                hijo.configure(text=mensaje)
                break

    def cerrar(self):
        try:
            self._barra.stop()
            self._ventana.grab_release()
            self._ventana.destroy()
        finally:
            estado["bloqueo_ui"] = False
