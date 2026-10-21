#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Carga automática de materias y presentaciones usando la interfaz gráfica real
de AI Presentation Analyzer.

El script:
  1. Abre (o reutiliza) la aplicación principal `main.py`.
  2. Agrega las 5 materias solicitadas mediante el modal "Agregar materia".
  3. Sube hasta 5 presentaciones .pptx por materia usando la tarjeta
     "Subir presentación" y el diálogo de archivos de Windows.
  4. Guarda capturas de pantalla con nombres descriptivos en
     `tests/presentacion/evidencias/<fecha_hora>/`.

No importa módulos internos de la aplicación ni escribe directamente en la
base de datos: toda la interacción se hace con clics/teclado sobre la GUI.

Requisitos (ya instalados en este equipo):
    pip install pyautogui pyperclip opencv-python pillow psutil

Uso:
    python tests/presentacion/pruebas/cargar_presentaciones_gui.py
    python tests/presentacion/pruebas/cargar_presentaciones_gui.py --solo "Administración de Servicios en Red"
    python tests/presentacion/pruebas/cargar_presentaciones_gui.py --max 5
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import subprocess
import sys
import time
import traceback
import unicodedata
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

# Importante: el proceso de automatización debe ser DPI-aware para que las
# coordenadas de pyautogui coincidan con las de la pantalla física.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    import cv2
    import numpy as np
    import pyautogui
    import pyperclip
    import psutil
    from PIL import ImageGrab
except ImportError as exc:  # pragma: no cover - mensaje amigable
    print("Faltan dependencias de automatización:", exc)
    print("Instala con: pip install pyautogui pyperclip opencv-python pillow psutil")
    raise SystemExit(1)

pyautogui.FAILSAFE = True  # mover el mouse a una esquina aborta la automatización
pyautogui.PAUSE = 0.08

# ---------------------------------------------------------------------------
# Rutas y configuración
# ---------------------------------------------------------------------------

RAIZ = Path(__file__).resolve().parents[3]
PRESENTACIONES = RAIZ / "tests" / "presentacion" / "presentaciones"
EVIDENCIAS_BASE = RAIZ / "tests" / "presentacion" / "evidencias"
PLANTILLAS = Path(__file__).resolve().parent / "plantillas"

TPL_AGREGAR = PLANTILLAS / "agregar_materia.png"
TPL_SUBIR = PLANTILLAS / "subir_presentacion.png"
TPL_MODAL_BUSCAR = PLANTILLAS / "modal_buscar.png"
TPL_MODAL_FILA = PLANTILLAS / "modal_fila_izquierda.png"
TPL_MODAL_AGREGAR = PLANTILLAS / "modal_agregar_habilitado.png"
TPL_MODAL_CANCELAR = PLANTILLAS / "modal_cancelar.png"
TPL_PAPELERA = PLANTILLAS / "papelera.png"
TPL_MODAL_ELIMINAR = PLANTILLAS / "modal_eliminar_todo.png"

MATERIAS = [
    "Administración de Servicios en Red",
    "Arquitectura de Computadoras",
    "Comunicación oral y escrita",
    "Procesamiento Digital de Señales",
    "Sistemas distribuidos",
]

LIMITE_BYTES = 30 * 1024 * 1024
VENTANA_ANCHO = 1900
VENTANA_ALTO = 1040

u = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

HWND_BOTTOM = 1
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_RESTORE = 9

# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------

APP_HWND: int | None = None
APP_PID: int | None = None
VENTANA_AL_FONDO: int | None = None
CARPETA_EVIDENCIAS: Path | None = None
CONTADOR_CAPTURAS = 0
LOG_PATH: Path | None = None
RESUMEN: list[str] = []
OMITIDOS: list[str] = []


def log(mensaje: str) -> None:
    """Imprime y guarda el mensaje en el registro de la corrida."""
    texto = f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}"
    print(texto, flush=True)
    if LOG_PATH:
        try:
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(texto + "\n")
        except Exception:
            pass


def sanear(nombre: str) -> str:
    """Convierte un texto en un nombre de archivo seguro y descriptivo."""
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)
    nombre = re.sub(r"_+", "_", nombre).strip("._-")
    return nombre[:110] or "captura"


