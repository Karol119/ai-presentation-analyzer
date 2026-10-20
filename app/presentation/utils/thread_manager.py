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
        """
        Ejecuta la tarea y GARANTIZA que siempre se notifique a la UI:
        - Si target_task lanza una excepción, se convierte en un resultado
          controlado (False, mensaje) que la UI mostrará como error modal.
        - Si la sincronización con Tk falla, se reporta en consola sin
          dejar la UI bloqueada con el modal de carga colgado.
        """
        try:
            result = target_task()
        except Exception as e:
            result = (False, f"Error inesperado al procesar: {e}")

        try:
            def _finalizar():
                # Protección extra: un error del callback (ej. TclError de Tk)
                # no debe tumbar el bucle principal ni dejar la UI bloqueada.
                try:
                    on_finished_callback(result)
                except Exception as e:
                    print(f"[async] Error en el callback de UI: {e}")

            # Sincronización segura con el hilo de la interfaz (Main Thread)
            ui["root"].after(0, _finalizar)
        except Exception as e:
            # Si la ventana principal ya no existe o Tk está en cierre abrupto
            print(f"[async] No se pudo sincronizar con la UI: {e}")

    # Configuración del hilo como Demonio para que finalice con la aplicación
    worker_thread = threading.Thread(target=task_wrapper, daemon=True)
    worker_thread.start()