#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Presentación automática de las presentaciones cargadas en una materia.

El programa:
  1. Pregunta la materia y el grupo escolar (o los recibe por argumentos).
  2. Lee qué presentaciones ya tienen `"presentada": true` y las omite.
  3. Para cada presentación pendiente abre un proceso independiente de la app.
     Los procesos se lanzan en secuencia (para que cada uno alcance a marcar
     `presentada=true`), pero se ejecutan en paralelo.
  4. Cada proceso llena el formulario "Configuración de Sesión" con el grupo
     y un tiempo de clase variable (igual, menor o mayor que el JSON).
  5. Cada proceso avanza sus diapositivas durante el tiempo del JSON.
  6. Al iniciar la proyección se marca `"presentada": true` y se avisa al
     orquestador para que lance el siguiente proceso sin esperar a que termine.

Por defecto los procesos trabajan en modo headless (sin ventanas visibles),
para que las proyecciones no se encimen. Usa --visible si quieres verlas.

Uso normal:
    python tests/presentacion/pruebas/presentar_presentaciones.py

Uso sin preguntas:
    python tests/presentacion/pruebas/presentar_presentaciones.py \
        --materia "Sistemas distribuidos" --grupo 7CM1

Opciones:
    --dry-run           Solo muestra el plan, sin abrir la aplicación.
    --repetir           Incluye también las que ya tienen presentada=true.
    --limite N          Toma únicamente las primeras N presentaciones.
    --escala-tiempo F   Multiplica los tiempos del JSON (0.05 para prueba rápida).
    --visible           Muestra las ventanas (se encimarán entre sí).
    --cerrar            Cierra cada app al terminar.
    --sin-mensaje       No pide confirmación ni muestra el cuadro final.
    --timeout-inicio S  Espera máxima para la señal de inicio de cada proceso.
    --timeout-total S   Duración máxima permitida a cada proceso.

Requisitos:
    pillow (capturas de evidencia)
    screeninfo (detección de monitores; la app lo usa para el proyector)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Trabajar siempre desde la raíz del proyecto para que las rutas relativas de
# la base de datos y de storage funcionen igual que al ejecutar main.py.
os.chdir(RAIZ)

try:
    import pyautogui
except ImportError:  # pragma: no cover
    pyautogui = None

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None


# ---------------------------------------------------------------------------
# Rutas y estado global
# ---------------------------------------------------------------------------

PRESENTACIONES = RAIZ / "tests" / "presentacion" / "presentaciones"
EVIDENCIAS_BASE = RAIZ / "tests" / "presentacion" / "evidencias"

MATERIA = ""
GRUPO = ""
PLAN: list[dict] = []
INDICE = 0
CARPETA_EVIDENCIAS: Path | None = None
LOG_PATH: Path | None = None
CONTADOR_CAPTURAS = 0
RESUMEN: list[str] = []
FALLOS: list[str] = []
APP_CERRADA = False
MODO_WORKER = False
HEADLESS = False
SIN_CAPTURAS = False
ARCHIVO_INICIO: Path | None = None
ARCHIVO_RESULTADO: Path | None = None
ETIQUETA = ""


def log(mensaje: str) -> None:
    texto = f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}"
    print(texto, flush=True)
    if LOG_PATH:
        try:
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(texto + "\n")
        except Exception:
            pass


def normalizar(texto: str) -> str:
    """Normaliza para comparar nombres sin acentos ni mayúsculas."""
    descompuesto = unicodedata.normalize("NFD", texto or "")
    sin_acentos = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return " ".join(sin_acentos.casefold().split())


def sanear(nombre: str) -> str:
    import re

    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)
    nombre = re.sub(r"_+", "_", nombre).strip("._-")
    return nombre[:110] or "captura"


def _escribir_json_atomico(ruta: Path, data: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporal, ruta)


def _configurar_sqlite_timeout() -> None:
    """
    Varios procesos de la app escriben reportes en la misma base SQLite.
    Ampliamos el tiempo de espera para que no fallen por bloqueos momentáneos.
    """
    import sqlite3

    original = sqlite3.connect
    if getattr(original, "_timeout_paralelo", False):
        return

    def connect_con_timeout(*args, **kwargs):
        kwargs.setdefault("timeout", 60)
        return original(*args, **kwargs)

    connect_con_timeout._timeout_paralelo = True  # type: ignore[attr-defined]
    sqlite3.connect = connect_con_timeout  # type: ignore[assignment]


def _preparar_visor_sin_render(visor) -> None:
    """
    En modo headless no hace falta rasterizar las diapositivas. Se conserva el
    cambio de página y el aviso `on_pagina_cambiada`, que es lo que usa la app
    para sincronizar la proyección y contabilizar el tiempo.
    """
    if visor is None:
        return

    def sin_render():
        return None

    def avanzar(event=None):
        try:
            if visor.pagina_actual < visor.total_paginas - 1:
                visor.pagina_actual += 1
                if visor.on_pagina_cambiada:
                    visor.on_pagina_cambiada(visor.pagina_actual)
        except Exception:
            pass
        return "break"

    def retroceder(event=None):
        try:
            if visor.pagina_actual > 0:
                visor.pagina_actual -= 1
                if visor.on_pagina_cambiada:
                    visor.on_pagina_cambiada(visor.pagina_actual)
        except Exception:
            pass
        return "break"

    visor.renderizar_slide_actual = sin_render
    visor.avanzar_pagina = avanzar
    visor.retroceder_pagina = retroceder


def capturar(nombre: str) -> None:
    """Captura todas las pantallas (sin mover el mouse ni usar el teclado)."""
    global CONTADOR_CAPTURAS
    if CARPETA_EVIDENCIAS is None or SIN_CAPTURAS:
        return
    CONTADOR_CAPTURAS += 1
    destino = CARPETA_EVIDENCIAS / f"{CONTADOR_CAPTURAS:02d}_{sanear(nombre)}.png"
    try:
        from PIL import ImageGrab

        try:
            imagen = ImageGrab.grab(all_screens=True)
        except TypeError:
            imagen = ImageGrab.grab()
        imagen.save(destino)
        log(f"Captura: {destino.name}")
    except Exception as exc:
        # Fallback si Pillow no puede capturar el escritorio.
        if pyautogui is not None:
            try:
                pyautogui.screenshot(str(destino))
                log(f"Captura: {destino.name}")
                return
            except Exception:
                pass
        log(f"No se pudo capturar la pantalla: {exc}")


# ---------------------------------------------------------------------------
# Lectura del catálogo y del JSON de tiempos
# ---------------------------------------------------------------------------


def materias_activas() -> list[str]:
    from app.core.controller.subject_controller import obtener_catalogo_materias_activas

    return obtener_catalogo_materias_activas()