def capturar_app(nombre: str) -> Path | None:
    """Captura únicamente el área cliente de la ventana principal."""
    global CONTADOR_CAPTURAS
    if not APP_HWND or not CARPETA_EVIDENCIAS:
        return None
    try:
        img = ImageGrab.grab(window=APP_HWND)
        CONTADOR_CAPTURAS += 1
        destino = CARPETA_EVIDENCIAS / f"{CONTADOR_CAPTURAS:02d}_{sanear(nombre)}.png"
        img.save(destino)
        log(f"Captura: {destino.name}")
        return destino
    except Exception as exc:
        log(f"No se pudo capturar la app: {exc}")
        return None


def capturar_ventana(nombre: str, hwnd: int) -> Path | None:
    """Captura una ventana concreta (modal, diálogo, etc.)."""
    global CONTADOR_CAPTURAS
    if not CARPETA_EVIDENCIAS:
        return None
    try:
        img = ImageGrab.grab(window=hwnd)
        CONTADOR_CAPTURAS += 1
        destino = CARPETA_EVIDENCIAS / f"{CONTADOR_CAPTURAS:02d}_{sanear(nombre)}.png"
        img.save(destino)
        log(f"Captura: {destino.name}")
        return destino
    except Exception as exc:
        log(f"No se pudo capturar la ventana {hwnd}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Utilidades Win32
# ---------------------------------------------------------------------------


def info_ventana(hwnd: int) -> dict:
    n = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(hwnd, buf, n + 1)
    cls = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(hwnd, cls, 256)
    rect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "hwnd": hwnd,
        "title": buf.value,
        "cls": cls.value,
        "left": rect.left,
        "top": rect.top,
        "w": rect.right - rect.left,
        "h": rect.bottom - rect.top,
    }


def ventanas_visibles(pid: int) -> list[dict]:
    salida: list[dict] = []

    def _cb(hwnd, _lparam):
        wpid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and u.IsWindowVisible(hwnd):
            salida.append(info_ventana(hwnd))
        return True

    u.EnumWindows(WNDENUMPROC(_cb), 0)
    return salida


def esperar_ventana(pid: int, predicado, timeout: float = 30.0, intervalo: float = 0.4) -> dict | None:
    inicio = time.time()
    while time.time() - inicio < timeout:
        for v in ventanas_visibles(pid):
            try:
                if predicado(v):
                    return v
            except Exception:
                continue
        time.sleep(intervalo)
    return None


def esperar_sin_ventana(pid: int, predicado, timeout: float = 120.0, intervalo: float = 0.5) -> bool:
    inicio = time.time()
    while time.time() - inicio < timeout:
        if not any(predicado(v) for v in ventanas_visibles(pid)):
            return True
        time.sleep(intervalo)
    return False


def es_carga(v: dict) -> bool:
    """Modal de carga: Toplevel sin barra de título, aprox. 450x225."""
    return (
        v["cls"] == "TkTopLevel"
        and 300 < v["w"] < 700
        and 150 < v["h"] < 300
        and v["title"] in ("", "CTkToplevel")
    )


def es_advertencia(v: dict) -> bool:
    return v["title"] in ("Atención", "Archivo Duplicado", "Límite de tamaño excedido")


def enfocar(hwnd: int, topmost: bool = True, espera: float = 0.8) -> None:
    try:
        u.ShowWindow(hwnd, SW_RESTORE)
        if topmost:
            u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.SetFocus(hwnd)
    except Exception:
        pass
    time.sleep(espera)


def quitar_topmost(hwnd: int) -> None:
    try:
        u.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass


def rect_zona(v: dict, pad: int = 6) -> tuple[int, int, int, int]:
    return (max(0, v["left"] - pad), max(0, v["top"] - pad),
            v["left"] + v["w"] + pad, v["top"] + v["h"] + pad)


# ---------------------------------------------------------------------------
# Búsqueda de plantillas
# ---------------------------------------------------------------------------


