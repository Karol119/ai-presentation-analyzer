# app/presentation/widgets/presentation_mode/presentation_controls.py
"""
Widget de Controles Inferiores para el Modo Presentación (TT2).
Contiene los botones Anterior, Siguiente, Contador y Salir.
"""

import customtkinter as ctk
from app.presentation.views.navigator import ir_a_principal

class PresentationControls(ctk.CTkFrame):
    def __init__(self, master, visor_referencia, **kwargs):
        # Usamos el color de fondo estándar de tus paneles para mantener la consistencia visual
        super().__init__(master, fg_color="#2b2b2b", corner_radius=8, height=70, **kwargs)
        
        self.visor = visor_referencia  # Guardamos la referencia para enviarle órdenes de paginación
        
        # Configurar columnas del grid para distribución simétrica:
        # Columna 0 (Izquierda: Salir), Columna 1 (Centro: Navegación), Columna 2 (Derecha: Espaciador)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # 1. BOTÓN IZQUIERDO: Salir de la clase
        self.btn_salir = ctk.CTkButton(
            self, 
            text="🚪 Salir de Clase", 
            fg_color="#cf6679",       # Tono rojizo/salmón para alertas o salidas
            hover_color="#b05464", 
            width=140,
            command=ir_a_principal   # Llama directo al enrutador para desmontar todo
        )
        self.btn_salir.grid(row=0, column=0, sticky="w", padx=20, pady=15)

        # 2. CONTENEDOR CENTRAL: Navegación de Diapositivas
        self.frame_central = ctk.CTkFrame(self, fg_color="transparent")
        # CORREGIDO: Se eliminó sticky="center" ya que grid centra automáticamente por defecto
        self.frame_central.grid(row=0, column=1, pady=15)
        
        # Botón Anterior
        self.btn_anterior = ctk.CTkButton(
            self.frame_central, 
            text="◀ Anterior", 
            width=100,
            command=self._handler_anterior
        )
        self.btn_anterior.pack(side="left", padx=10)
        
        # Indicador de posición (Label dinámico)
        self.label_contador = ctk.CTkLabel(
            self.frame_central, 
            text=f"Diapositiva: {self.visor.pagina_actual + 1} / {self.visor.total_paginas}",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.label_contador.pack(side="left", padx=15)
        
        # Botón Siguiente
        self.btn_siguiente = ctk.CTkButton(
            self.frame_central, 
            text="Siguiente ▶", 
            width=100,
            command=self._handler_siguiente
        )
        self.btn_siguiente.pack(side="left", padx=10)

        # Inicializar el estado de deshabilitación de los botones
        self._actualizar_UI_controles()

    def _handler_anterior(self):
        """Ordena al visor ir atrás y refresca el contador si hubo éxito."""
        if self.visor.retroceder_pagina():
            self._actualizar_UI_controles()

    def _handler_siguiente(self):
        """Ordena al visor ir adelante y refresca el contador si hubo éxito."""
        if self.visor.avanzar_pagina():
            self._actualizar_UI_controles()

    def _actualizar_UI_controles(self):
        """Actualiza el texto del contador y apaga/prende botones según los límites."""
        pagina_humana = self.visor.pagina_actual + 1
        total = self.visor.total_paginas
        
        # Actualizar texto del label
        self.label_contador.configure(text=f"Diapositiva: {pagina_humana} / {total}")
        
        # Deshabilitar "Anterior" si estamos en la primera diapositiva
        if self.visor.pagina_actual == 0:
            self.btn_anterior.configure(state="disabled")
        else:
            self.btn_anterior.configure(state="normal")
            
        # Deshabilitar "Siguiente" si estamos en la última diapositiva
        if self.visor.pagina_actual >= total - 1:
            self.btn_siguiente.configure(state="disabled")
        else:
            self.btn_siguiente.configure(state="normal")