def carpeta_materia(nombre: str) -> Path | None:
    """Localiza la carpeta de JSON/PPTX de la materia, tolerando acentos."""
    exacta = PRESENTACIONES / nombre
    if exacta.is_dir():
        return exacta
    if PRESENTACIONES.is_dir():
        objetivo = normalizar(nombre)
        for carpeta in PRESENTACIONES.iterdir():
            if carpeta.is_dir() and normalizar(carpeta.name) == objetivo:
                return carpeta
    return None


def resolver_json(materia: str, nombre_presentacion: str, ruta_pptx: str, ruta_pdf: str) -> Path | None:
    """
    Busca el JSON de tiempos de una presentación.

    Prioridad:
      1. tests/presentacion/presentaciones/<materia>/<stem>.json
      2. junto al PPTX o al PDF de storage (<stem>.json)
    """
    stem = Path(nombre_presentacion).stem
    carpeta = carpeta_materia(materia)
    candidatos: list[Path] = []

    if carpeta:
        exacto = carpeta / f"{stem}.json"
        if exacto.exists():
            candidatos.append(exacto)
        # Búsqueda tolerante a diferencias de normalización Unicode.
        objetivo = normalizar(stem)
        for p in carpeta.glob("*.json"):
            if normalizar(p.stem) == objetivo:
                candidatos.append(p)

    for ruta in (ruta_pptx, ruta_pdf):
        if ruta:
            candidatos.append(Path(ruta).with_suffix(".json"))

    vistos = set()
    for p in candidatos:
        clave = str(p).casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        if p.exists() and p.is_file():
            return p
    return None


def paginas_pdf(ruta_pdf: str) -> int | None:
    if not fitz or not ruta_pdf or not Path(ruta_pdf).exists():
        return None
    try:
        with fitz.open(ruta_pdf) as doc:
            return doc.page_count
    except Exception:
        return None


def construir_plan(materia: str, limite: int | None = None) -> list[dict]:
    """
    Recupera las presentaciones cargadas y visibles de la materia y valida que
    cada una tenga análisis y JSON de tiempos.
    """
    from app.core.controller.subject_controller import (
        obtener_archivos_materia,
        obtener_id_materia,
    )

    id_materia = obtener_id_materia(materia)
    if not id_materia:
        raise RuntimeError(f"No se encontró la materia '{materia}' en la base de datos.")

    archivos = obtener_archivos_materia(id_materia)
    if limite:
        archivos = archivos[:limite]

    if not archivos:
        raise RuntimeError(f"La materia '{materia}' no tiene presentaciones cargadas.")

    plan: list[dict] = []
    errores: list[str] = []

    for nombre, ruta_pptx, _ruta_thumb, analisis, ruta_pdf in archivos:
        if not analisis:
            errores.append(f"{nombre}: no tiene análisis de IA (la app no permite presentarla).")
            continue

        ruta_json = resolver_json(materia, nombre, ruta_pptx, ruta_pdf)
        if not ruta_json:
            errores.append(
                f"{nombre}: no se encontró su JSON de tiempos "
                f"(se esperaba en tests/presentacion/presentaciones/{materia}/)."
            )
            continue

        try:
            data = json.loads(ruta_json.read_text(encoding="utf-8"))
            tiempos = [
                float(s["tiempo_segundos"])
                for s in data.get("tiempo_por_diapositiva", [])
            ]
        except Exception as exc:
            errores.append(f"{nombre}: JSON inválido ({exc}).")
            continue

        if not tiempos:
            errores.append(f"{nombre}: el JSON no contiene tiempos por diapositiva.")
            continue

        total_json = float(data.get("tiempo_total_segundos") or sum(tiempos))
        total_sum = sum(tiempos)
        paginas = paginas_pdf(ruta_pdf)

        if paginas is not None and paginas != len(tiempos):
            errores.append(
                f"{nombre}: el PDF tiene {paginas} diapositivas y el JSON {len(tiempos)}. "
                "Regenera el JSON antes de presentar."
            )
            continue

        plan.append(
            {
                "nombre": nombre,
                "ruta_pptx": ruta_pptx,
                "ruta_pdf": ruta_pdf,
                "ruta_json": str(ruta_json),
                "tiempos": tiempos,
                "total_json": total_json,
                "total_sum": total_sum,
                "total_diapositivas": len(tiempos),
                "presentada_previa": bool(data.get("presentada", False)),
            }
        )

    if errores:
        detalle = "\n  - " + "\n  - ".join(errores)
        raise RuntimeError(
            "No se puede iniciar la presentación porque hay presentaciones "
            "cargadas que no están listas:" + detalle
        )

    return plan


def asignar_tiempos_docente(plan: list[dict]) -> None:
    """
    Asigna un tiempo de clase variable a cada presentación.

    Se alternan tres modos:
      - igual: entero de minutos más cercano al total del JSON.
      - menor: al menos un minuto por debajo del total.
      - mayor: al menos un minuto por encima del total.
    """
    modos = ("igual", "menor", "mayor")

    for i, item in enumerate(plan):
        modo = modos[i % len(modos)]
        total = item["total_sum"]
        total_min = total / 60.0

        if modo == "igual":
            minutos = int(round(total_min))
        elif modo == "menor":
            minutos = int(round(total_min)) - 1
        else:
            minutos = int(total_min) + (1 if total_min == int(total_min) else 0)
            if minutos * 60 <= total:
                minutos += 1

        minutos = max(1, min(90, minutos))

        # Garantizar estrictamente la relación solicitada cuando sea posible.
        if modo == "menor" and minutos * 60 >= total:
            minutos = max(1, minutos - 1)
        if modo == "mayor" and minutos * 60 <= total:
            minutos = min(90, minutos + 1)

        item["modo_tiempo"] = modo
        item["tiempo_min"] = minutos
        item["tiempo_seg"] = minutos * 60


def describir_plan(plan: list[dict]) -> None:
    log("=" * 78)
    log(f"Materia: {MATERIA}")
    log(f"Grupo escolar: {GRUPO}")
    log(f"Presentaciones a proyectar: {len(plan)}")
    log("Tiempos de clase asignados (se alternan igual / menor / mayor):")
    for i, item in enumerate(plan, 1):
        total_fmt = f"{int(item['total_sum']) // 60:02d}:{int(item['total_sum']) % 60:02d}"
        log(
            f"  {i}. {item['nombre']} | {item['total_diapositivas']} diapositivas | "
            f"JSON {total_fmt} | docente {item['tiempo_min']} min ({item['modo_tiempo']})"
        )
        if item["presentada_previa"]:
            log("     Nota: el JSON ya tenía presentada=true; se volverá a marcar al iniciar.")
    log("=" * 78)


# ---------------------------------------------------------------------------
# Utilidades de widgets Tk/CTk
# ---------------------------------------------------------------------------


def iterar_widgets(widget):
    yield widget
    try:
        hijos = widget.winfo_children()
    except Exception:
        return
    for hijo in hijos:
        yield from iterar_widgets(hijo)


