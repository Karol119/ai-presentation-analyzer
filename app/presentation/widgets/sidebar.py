# app/presentation/widgets/sidebar.py
import customtkinter as ctk

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, controller, on_select):
        super().__init__(master, fg_color="white", width=210, corner_radius=0, 
                         border_width=1, border_color="#E2E8F0")
        self.controller = controller
        self.on_select = on_select # Función que se llama en gui.py
        self.buttons = {}
        self.active_subject = None

        self.pack_propagate(False)
        self._build_sidebar()

    def _build_sidebar(self):
        # Título de sección
        ctk.CTkLabel(
            self, text="MATERIAS",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#94A3B8",
        ).pack(anchor="w", padx=16, pady=(18, 8))

        # Contenedor scrollable para las materias
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll_frame.pack(fill="both", expand=True, padx=8)

        # Cargar materias desde el controlador
        subjects = self.controller.get_subjects()
        for s in subjects:
            self._add_subject_item(s)

        # Botón de acción al final
        self._add_action_buttons()

    def _add_subject_item(self, name):
        """Crea un botón estilizado para cada materia"""
        row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent", height=40, cursor="hand2")
        row.pack(fill="x", pady=2)
        row.pack_propagate(False)

        # Indicador visual azul lateral
        indicator = ctk.CTkFrame(row, width=3, fg_color="transparent", corner_radius=2)
        indicator.pack(side="left", fill="y", padx=(4, 0), pady=6)

        label = ctk.CTkLabel(
            row, text=name,
            font=ctk.CTkFont(size=13),
            text_color="#334155",
            anchor="w",
        )
        label.pack(side="left", fill="both", expand=True, padx=8)

        # Eventos de clic
        for w in (row, label):
            w.bind("<Button-1>", lambda e, n=name: self._select_materia(n))

        # Guardar referencias para cambiar estilos
        self.buttons[name] = {"frame": row, "indicator": indicator, "label": label}

    def _select_materia(self, name):
        # 1. Resetear estilos de todos los botones
        for n, widgets in self.buttons.items():
            widgets["frame"].configure(fg_color="transparent")
            widgets["indicator"].configure(fg_color="transparent")
            widgets["label"].configure(text_color="#334155", font=ctk.CTkFont(size=13))

        # 2. Aplicar estilo activo al seleccionado
        self.buttons[name]["frame"].configure(fg_color="#EFF6FF")
        self.buttons[name]["indicator"].configure(fg_color="#2563EB")
        self.buttons[name]["label"].configure(text_color="#1D4ED8", font=ctk.CTkFont(size=13, weight="bold"))

        # 3. Notificar a la Vista Principal (gui.py)
        self.on_select(name)

    def _add_action_buttons(self):
        """Botón inferior para agregar materias"""
        ctk.CTkFrame(self, height=1, fg_color="#E2E8F0").pack(fill="x", pady=6)
        
        btn = ctk.CTkButton(
            self, text="＋  Agregar materia",
            font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color="#F1F5F9",
            text_color="#64748B", border_width=1, border_color="#CBD5E1",
            corner_radius=8, height=36, anchor="w",
            command=lambda: print("Abrir modal de agregar...") # Esto debería ir al controlador
        )
        btn.pack(fill="x", padx=10, pady=(0, 14))