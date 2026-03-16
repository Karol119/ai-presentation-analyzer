# app/presentation/views/gui.py
import customtkinter as ctk
from app.core.controller.presentation_controller import PresentationController
from app.presentation.widgets.sidebar import Sidebar
from app.presentation.widgets.content_panel import ContentArea

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 1. Instanciar Controlador
        self.controller = PresentationController()
        
        # 2. Configurar Ventana
        self.title("Sistema de Gestión de Presentaciones")
        self.geometry("1200x700")
        self.configure(fg_color="#F1F5F9")

        # 3. Layout General
        self.sidebar = Sidebar(self, self.controller, self._on_subject_selected)
        self.sidebar.pack(side="left", fill="y")
        
        self.content_area = ContentArea(self, self.controller)
        self.content_area.pack(side="right", fill="both", expand=True)

    def _on_subject_selected(self, subject_name):
        """Callback que se ejecuta cuando cambias de materia en el sidebar"""
        self.content_area.load_subject(subject_name)