def buscar_toplevel(titulo: str):
    from app.presentation.views.ui_state import ui

    root = ui.get("root")
    if not root:
        return None
    for w in iterar_widgets(root):
        try:
            if w.winfo_toplevel() is w and w.title() == titulo:
                return w
        except Exception:
            continue
    return None


def buscar_boton(widget, texto: str):
    import customtkinter as ctk

    if widget is None:
        return None
    for w in iterar_widgets(widget):
        if isinstance(w, ctk.CTkButton):
            try:
                if texto in str(w.cget("text")):
                    return w
            except Exception:
                continue
    return None


def buscar_entry_placeholder(widget, fragmento: str):
    import customtkinter as ctk

    if widget is None:
        return None
    for w in iterar_widgets(widget):
        if isinstance(w, ctk.CTkEntry):
            try:
                if fragmento in str(w.cget("placeholder_text")):
                    return w
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Máquina de estados de la presentación
# ---------------------------------------------------------------------------


def _item_actual() -> dict | None:
    if 0 <= INDICE < len(PLAN):
        return PLAN[INDICE]
    return None


def _fallo_actual(mensaje: str) -> None:
    item = _item_actual()
    if item and item.get("finalizado"):
        return
    nombre = item["nombre"] if item else "?"
    log(f"ERROR en '{nombre}': {mensaje}")
    FALLOS.append(f"{nombre}: {mensaje}")
    if item:
        item["error"] = mensaje
        item["cancelado"] = True
    # Intentar cerrar una proyección que haya quedado abierta.
    try:
        from app.presentation.views import presentation_gui

        ventana = presentation_gui._ventana_proyeccion
        if ventana is not None and ventana.winfo_exists():
            ventana.cerrar()
    except Exception:
        pass
    _volver_y_siguiente(item)


def _siguiente() -> None:
    global INDICE

    if APP_CERRADA:
        return

    if INDICE >= len(PLAN):
        _finalizar()
        return

    item = _item_actual()
    log("-" * 78)
    log(
        f"Presentación {INDICE + 1}/{len(PLAN)}: {item['nombre']} | "
        f"{item['total_diapositivas']} diapositivas | docente {item['tiempo_min']} min "
        f"({item['modo_tiempo']})"
    )

    from app.presentation.views import navigator
    from app.presentation.views import main_gui

    try:
        if navigator.vista_actual() != "main":
            navigator.ir_a_principal()
            main_gui._seleccionar_materia(MATERIA)
            from app.presentation.views.ui_state import ui

            ui["root"].after(700, _abrir_presentacion)
        else:
            _abrir_presentacion()
    except Exception as exc:
        _fallo_actual(f"no se pudo volver a la pantalla principal: {exc}")


def _abrir_presentacion() -> None:
    item = _item_actual()
    if not item or item.get("cancelado"):
        return

    from app.presentation.views import main_gui, navigator
    from app.presentation.views.ui_state import ui

    try:
        main_gui._seleccionar_materia(MATERIA)
        navigator.ir_a_presentacion(MATERIA, item["nombre"], item["ruta_pdf"])

        if HEADLESS:
            from app.presentation.views import presentation_gui

            _preparar_visor_sin_render(presentation_gui._visor_panel)

        ui["root"].after(1100, _abrir_formulario)
    except Exception as exc:
        _fallo_actual(f"no se pudo abrir la vista de presentación: {exc}")


def _abrir_formulario(intento: int = 0) -> None:
    """
    Pulsa "📺 Presentar". La llamada abre el formulario modal y se queda
    esperando; por eso programamos su llenado con after() antes de invocar.
    """
    item = _item_actual()
    if not item or item.get("cancelado"):
        return

    from app.presentation.views import presentation_gui
    from app.presentation.views.ui_state import ui

    panel = presentation_gui._datos_panel
    visor = presentation_gui._visor_panel
    if not visor or getattr(visor, "total_paginas", 0) <= 0:
        if intento < 15:
            ui["root"].after(400, lambda: _abrir_formulario(intento + 1))
        else:
            _fallo_actual("el visor no terminó de cargar el PDF.")
        return

    boton = buscar_boton(panel, "Presentar")
    if not boton:
        _fallo_actual("no se encontró el botón 'Presentar' en la vista de presentación.")
        return

    # Desactivar la reanudación automática: aunque el grupo ya exista, cada
    # presentación debe comenzar desde la diapositiva 1. Se restaura al salir.
    original_obtener_reporte = presentation_gui.orquestar_obtener_reporte_tiempo
    original_lanzar = presentation_gui._lanzar_proyeccion

    def _sin_reporte_previo(*_args, **_kwargs):
        return None

    def _lanzar_con_escala(root, ruta_pdf, indice_actual, pos_x, pos_y, ancho, alto):
        """
        La app toma el ancho/alto de screeninfo en píxeles físicos, pero Tk
        interpreta geometry() en unidades lógicas. En pantallas con escalado
        (125 %, 150 %) eso crea una ventana más grande que el monitor. Aquí
        convertimos a unidades lógicas antes de crear la proyección.
        """
        try:
            from customtkinter import ScalingTracker

            escala = ScalingTracker.get_window_scaling(root) or 1.0
            if escala > 0:
                # Si la app no pudo leer los monitores, usa 800x600. En ese
                # caso forzamos la pantalla principal completa.
                if ancho <= 800 and alto <= 600:
                    ancho = root.winfo_screenwidth()
                    alto = root.winfo_screenheight()
                    pos_x = 0
                    pos_y = 0
                ancho = int(ancho / escala)
                alto = int(alto / escala)
                pos_x = int(pos_x / escala)
                pos_y = int(pos_y / escala)
        except Exception:
            pass

        if HEADLESS:
            # La proyección se crea a tamaño completo, pero fuera del escritorio.
            pos_x = 10000
            pos_y = 10000

        resultado = original_lanzar(
            root, ruta_pdf, indice_actual, pos_x, pos_y, ancho, alto
        )

        if HEADLESS:
            try:
                ventana = presentation_gui._ventana_proyeccion
                if ventana is not None and ventana.winfo_exists():
                    _preparar_visor_sin_render(ventana.visor)
            except Exception:
                pass
        return resultado

    presentation_gui.orquestar_obtener_reporte_tiempo = _sin_reporte_previo
    presentation_gui._lanzar_proyeccion = _lanzar_con_escala
    ui["root"].after(50, _mover_formulario_fuera)
    ui["root"].after(350, _completar_formulario)
    # Si el formulario no se puede llenar, cerrarlo para no bloquear la app.
    ui["root"].after(15000, _abortar_formulario_si_sigue)
    try:
        boton.invoke()
    except Exception as exc:
        _fallo_actual(f"no se pudo abrir el formulario de sesión: {exc}")
        return
    finally:
        presentation_gui.orquestar_obtener_reporte_tiempo = original_obtener_reporte
        presentation_gui._lanzar_proyeccion = original_lanzar

    # Si el formulario se llenó correctamente, la proyección ya debe existir.
    ui["root"].after(300, lambda: _proyeccion_iniciada(item))