def _captura_cv():
    img = pyautogui.screenshot()
    return img, cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def buscar(tpl_path: Path, zona=None, confianza: float = 0.82):
    """Busca una plantilla en la pantalla (o en una zona) y devuelve su centro."""
    if not tpl_path.exists():
        return None
    img, hay = _captura_cv()
    x1, y1, x2, y2 = zona or (0, 0, img.width, img.height)
    x1 = max(0, min(x1, img.width - 1))
    y1 = max(0, min(y1, img.height - 1))
    x2 = max(x1 + 1, min(x2, img.width))
    y2 = max(y1 + 1, min(y2, img.height))
    recorte = hay[y1:y2, x1:x2]
    tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
    if tpl is None or recorte.size == 0 or tpl.shape[0] > recorte.shape[0] or tpl.shape[1] > recorte.shape[1]:
        return None
    res = cv2.matchTemplate(recorte, tpl, cv2.TM_CCOEFF_NORMED)
    _, maxv, _, maxloc = cv2.minMaxLoc(res)
    if maxv < confianza:
        return None
    th, tw = tpl.shape[:2]
    return (x1 + maxloc[0] + tw // 2, y1 + maxloc[1] + th // 2, float(maxv))


def buscar_en_modal(tpl_path: Path, modal: dict, confianza: float = 0.80, y_desde: float = 0.0, y_hasta: float = 1.0):
    x1, y1, x2, y2 = rect_zona(modal)
    alto = y2 - y1
    return buscar(
        tpl_path,
        (x1, y1 + int(alto * y_desde), x2, y1 + int(alto * y_hasta)),
        confianza,
    )


# ---------------------------------------------------------------------------
# Preparación de la aplicación
# ---------------------------------------------------------------------------


def encontrar_app_existente() -> tuple[int, int] | None:
    """Busca una ventana visible de la app lanzada por main.py."""
    encontrados = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(proc.info["cmdline"] or [])
            if proc.info["name"] == "python.exe" and cmd.strip().endswith("main.py"):
                for v in ventanas_visibles(proc.info["pid"]):
                    if "IPN ESCOM" in v["title"]:
                        encontrados.append((proc.info["pid"], v["hwnd"]))
        except Exception:
            continue
    return encontrados[0] if encontrados else None


def lanzar_o_reutilizar_app() -> tuple[int, int]:
    existente = encontrar_app_existente()
    if existente:
        log(f"Se reutiliza la aplicación ya abierta (PID {existente[0]}).")
        return existente

    log("Abriendo la aplicación principal (main.py)...")
    subprocess.Popen([sys.executable, "main.py"], cwd=str(RAIZ))
    inicio = time.time()
    while time.time() - inicio < 90:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info["cmdline"] or [])
                if proc.info["name"] == "python.exe" and cmd.strip().endswith("main.py"):
                    for v in ventanas_visibles(proc.info["pid"]):
                        if "IPN ESCOM" in v["title"]:
                            log(f"Aplicación iniciada (PID {proc.info['pid']}).")
                            return proc.info["pid"], v["hwnd"]
            except Exception:
                continue
        time.sleep(0.8)
    raise RuntimeError("La aplicación no mostró su ventana en 90 segundos.")


