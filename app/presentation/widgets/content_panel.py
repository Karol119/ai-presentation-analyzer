# app/presentation/widgets/content_panel.py
import customtkinter as ctk
from tkinter import filedialog

class ContentArea(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color="transparent")
        self.controller = controller
        self.current_subject = None
        
        # Label de título
        self.title_label = ctk.CTkLabel(self, text="Selecciona una materia", font=("Segoe UI", 20, "bold"))
        self.title_label.pack(pady=20)

        self.cards_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="both", expand=True, padx=20)

    def load_subject(self, subject_name):
        self.current_subject = subject_name
        self.title_label.configure(text=subject_name)
        self.refresh_cards()

    def refresh_cards(self):
        # Limpiar tarjetas anteriores
        for child in self.cards_frame.winfo_children():
            child.destroy()
            
        # Obtener archivos del controlador
        files = self.controller.get_files_by_subject(self.current_subject)
        
        # Crear tarjeta de "Subir"
        self._make_upload_button()
        
        # Crear tarjetas de archivos
        for fname, _ in files:
            self._make_file_card(fname)

    def _make_upload_button(self):
        btn = ctk.CTkButton(self.cards_frame, text="+ Subir", command=self._pick_files)
        btn.pack(pady=10)

    def _pick_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("Presentaciones", "*.pptx *.pdf")])
        if paths:
            # LE PASAMOS LAS RUTAS AL CONTROLADOR
            self.controller.upload_presentations(self.current_subject, paths)
            self.refresh_cards()

    def _make_file_card(self, name):
        # Aquí iría el diseño de tu tarjeta azul con el ícono de hoja
        card = ctk.CTkFrame(self.cards_frame, fg_color="white", corner_radius=10)
        card.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(card, text=f"📄 {name}", text_color="#1E40AF").pack(side="left", padx=10)