def _mover_formulario_fuera() -> None:
    """En modo headless, mantiene el formulario fuera de la vista."""
    if not HEADLESS:
        return
    formulario = buscar_toplevel("Configuración de Sesión")
    if formulario is None:
        return
    try:
        formulario.attributes("-alpha", 1.0)
        formulario.geometry("+10000+10000")
    except Exception:
        pass


def _abortar_formulario_si_sigue() -> None:
    """Cierra el formulario modal si quedó abierto por un fallo de llenado."""
    formulario = buscar_toplevel("Configuración de Sesión")
    if formulario is None:
        return
    log("El formulario de sesión sigue abierto; se cierra para continuar.")
    try:
        formulario.grab_release()
    except Exception:
        pass
    try:
        formulario.destroy()
    except Exception:
        pass


def _completar_formulario(intento: int = 0) -> None:
    import customtkinter as ctk

    from app.presentation.views.ui_state import ui

    item = _item_actual()
    if not item or item.get("cancelado"):
        return

    formulario = buscar_toplevel("Configuración de Sesión")
    if formulario is None:
        if intento < 25:
            ui["root"].after(200, lambda: _completar_formulario(intento + 1))
        else:
            log("No apareció el formulario 'Configuración de Sesión'.")
        return

    try:
        # 1. Forzar "Crear Nuevo" para capturar el grupo indicado.
        segmentado = next(
            (w for w in iterar_widgets(formulario) if isinstance(w, ctk.CTkSegmentedButton)),
            None,
        )
        if segmentado is not None:
            try:
                segmentado.set("Crear Nuevo")
                comando = getattr(segmentado, "_command", None)
                if comando:
                    comando("Crear Nuevo")
            except Exception:
                pass

        # 2. Grupo escolar.
        entry_grupo = buscar_entry_placeholder(formulario, "Ej. 3CM2")
        if entry_grupo is None:
            raise RuntimeError("no se encontró el campo de grupo.")
        entry_grupo.delete(0, "end")
        entry_grupo.insert(0, GRUPO)

        # 3. Tiempo estimado: es el CTkEntry que no es el campo de grupo.
        entries = [w for w in iterar_widgets(formulario) if isinstance(w, ctk.CTkEntry)]
        entry_tiempo = None
        for w in entries:
            if w is entry_grupo:
                continue
            try:
                if str(w.get()).strip().isdigit():
                    entry_tiempo = w
                    break
            except Exception:
                continue
        if entry_tiempo is None:
            raise RuntimeError("no se encontró el campo de tiempo.")
        entry_tiempo.delete(0, "end")
        entry_tiempo.insert(0, str(item["tiempo_min"]))

        # 4. Dejar la pantalla que la app eligió por defecto: con un solo
        # monitor será la principal; con proyector, la segunda pantalla.
        formulario.update_idletasks()
        try:
            formulario.attributes("-topmost", True)
            formulario.lift()
            formulario.update()
        except Exception:
            pass
        time.sleep(0.35)
        capturar(f"{Path(item['nombre']).stem}_formulario")

        log(
            f"Formulario: grupo={GRUPO} | tiempo={item['tiempo_min']} min "
            f"({item['modo_tiempo']} respecto al JSON)"
        )

        boton_iniciar = buscar_boton(formulario, "Iniciar Proyección")
        if boton_iniciar is None:
            raise RuntimeError("no se encontró el botón 'Iniciar Proyección'.")
        boton_iniciar.invoke()
    except Exception as exc:
        log(f"No se pudo completar el formulario: {exc}")
        try:
            formulario.grab_release()
        except Exception:
            pass
        try:
            formulario.destroy()
        except Exception:
            pass


def _proyeccion_iniciada(item: dict | None = None) -> None:
    item = item or _item_actual()
    if not item or item.get("cancelado") or item.get("finalizado"):
        return

    from app.presentation.views import presentation_gui
    from app.presentation.views.ui_state import ui

    ventana = presentation_gui._ventana_proyeccion
    try:
        existe = ventana is not None and ventana.winfo_exists()
    except Exception:
        existe = False
    if not existe:
        _fallo_actual("la ventana de proyección no se creó. Revisa el formulario.")
        return

    # Marcar presentada=true en el JSON en cuanto inicia la proyección.
    try:
        marcar_presentada(Path(item["ruta_json"]))
        item["presentada_marcada"] = True
        log(f"JSON actualizado: presentada=true -> {Path(item['ruta_json']).name}")
    except Exception as exc:
        item["presentada_marcada"] = False
        mensaje = f"{item['nombre']}: no se pudo marcar presentada=true ({exc})."
        FALLOS.append(mensaje)
        log(f"ADVERTENCIA: {mensaje}")

    item["inicio_real"] = time.monotonic()
    log("Proyección iniciada.")
    senalar_inicio(item)

    try:
        from customtkinter import ScalingTracker

        escala = ScalingTracker.get_window_scaling(ventana) or 1.0
        ventana.update_idletasks()
        if HEADLESS:
            _preparar_visor_sin_render(ventana.visor)
            log(f"Proyección headless: {ventana.winfo_geometry()} (escala {escala:.2f}).")
        else:
            # La app ya crea la proyección en el monitor elegido. Solo si cayó
            # en el tamaño simulado de 800x600 forzamos la pantalla principal.
            if ventana.winfo_width() <= 800 and ventana.winfo_height() <= 600:
                ancho = int(ventana.winfo_screenwidth() / escala)
                alto = int(ventana.winfo_screenheight() / escala)
                ventana.overrideredirect(True)
                ventana.geometry(f"{ancho}x{alto}+0+0")
                ventana.update_idletasks()
                log(f"Proyección ajustada a pantalla completa: {ancho}x{alto} lógicos.")
            else:
                log(f"Proyección: {ventana.winfo_geometry()} (escala {escala:.2f}).")
            ventana.after(150, ventana.visor.renderizar_slide_actual)
            ventana.attributes("-topmost", True)
            ventana.lift()
            ventana.update()
    except Exception as exc:
        log(f"ADVERTENCIA: no se pudo ajustar la proyección: {exc}")

    def _log_geometria():
        try:
            label = ventana.visor.label_imagen
            imagen = getattr(label, "_image", None)
            ancho_img = imagen.width() if hasattr(imagen, "width") else "?"
            alto_img = imagen.height() if hasattr(imagen, "height") else "?"
            log(
                f"Geometría proyección: ventana={ventana.winfo_geometry()} | "
                f"visor={ventana.visor.winfo_geometry()} | label={label.winfo_geometry()} | "
                f"imagen={ancho_img}x{alto_img} | label_root=({label.winfo_rootx()},{label.winfo_rooty()})"
            )
        except Exception as exc:
            log(f"No se pudo leer la geometría de la proyección: {exc}")

    if not HEADLESS:
        ui["root"].after(1200, _log_geometria)
    ui["root"].after(600, lambda: capturar(f"{Path(item['nombre']).stem}_slide_01"))
    _programar_diapositivas(item)