def preparar_ventana(pid: int, hwnd: int) -> None:
    """Trae la app al frente, la redimensiona y la deja visible.

    Se manda al fondo la ventana que esté al frente (habitualmente el editor)
    para que la app quede visible. Al final se restaura.
    """
    global VENTANA_AL_FONDO
    fg = u.GetForegroundWindow()
    if fg and fg != hwnd:
        VENTANA_AL_FONDO = fg
        try:
            u.SetWindowPos(fg, HWND_BOTTOM, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass

    # Esperar a que la app termine de cargar su estado inicial. Tkinter puede
    # reaplicar su geometría por defecto durante los primeros segundos, así que
    # se verifica el tamaño y se reintenta hasta conseguirlo.
    time.sleep(10)
    u.ShowWindow(hwnd, SW_RESTORE)
    rect = wintypes.RECT()
    for intento in range(8):
        u.SetWindowPos(hwnd, HWND_TOP, 0, 0, VENTANA_ANCHO, VENTANA_ALTO, SWP_SHOWWINDOW)
        time.sleep(1.5)
        u.GetWindowRect(hwnd, ctypes.byref(rect))
        actual = (rect.right - rect.left, rect.bottom - rect.top)
        if actual == (VENTANA_ANCHO, VENTANA_ALTO):
            break
        log(f"  Reintentando tamaño de ventana (intento {intento + 1}, actual {actual[0]}x{actual[1]}).")

    u.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                   SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    u.BringWindowToTop(hwnd)
    u.SetForegroundWindow(hwnd)
    time.sleep(1.2)

    u.GetWindowRect(hwnd, ctypes.byref(rect))
    log(f"Ventana de la app: {rect.right - rect.left}x{rect.bottom - rect.top} en ({rect.left},{rect.top}).")


# ---------------------------------------------------------------------------
# Alta de materias
# ---------------------------------------------------------------------------


def agregar_materia(nombre: str) -> bool:
    log(f"Agregando materia: {nombre}")
    btn = buscar(TPL_AGREGAR, confianza=0.80)
    if not btn:
        raise RuntimeError("No se encontró el botón '＋ Agregar materia' en la app.")
    pyautogui.click(btn[0], btn[1])
    time.sleep(1.2)

    modal = esperar_ventana(APP_PID, lambda v: v["title"] == "Agregar materia", 12)
    if not modal:
        raise RuntimeError("No se abrió el modal 'Agregar materia'.")
    enfocar(modal["hwnd"])
    capturar_ventana(f"modal_agregar_{nombre}", modal["hwnd"])

    # Campo de búsqueda: su posición relativa dentro del modal es estable.
    pyautogui.click(modal["left"] + int(modal["w"] * 0.50),
                    modal["top"] + int(modal["h"] * 0.224))
    time.sleep(0.3)
    pyperclip.copy(nombre)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(1.2)
    capturar_ventana(f"modal_busqueda_{nombre}", modal["hwnd"])

    # Primera fila del resultado. La plantilla es el borde izquierdo de una
    # fila sin seleccionar; se limita la búsqueda a la zona de la lista para
    # no confundirla con el campo de búsqueda.
    def seleccionar_fila() -> bool:
        fila = buscar_en_modal(TPL_MODAL_FILA, modal, confianza=0.68, y_desde=0.30, y_hasta=0.60)
        if fila:
            pyautogui.click(fila[0] + 120, fila[1])
            log(f"  Fila localizada en {fila[0] + 120},{fila[1]} (confianza {fila[2]:.2f}).")
        else:
            pyautogui.click(modal["left"] + int(modal["w"] * 0.48),
                            modal["top"] + int(modal["h"] * 0.36))
            log("  Fila seleccionada por posición relativa.")
        time.sleep(0.9)
        return True

    seleccionar_fila()
    capturar_ventana(f"modal_seleccion_{nombre}", modal["hwnd"])

    boton = buscar_en_modal(TPL_MODAL_AGREGAR, modal, confianza=0.80, y_desde=0.70, y_hasta=1.0)
    if not boton:
        # Segundo intento: a veces el primer clic cae en el borde de la fila.
        log("  No se detectó el botón habilitado; se reintenta seleccionar la fila.")
        seleccionar_fila()
        capturar_ventana(f"modal_seleccion_reintento_{nombre}", modal["hwnd"])
        boton = buscar_en_modal(TPL_MODAL_AGREGAR, modal, confianza=0.80, y_desde=0.70, y_hasta=1.0)

    if not boton:
        log(f"  La materia '{nombre}' no está disponible (posiblemente ya está activa).")
        cancelar = buscar_en_modal(TPL_MODAL_CANCELAR, modal, confianza=0.75, y_desde=0.70, y_hasta=1.0)
        if cancelar:
            pyautogui.click(cancelar[0], cancelar[1])
        else:
            pyautogui.hotkey("alt", "f4")
        time.sleep(1.0)
        return False

    pyautogui.click(boton[0], boton[1])
    if not esperar_sin_ventana(APP_PID, lambda v: v["title"] == "Agregar materia", 15):
        log("  El modal de alta no se cerró; se intenta cerrar con Alt+F4.")
        pyautogui.hotkey("alt", "f4")
        time.sleep(1.0)
    time.sleep(1.8)
    capturar_app(f"materia_agregada_{nombre}")
    log(f"  Materia agregada: {nombre}")
    return True


# ---------------------------------------------------------------------------
# Carga de presentaciones
# ---------------------------------------------------------------------------


def archivos_para_materia(nombre: str, maximo: int) -> tuple[list[Path], list[tuple[Path, str]]]:
    carpeta = PRESENTACIONES / nombre
    if not carpeta.is_dir():
        return [], []
    todos = sorted([p for p in carpeta.iterdir() if p.suffix.lower() == ".pptx"], key=lambda p: p.name.lower())
    seleccionados: list[Path] = []
    omitidos: list[tuple[Path, str]] = []
    for p in todos:
        try:
            tam = p.stat().st_size
        except OSError:
            continue
        if tam > LIMITE_BYTES:
            omitidos.append((p, f"{tam / (1024 * 1024):.1f} MB > 30 MB"))
            continue
        if len(seleccionados) < maximo:
            seleccionados.append(p)
    return seleccionados, omitidos


def ubicar_tarjeta_subir() -> tuple[int, int] | None:
    """Busca la tarjeta 'Subir presentación', desplazando si es necesario."""
    punto = buscar(TPL_SUBIR, confianza=0.80)
    if punto:
        return punto[0], punto[1]

    # La tarjeta puede quedar debajo del área visible: desplazar el panel de tarjetas.
    try:
        pyautogui.moveTo(VENTANA_ANCHO // 2, VENTANA_ALTO // 2)
        for delta in (-700, -700, -700, 700, 700, 700):
            pyautogui.scroll(delta)
            time.sleep(0.6)
            punto = buscar(TPL_SUBIR, confianza=0.80)
            if punto:
                return punto[0], punto[1]
    except Exception:
        pass
    return None


def cerrar_advertencia(v: dict) -> None:
    """Cierra el modal de advertencia con su botón 'Entendido'."""
    capturar_ventana(f"advertencia_{v['title']}", v["hwnd"])
    # El botón está centrado en la parte inferior del modal.
    x = v["left"] + v["w"] // 2
    y = v["top"] + int(v["h"] * 0.84)
    pyautogui.click(x, y)
    if not esperar_sin_ventana(APP_PID, lambda w: w["hwnd"] == v["hwnd"], 6):
        pyautogui.press("enter")
        time.sleep(1.0)


def subir_presentacion(nombre_materia: str, ruta: Path) -> str:
    """Sube un archivo por la GUI. Devuelve 'ok', 'duplicado', 'pesado' o 'error'."""
    log(f"  Subiendo: {ruta.name} ({ruta.stat().st_size / (1024 * 1024):.1f} MB)")
    tarjeta = ubicar_tarjeta_subir()
    if not tarjeta:
        capturar_app(f"error_sin_tarjeta_subir_{nombre_materia}")
        raise RuntimeError("No se encontró la tarjeta 'Subir presentación'.")

    pyautogui.click(tarjeta[0], tarjeta[1])
    dialogo = esperar_ventana(
        APP_PID,
        lambda v: v["cls"] == "#32770" and v["w"] > 300,
        15,
    )
    if not dialogo:
        capturar_app(f"error_sin_dialogo_{nombre_materia}")
        raise RuntimeError("No se abrió el diálogo de archivos.")

    if dialogo["hwnd"] != u.GetForegroundWindow():
        enfocar(dialogo["hwnd"], topmost=False, espera=0.4)

    try:
        pyperclip.copy(str(ruta))
    except Exception:
        time.sleep(0.3)
        pyperclip.copy(str(ruta))
    pyautogui.hotkey("ctrl", "a")
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.6)
    pyautogui.press("enter")
    time.sleep(0.8)

    # Si el diálogo sigue abierto, se reintenta Enter.
    if any(v["hwnd"] == dialogo["hwnd"] for v in ventanas_visibles(APP_PID)):
        pyautogui.press("enter")
        time.sleep(0.8)

    # Esperar el modal de carga y su finalización.
    visto_carga = False
    resultado = "ok"
    inicio = time.time()
    while time.time() - inicio < 300:
        vs = ventanas_visibles(APP_PID)
        cargando = [v for v in vs if es_carga(v)]
        advertencias = [v for v in vs if es_advertencia(v)]
        if cargando and not visto_carga:
            visto_carga = True
            capturar_ventana(f"cargando_{ruta.stem}", cargando[0]["hwnd"])
        if advertencias:
            adv = advertencias[0]
            capturar_app(f"advertencia_{ruta.stem}")
            if adv["title"] == "Archivo Duplicado":
                resultado = "duplicado"
            elif adv["title"] == "Límite de tamaño excedido":
                resultado = "pesado"
            cerrar_advertencia(adv)
            break
        if visto_carga and not cargando:
            # Pequeña espera para que aparezca una advertencia posterior.
            time.sleep(0.8)
            vs = ventanas_visibles(APP_PID)
            advertencias = [v for v in vs if es_advertencia(v)]
            if advertencias:
                adv = advertencias[0]
                capturar_app(f"advertencia_{ruta.stem}")
                if adv["title"] == "Archivo Duplicado":
                    resultado = "duplicado"
                elif adv["title"] == "Límite de tamaño excedido":
                    resultado = "pesado"
                cerrar_advertencia(adv)
            break
        if not visto_carga and time.time() - inicio > 10:
            # No apareció el modal: puede haber terminado muy rápido.
            if not any(v["cls"] == "#32770" for v in vs):
                capturar_app(f"sin_modal_carga_{ruta.stem}")
                break
        time.sleep(0.5)

    time.sleep(1.5)
    capturar_app(f"presentacion_cargada_{nombre_materia}_{ruta.stem}")
    log(f"  Resultado: {resultado} - {ruta.name}")
    return resultado


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------


def restaurar_entorno() -> None:
    if APP_HWND:
        quitar_topmost(APP_HWND)
    if VENTANA_AL_FONDO:
        try:
            u.SetWindowPos(VENTANA_AL_FONDO, HWND_TOP, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
        except Exception:
            pass


def main() -> int:
    global APP_HWND, APP_PID, CARPETA_EVIDENCIAS, LOG_PATH

    parser = argparse.ArgumentParser(description="Carga materias y presentaciones usando la GUI.")
    parser.add_argument("--solo", help="Procesar únicamente la materia indicada.")
    parser.add_argument("--max", type=int, default=5, help="Máximo de presentaciones por materia (default 5).")
    args = parser.parse_args()

    materias = [m for m in MATERIAS if not args.solo or m == args.solo]
    if not materias:
        print(f"No se encontró la materia '{args.solo}'. Opciones: {', '.join(MATERIAS)}")
        return 2

    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    CARPETA_EVIDENCIAS = EVIDENCIAS_BASE / marca
    CARPETA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    LOG_PATH = CARPETA_EVIDENCIAS / "registro.txt"
    log(f"Carpeta de evidencias: {CARPETA_EVIDENCIAS}")

    try:
        APP_PID, APP_HWND = lanzar_o_reutilizar_app()
        preparar_ventana(APP_PID, APP_HWND)
        capturar_app("aplicacion_iniciada")

        for materia in materias:
            log("=" * 70)
            log(f"MATERIA: {materia}")
            agregada = agregar_materia(materia)
            if not agregada:
                log(f"  Se omite la carga de presentaciones de '{materia}' porque no se pudo agregar.")
                RESUMEN.append(f"{materia}: NO AGREGADA (ya activa o no disponible)")
                continue

            archivos, omitidos = archivos_para_materia(materia, args.max)
            log(f"  Archivos a cargar ({len(archivos)}):")
            for p in archivos:
                log(f"    - {p.name}")
            for p, motivo in omitidos:
                log(f"    OMITIDO: {p.name} ({motivo})")
                OMITIDOS.append(f"{materia}/{p.name}: {motivo}")

            resultados = []
            for ruta in archivos:
                try:
                    res = subir_presentacion(materia, ruta)
                except Exception as exc:
                    log(f"  ERROR al subir {ruta.name}: {exc}")
                    capturar_app(f"error_subida_{materia}_{ruta.stem}")
                    resultados.append((ruta.name, "error"))
                    continue
                resultados.append((ruta.name, res))

            ok = sum(1 for _, r in resultados if r == "ok")
            RESUMEN.append(f"{materia}: {ok} cargadas de {len(archivos)} intentadas")
            for nombre, res in resultados:
                if res != "ok":
                    RESUMEN.append(f"  - {nombre}: {res}")
            for p, motivo in omitidos:
                RESUMEN.append(f"  - OMITIDO {p.name}: {motivo}")

        capturar_app("resumen_final_materias")
        log("=" * 70)
        log("RESUMEN")
        for linea in RESUMEN:
            log("  " + linea)
        if OMITIDOS:
            log("ARCHIVOS OMITIDOS POR TAMAÑO:")
            for linea in OMITIDOS:
                log("  " + linea)

        resumen_path = CARPETA_EVIDENCIAS / "resumen.txt"
        with resumen_path.open("w", encoding="utf-8") as fh:
            fh.write("Carga de materias y presentaciones mediante la GUI\n")
            fh.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write(f"Aplicación: {RAIZ / 'main.py'}\n\n")
            fh.write("Resultados por materia:\n")
            for linea in RESUMEN:
                fh.write(linea + "\n")
            if OMITIDOS:
                fh.write("\nArchivos omitidos:\n")
                for linea in OMITIDOS:
                    fh.write(linea + "\n")
            fh.write(f"\nCapturas: {CARPETA_EVIDENCIAS}\n")
        log(f"Resumen guardado en: {resumen_path}")
        log("La aplicación queda abierta para su revisión.")
        return 0
    except Exception:
        log("ERROR FATAL:")
        log(traceback.format_exc())
        capturar_app("error_fatal")
        return 1
    finally:
        restaurar_entorno()


if __name__ == "__main__":
    raise SystemExit(main())
