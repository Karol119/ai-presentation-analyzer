# app/presentation/utils/thread_manager.py
import threading
from typing import Callable, Any
from app.presentation.views.ui_state import ui

def ejecutar_tarea_asincrona(
    target_task: Callable[[], Any], 
    on_finished_callback: Callable[[Any], None]
) -> None:
    """
    Ejecuta una lógica de negocio en un hilo de ejecución independiente para 
    evitar el bloqueo del bucle de eventos principal (Main Loop) de la interfaz.
    
    Args:
        target_task: Función que contiene la lógica pesada (capa de controlador).
        on_finished_callback: Función que procesará el resultado en el hilo principal.
    """
    def task_wrapper() -> None:
        # Ejecución de la lógica en el hilo secundario (Worker Thread)
        result = target_task()
        
        # Sincronización con el hilo de la interfaz (Main Thread)
        # Se utiliza el método after para garantizar la seguridad de hilos en Tkinter
        ui["root"].after(0, lambda: on_finished_callback(result))

    # Configuración del hilo como Demonio para que finalice con la aplicación
    worker_thread = threading.Thread(target=task_wrapper, daemon=True)
    worker_thread.start()