def _programar_diapositivas(item: dict) -> None:
    from app.presentation.views.ui_state import ui

    tiempos = item["tiempos"]
    escala = max(0.001, float(item.get("escala_tiempo", 1.0)))

    acumulado = 0.0
    for i, duracion in enumerate(tiempos):
        acumulado += duracion * escala
        if i < len(tiempos) - 1:
            ui["root"].after(
                max(1, int(round(acumulado * 1000))),
                lambda idx=i, it=item: _avanzar_diapositiva(idx, it),
            )

    # Detener después de la última diapositiva (con un pequeño margen).
    ui["root"].after(
        max(1, int(round(acumulado * 1000)) + 250),
        lambda it=item: _detener_presentacion(it),
    )


def _avanzar_diapositiva(indice: int, item: dict | None = None) -> None:
    item = item or _item_actual()
    if not item or item.get("cancelado") or item.get("finalizado") or item.get("detenido"):
        return

    from app.presentation.views import presentation_gui
    from app.presentation.views.ui_state import ui

    ventana = presentation_gui._ventana_proyeccion
    try:
        existe = ventana is not None and ventana.winfo_exists()
    except Exception:
        existe = False
    if not existe:
        log("La ventana de proyección ya no existe; se omiten los avances restantes.")
        item["cancelado"] = True
        return

    boton = buscar_boton(presentation_gui._datos_panel, "▶")
    if boton is None:
        log("No se encontró el botón '▶' para avanzar.")
        return

    try:
        boton.invoke()
        log(
            f"Avance: diapositiva {indice + 1} -> {indice + 2} "
            f"(t={time.monotonic() - item.get('inicio_real', time.monotonic()):.1f}s)"
        )
    except Exception as exc:
        log(f"No se pudo avanzar de diapositiva: {exc}")
        return

    if indice == 0:
        ui["root"].after(
            500,
            lambda: capturar(f"{Path(item['nombre']).stem}_slide_02"),
        )


def _detener_presentacion(item: dict | None = None) -> None:
    item = item or _item_actual()
    if not item or item.get("detenido") or item.get("finalizado"):
        return

    item["detenido"] = True
    from app.presentation.views import presentation_gui
    from app.presentation.views.ui_state import ui

    ventana = presentation_gui._ventana_proyeccion
    panel = presentation_gui._datos_panel

    try:
        existe = ventana is not None and ventana.winfo_exists()
    except Exception:
        existe = False
    if existe:
        boton = buscar_boton(panel, "Detener")
        if boton is not None:
            try:
                boton.invoke()
                log("Presentación detenida; guardando reporte de tiempos...")
            except Exception as exc:
                log(f"No se pudo pulsar 'Detener': {exc}")
                try:
                    ventana.cerrar()
                except Exception:
                    pass
        else:
            log("No se encontró el botón 'Detener'; se cierra la proyección directamente.")
            try:
                ventana.cerrar()
            except Exception:
                pass
    else:
        log("La proyección ya estaba cerrada.")

    ui["root"].after(1400, lambda: _verificar_reporte(item))


def _verificar_reporte(item: dict | None = None) -> None:
    item = item or _item_actual()
    if not item or item.get("finalizado"):
        return

    from app.core.controller.presentation_controller import orquestar_obtener_reporte_tiempo
    from app.core.controller.subject_controller import obtener_id_materia
    from app.presentation.views import presentation_gui
    from app.presentation.views.ui_state import ui

    panel = presentation_gui._datos_panel
    guardado = bool(getattr(panel, "_reporte_guardado", False)) if panel else False

    if not guardado and panel is not None:
        # Reintento explícito por si el guardado automático no alcanzó a correr.
        try:
            panel.generar_reporte_json()
            guardado = bool(getattr(panel, "_reporte_guardado", False))
        except Exception as exc:
            log(f"Reintento de guardado falló: {exc}")

    reporte_ok = False
    detalle = ""
    try:
        id_materia = obtener_id_materia(MATERIA)
        raw = orquestar_obtener_reporte_tiempo(item["nombre"], id_materia)
        if raw:
            data = json.loads(raw)
            grupo_data = data.get("grupos", {}).get(GRUPO)
            if grupo_data and grupo_data.get("historial_sesiones"):
                ultima = list(grupo_data["historial_sesiones"].values())[-1]
                reporte_ok = True
                detalle = (
                    f"planeado={ultima.get('planeado_seg')}s, "
                    f"duracion={ultima.get('duracion_seg')}s"
                )
    except Exception as exc:
        detalle = f"no se pudo leer el reporte: {exc}"

    item["reporte_ok"] = reporte_ok or guardado
    item["reporte_detalle"] = detalle

    real = time.monotonic() - item.get("inicio_real", time.monotonic())
    item["duracion_real"] = real
    log(
        f"Fin de '{item['nombre']}': duración real {real:.1f}s | "
        f"reporte={'OK' if item['reporte_ok'] else 'NO GUARDADO'} {detalle}"
    )

    if not item["reporte_ok"]:
        FALLOS.append(f"{item['nombre']}: el reporte de tiempos no se guardó.")

    ui["root"].after(700, lambda: _volver_y_siguiente(item))


def _volver_y_siguiente(item: dict | None = None) -> None:
    global INDICE

    if APP_CERRADA:
        return

    item = item or _item_actual()
    if item and item.get("finalizado"):
        return
    if item:
        item["finalizado"] = True

    from app.presentation.views import main_gui, navigator
    from app.presentation.views.ui_state import ui

    try:
        if navigator.vista_actual() != "main":
            navigator.ir_a_principal()
        main_gui._seleccionar_materia(MATERIA)
    except Exception as exc:
        log(f"No se pudo volver a la pantalla principal: {exc}")

    if item:
        nombre = item["nombre"]
        estado = "ERROR" if item.get("error") else "OK"
        RESUMEN.append(
            f"{nombre} | {item['total_diapositivas']} diapositivas | "
            f"JSON {int(item['total_sum'])}s | docente {item['tiempo_min']} min "
            f"({item['modo_tiempo']}) | duración {item.get('duracion_real', 0):.1f}s | "
            f"presentada={item.get('presentada_marcada', False)} | reporte={item.get('reporte_ok', False)} | {estado}"
        )
        try:
            INDICE = PLAN.index(item) + 1
        except ValueError:
            INDICE += 1
    else:
        INDICE += 1

    ui["root"].after(900, _siguiente)


# ---------------------------------------------------------------------------
# JSON presentada
# ---------------------------------------------------------------------------


def marcar_presentada(ruta_json: Path) -> None:
    data = json.loads(ruta_json.read_text(encoding="utf-8"))
    data["presentada"] = True
    _escribir_json_atomico(ruta_json, data)


def senalar_inicio(item: dict) -> None:
    """Avisa al orquestador que este proceso ya marcó presentada e inició."""
    if ARCHIVO_INICIO is None:
        return
    try:
        _escribir_json_atomico(
            ARCHIVO_INICIO,
            {
                "nombre": item.get("nombre"),
                "ruta_json": item.get("ruta_json"),
                "presentada": bool(item.get("presentada_marcada")),
                "pid": os.getpid(),
                "hora": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        log(f"Señal de inicio enviada: {ARCHIVO_INICIO.name}")
    except Exception as exc:
        log(f"ADVERTENCIA: no se pudo escribir la señal de inicio: {exc}")


# ---------------------------------------------------------------------------
# Entrada principal y arranque de la GUI
# ---------------------------------------------------------------------------


def preguntar_materia(materias: list[str], materia_arg: str | None) -> str:
    if materia_arg:
        objetivo = normalizar(materia_arg)
        for m in materias:
            if normalizar(m) == objetivo:
                return m
        raise SystemExit(
            f"No se encontró la materia '{materia_arg}'. Activas: {', '.join(materias)}"
        )

    print("\nMaterias activas:")
    for i, m in enumerate(materias, 1):
        print(f"  {i}. {m}")

    while True:
        entrada = input("\n¿Qué materia deseas presentar? (número o nombre): ").strip()
        if not entrada:
            continue
        if entrada.isdigit():
            idx = int(entrada) - 1
            if 0 <= idx < len(materias):
                return materias[idx]
        else:
            objetivo = normalizar(entrada)
            for m in materias:
                if normalizar(m) == objetivo:
                    return m
        print("Opción no válida. Intenta de nuevo.")


def preguntar_grupo(grupo_arg: str | None) -> str:
    if grupo_arg:
        grupo = grupo_arg.strip().upper()
    else:
        while True:
            grupo = input("Grupo escolar para el formulario (ej. 7CM1): ").strip().upper()
            if grupo:
                break
            print("El grupo no puede estar vacío.")

    if len(grupo) > 5 or not grupo.isalnum():
        raise SystemExit("El grupo debe ser alfanumérico y tener máximo 5 caracteres.")
    return grupo


def _escribir_resultado_trabajador() -> None:
    if ARCHIVO_RESULTADO is None:
        return
    item = PLAN[0] if PLAN else {}
    data = {
        "ok": (
            not FALLOS
            and bool(item.get("reporte_ok"))
            and bool(item.get("presentada_marcada"))
        ),
        "nombre": item.get("nombre"),
        "ruta_json": item.get("ruta_json"),
        "presentada": bool(item.get("presentada_marcada")),
        "reporte_ok": bool(item.get("reporte_ok")),
        "duracion_real": float(item.get("duracion_real") or 0.0),
        "error": item.get("error"),
        "resumen": RESUMEN,
        "fallos": FALLOS,
    }
    try:
        _escribir_json_atomico(ARCHIVO_RESULTADO, data)
        log(f"Resultado del trabajador guardado: {ARCHIVO_RESULTADO.name}")
    except Exception as exc:
        log(f"No se pudo guardar el resultado del trabajador: {exc}")


def _finalizar() -> None:
    global APP_CERRADA

    from app.presentation.views.ui_state import ui
    import tkinter.messagebox as messagebox

    log("=" * 78)
    log("RESUMEN FINAL")
    for linea in RESUMEN:
        log("  " + linea)
    if FALLOS:
        log("FALLOS:")
        for linea in FALLOS:
            log("  " + linea)

    if CARPETA_EVIDENCIAS:
        resumen_path = CARPETA_EVIDENCIAS / "resumen.txt"
        try:
            with resumen_path.open("w", encoding="utf-8") as fh:
                fh.write("Presentación automática mediante la GUI\n")
                fh.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                fh.write(f"Materia: {MATERIA}\n")
                fh.write(f"Grupo: {GRUPO}\n")
                fh.write(f"Presentaciones: {len(PLAN)}\n\n")
                for linea in RESUMEN:
                    fh.write(linea + "\n")
                if FALLOS:
                    fh.write("\nFallos:\n")
                    for linea in FALLOS:
                        fh.write(linea + "\n")
                fh.write(f"\nCapturas: {CARPETA_EVIDENCIAS}\n")
            log(f"Resumen guardado en: {resumen_path}")
        except Exception as exc:
            log(f"No se pudo guardar el resumen: {exc}")

    _escribir_resultado_trabajador()
    APP_CERRADA = True

    if not _ARGS.sin_mensaje:
        try:
            texto = (
                f"Se procesaron {len(PLAN)} presentaciones de '{MATERIA}'.\n"
                f"Grupo: {GRUPO}\n"
                f"Correctas: {len(PLAN) - len(FALLOS)} | Fallos: {len(FALLOS)}\n\n"
                f"Evidencias: {CARPETA_EVIDENCIAS}"
            )
            messagebox.showinfo("Presentaciones terminadas", texto, parent=ui["root"])
        except Exception:
            pass

    if _ARGS.cerrar:
        try:
            ui["root"].destroy()
        except Exception:
            pass


def _arrancar_secuencia() -> None:
    from app.presentation.views import main_gui
    from app.presentation.views.ui_state import ui

    root = ui.get("root")
    if root is None:
        log("No se encontró la ventana principal de la aplicación.")
        return

    if HEADLESS:
        try:
            # No usar withdraw(): el formulario es transient del root y
            # necesita que el root siga siendo "viewable" para su grab_set().
            root.geometry("+10000+10000")
            root.attributes("-alpha", 0.0)
        except Exception:
            pass
    else:
        try:
            root.geometry("1900x1040+0+0")
            root.update_idletasks()
            root.lift()
            root.focus_force()
            root.attributes("-topmost", True)
            root.after(1200, lambda: root.attributes("-topmost", False))
        except Exception:
            pass

    log(f"Aplicación abierta. Materia activa: {MATERIA}")
    try:
        main_gui._seleccionar_materia(MATERIA)
    except Exception as exc:
        log(f"No se pudo seleccionar la materia en la UI: {exc}")

    root.after(700, lambda: capturar(f"inicio_{MATERIA}"))
    root.after(1300, _siguiente)


def ejecutar_gui() -> int:
    import customtkinter as ctk

    from app.presentation.views import main_gui

    mainloop_original = ctk.CTk.mainloop

    def mainloop_con_arranque(self, *args, **kwargs):
        self.after(1200, _arrancar_secuencia)
        return mainloop_original(self, *args, **kwargs)

    ctk.CTk.mainloop = mainloop_con_arranque
    try:
        main_gui.iniciar_aplicacion()
    finally:
        ctk.CTk.mainloop = mainloop_original
    return 0


_ARGS = None


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Presenta en paralelo todas las presentaciones pendientes de una "
            "materia, una por proceso de la aplicación."
        )
    )
    parser.add_argument("--materia", help="Materia a presentar (omite la pregunta).")
    parser.add_argument("--grupo", help="Grupo escolar (omite la pregunta).")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra el plan.")
    parser.add_argument("--limite", type=int, help="Tomar solo las primeras N.")
    parser.add_argument(
        "--escala-tiempo",
        type=float,
        default=1.0,
        help="Multiplicador de los tiempos del JSON (para pruebas rápidas).",
    )
    parser.add_argument(
        "--repetir",
        action="store_true",
        help="Incluir también las presentaciones que ya tienen presentada=true.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Mostrar las ventanas (las proyecciones se encimarán).",
    )
    parser.add_argument("--cerrar", action="store_true", help="Cerrar cada app al terminar.")
    parser.add_argument(
        "--sin-mensaje",
        action="store_true",
        help="No mostrar el cuadro final (pruebas automatizadas).",
    )
    parser.add_argument(
        "--timeout-inicio",
        type=float,
        default=120.0,
        help="Segundos máximos para esperar la señal de inicio de cada proceso.",
    )
    parser.add_argument(
        "--timeout-total",
        type=float,
        default=1800.0,
        help="Segundos máximos que puede durar cada proceso.",
    )

    # Opciones internas usadas por el orquestador al lanzar cada trabajador.
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--solo-json", help=argparse.SUPPRESS)
    parser.add_argument("--tiempo-min", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--modo-tiempo", help=argparse.SUPPRESS)
    parser.add_argument("--estado-inicio", help=argparse.SUPPRESS)
    parser.add_argument("--resultado", help=argparse.SUPPRESS)
    parser.add_argument("--etiqueta", help=argparse.SUPPRESS)
    return parser


def _separar_pendientes(plan: list[dict], repetir: bool) -> tuple[list[dict], list[dict]]:
    pendientes: list[dict] = []
    omitidas: list[dict] = []
    for item in plan:
        if item.get("presentada_previa") and not repetir:
            omitidas.append(item)
        else:
            pendientes.append(item)
    return pendientes, omitidas


def _resultado_error(mensaje: str) -> None:
    if ARCHIVO_RESULTADO is None:
        return
    try:
        _escribir_json_atomico(
            ARCHIVO_RESULTADO,
            {
                "ok": False,
                "nombre": PLAN[0].get("nombre") if PLAN else None,
                "presentada": False,
                "reporte_ok": False,
                "duracion_real": 0.0,
                "error": mensaje,
                "resumen": [],
                "fallos": [mensaje],
            },
        )
    except Exception:
        pass


def _ejecutar_worker(args) -> int:
    """Presenta una sola presentación; es el proceso hijo del modo paralelo."""
    global MATERIA, GRUPO, PLAN, _ARGS, HEADLESS, SIN_CAPTURAS
    global ARCHIVO_INICIO, ARCHIVO_RESULTADO, ETIQUETA, CARPETA_EVIDENCIAS, LOG_PATH

    _ARGS = args
    HEADLESS = not args.visible
    SIN_CAPTURAS = HEADLESS
    CARPETA_EVIDENCIAS = None
    LOG_PATH = None
    ETIQUETA = args.etiqueta or "trabajador"
    ARCHIVO_INICIO = Path(args.estado_inicio) if args.estado_inicio else None
    ARCHIVO_RESULTADO = Path(args.resultado) if args.resultado else None

    # Antes de tocar la base de datos, ampliar el timeout de SQLite.
    _configurar_sqlite_timeout()

    materias = materias_activas()
    if not materias:
        _resultado_error("No hay materias activas en la aplicación.")
        return 2

    try:
        MATERIA = preguntar_materia(materias, args.materia)
        GRUPO = preguntar_grupo(args.grupo)
        plan = construir_plan(MATERIA)
    except Exception as exc:
        _resultado_error(str(exc))
        print(f"ERROR: {exc}", flush=True)
        return 1

    if not args.solo_json:
        _resultado_error("El trabajador no recibió --solo-json.")
        return 1

    objetivo = Path(args.solo_json).resolve()
    plan = [it for it in plan if Path(it["ruta_json"]).resolve() == objetivo]
    if not plan:
        _resultado_error(f"No se encontró el JSON indicado: {args.solo_json}")
        return 1

    item = plan[0]
    if args.tiempo_min is not None:
        item["tiempo_min"] = int(args.tiempo_min)
        item["tiempo_seg"] = item["tiempo_min"] * 60
    if args.modo_tiempo:
        item["modo_tiempo"] = args.modo_tiempo
    if args.escala_tiempo != 1.0:
        item["escala_tiempo"] = args.escala_tiempo
    PLAN = [item]

    try:
        return ejecutar_gui()
    except Exception as exc:
        _resultado_error(f"Error fatal en el trabajador: {exc}")
        traceback.print_exc()
        return 1


def _esperar_inicio(proc: subprocess.Popen, started: Path, timeout: float) -> bool:
    inicio = time.monotonic()
    while time.monotonic() - inicio < timeout:
        if started.exists():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.25)
    return False


def _leer_resultado(ruta: Path) -> dict | None:
    try:
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _cola_archivo(ruta: Path, lineas: int = 30) -> str:
    try:
        contenido = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(contenido[-lineas:])
    except Exception:
        return ""


def _lanzar_workers(plan: list[dict], args) -> tuple[list[tuple], float]:
    assert CARPETA_EVIDENCIAS is not None
    carpeta = CARPETA_EVIDENCIAS
    procesos: list[tuple] = []
    inicio_global = time.monotonic()

    for indice, item in enumerate(plan, 1):
        etiqueta = f"{indice:02d}_{sanear(Path(item['nombre']).stem)}"
        started = carpeta / f"{etiqueta}.started.json"
        resultado = carpeta / f"{etiqueta}.result.json"
        salida = carpeta / f"{etiqueta}.out.txt"

        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--materia",
            MATERIA,
            "--grupo",
            GRUPO,
            "--solo-json",
            item["ruta_json"],
            "--tiempo-min",
            str(item["tiempo_min"]),
            "--modo-tiempo",
            item["modo_tiempo"],
            "--estado-inicio",
            str(started),
            "--resultado",
            str(resultado),
            "--etiqueta",
            etiqueta,
            "--sin-mensaje",
            "--cerrar",
        ]
        if args.visible:
            cmd.append("--visible")
        if args.escala_tiempo != 1.0:
            cmd.extend(["--escala-tiempo", str(args.escala_tiempo)])

        entorno = os.environ.copy()
        entorno["PYTHONIOENCODING"] = "utf-8"
        entorno["PYTHONUNBUFFERED"] = "1"

        opciones = {
            "cwd": str(RAIZ),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "env": entorno,
        }
        if os.name == "nt":
            opciones["creationflags"] = subprocess.CREATE_NO_WINDOW

        with salida.open("wb") as fh:
            opciones["stdout"] = fh
            proc = subprocess.Popen(cmd, **opciones)

        log(
            f"Lanzado {indice}/{len(plan)}: {item['nombre']} | "
            f"docente {item['tiempo_min']} min ({item['modo_tiempo']}) | PID {proc.pid}"
        )

        if _esperar_inicio(proc, started, args.timeout_inicio):
            log(f"  {item['nombre']}: presentada=true y proyección iniciada. Siguiente…")
        else:
            if proc.poll() is not None:
                log(f"  ADVERTENCIA: el proceso terminó antes de iniciar. Revisa {salida.name}.")
            else:
                log(
                    f"  ADVERTENCIA: no llegó la señal de inicio en "
                    f"{args.timeout_inicio:.0f}s; se continúa con la siguiente."
                )

        procesos.append((proc, item, etiqueta, started, resultado, salida))

    resultados: list[tuple] = []
    try:
        for proc, item, etiqueta, _started, resultado, salida in procesos:
            try:
                proc.wait(timeout=args.timeout_total)
            except subprocess.TimeoutExpired:
                log(f"Tiempo de espera agotado para {etiqueta}; se termina el proceso.")
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except Exception:
                    proc.kill()
    except KeyboardInterrupt:
        log("Interrupción recibida; terminando los procesos en paralelo…")
        for proc, *_ in procesos:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        raise

    for proc, item, etiqueta, _started, resultado, salida in procesos:
        data = _leer_resultado(resultado)
        if data is None:
            data = {
                "ok": False,
                "nombre": item["nombre"],
                "presentada": False,
                "reporte_ok": False,
                "duracion_real": 0.0,
                "error": "El trabajador no dejó archivo de resultado.",
                "resumen": [],
                "fallos": [f"{item['nombre']}: no dejó resultado."],
            }
            cola = _cola_archivo(salida)
            if cola:
                log(f"Últimas líneas de {salida.name}:\n{cola}")
        resultados.append((item, data, etiqueta, salida))

    return resultados, time.monotonic() - inicio_global


def _resumen_paralelo(resultados: list[tuple], duracion_total: float, args) -> int:
    assert CARPETA_EVIDENCIAS is not None
    log("=" * 78)
    log("RESUMEN FINAL (MODO PARALELO)")
    lineas: list[str] = []
    fallos = 0

    for item, data, etiqueta, _salida in resultados:
        ok = bool(data.get("ok"))
        if not ok:
            fallos += 1
        duracion = float(data.get("duracion_real") or 0.0)
        linea = (
            f"{item['nombre']} | {item['total_diapositivas']} diapositivas | "
            f"JSON {int(item['total_sum'])}s | docente {item['tiempo_min']} min "
            f"({item['modo_tiempo']}) | duración {duracion:.1f}s | "
            f"presentada={bool(data.get('presentada'))} | "
            f"reporte={bool(data.get('reporte_ok'))} | "
            f"{'OK' if ok else 'ERROR'}"
        )
        if not ok and data.get("error"):
            linea += f" | {data['error']}"
        lineas.append(linea)
        log("  " + linea)

    log(f"Tiempo total de pared: {duracion_total:.1f}s ({duracion_total / 60:.1f} min)")
    log(f"Correctas: {len(resultados) - fallos} | Fallos: {fallos}")

    resumen_path = CARPETA_EVIDENCIAS / "resumen.txt"
    try:
        with resumen_path.open("w", encoding="utf-8") as fh:
            fh.write("Presentación automática en paralelo\n")
            fh.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write(f"Materia: {MATERIA}\n")
            fh.write(f"Grupo: {GRUPO}\n")
            fh.write(f"Presentaciones: {len(resultados)}\n")
            fh.write(f"Modo: {'visible' if args.visible else 'headless'}\n")
            fh.write(f"Tiempo total de pared: {duracion_total:.1f}s\n\n")
            for linea in lineas:
                fh.write(linea + "\n")
            fh.write(f"\nEvidencias: {CARPETA_EVIDENCIAS}\n")
        log(f"Resumen guardado en: {resumen_path}")
    except Exception as exc:
        log(f"No se pudo guardar el resumen: {exc}")

    return 0 if fallos == 0 else 1


def main() -> int:
    global MATERIA, GRUPO, PLAN, CARPETA_EVIDENCIAS, LOG_PATH, _ARGS
    global HEADLESS, SIN_CAPTURAS

    args = _crear_parser().parse_args()
    _ARGS = args

    if args.worker:
        return _ejecutar_worker(args)

    HEADLESS = not args.visible
    SIN_CAPTURAS = HEADLESS

    materias = materias_activas()
    if not materias:
        print("No hay materias activas en la aplicación.")
        return 2

    MATERIA = preguntar_materia(materias, args.materia)
    GRUPO = preguntar_grupo(args.grupo)

    try:
        plan = construir_plan(MATERIA, limite=args.limite)
    except Exception as exc:
        print(f"\nNo se puede continuar: {exc}")
        return 1

    pendientes, omitidas = _separar_pendientes(plan, args.repetir)
    PLAN = pendientes

    for item in PLAN:
        if args.escala_tiempo != 1.0:
            item["escala_tiempo"] = args.escala_tiempo
    asignar_tiempos_docente(PLAN)

    if args.dry_run:
        describir_plan(PLAN)
        for item in omitidas:
            log(f"Omitida (ya presentada): {item['nombre']}")
        log("Modo --dry-run: no se abre la aplicación.")
        return 0

    if not PLAN:
        log(
            f"Todas las presentaciones de '{MATERIA}' ya están marcadas como "
            "presentadas. Usa --repetir para volver a presentarlas."
        )
        return 0

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    CARPETA_EVIDENCIAS = EVIDENCIAS_BASE / f"presentacion_{marca}"
    CARPETA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    LOG_PATH = CARPETA_EVIDENCIAS / "registro.txt"

    log(f"Carpeta de evidencias: {CARPETA_EVIDENCIAS}")
    log(f"Modo: {'VISIBLE (las ventanas se encimarán)' if args.visible else 'HEADLESS (sin ventanas)'}")
    describir_plan(PLAN)
    for item in omitidas:
        log(f"Omitida (ya presentada): {item['nombre']}")

    if args.escala_tiempo != 1.0:
        log(
            "ATENCIÓN: modo de prueba con tiempos escalados "
            f"x{args.escala_tiempo}. No uses este modo para la presentación real."
        )

    if not args.sin_mensaje:
        try:
            respuesta = input(
                f"\n¿Iniciar {len(PLAN)} presentaciones en paralelo? (s/n): "
            ).strip().lower()
            if respuesta not in ("s", "si", "sí", "y", "yes"):
                print("Cancelado.")
                return 0
        except EOFError:
            pass

    try:
        resultados, duracion = _lanzar_workers(PLAN, args)
        return _resumen_paralelo(resultados, duracion, args)
    except Exception:
        log("ERROR FATAL:")
        log(traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
