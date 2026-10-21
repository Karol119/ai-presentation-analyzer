#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Análisis secuencial de las presentaciones cargadas usando la interfaz gráfica
real de AI Presentation Analyzer.

El script:
  1. Abre (o reutiliza) la aplicación principal `main.py`.
  2. Recorre las materias activas y sus presentaciones visibles.
  3. Para cada presentación aún no analizada:
       - abre el menú "Ver opciones" de su tarjeta,
       - pulsa "Analizar presentación",
       - espera a que termine el análisis (modal de carga),
       - captura la vista de análisis y algunas diapositivas,
       - vuelve a la pantalla principal.
  4. Hace una pausa entre presentaciones para respetar el límite de tokens por
     minuto de Gemini.
  5. Guarda capturas, un registro y un resumen en
     `tests/presentacion/evidencias/analisis_<fecha_hora>/`.

No importa módulos internos de la aplicación para analizar ni escribe en la
base de datos: todos los análisis se disparan con clics sobre la GUI. La base
de datos se consulta en modo sólo lectura para saber qué falta y para anotar
el score obtenido en el resumen.

Uso:
    python tests/presentacion/pruebas/analizar_presentaciones_gui.py
    python tests/presentacion/pruebas/analizar_presentaciones_gui.py --pausa 90
    python tests/presentacion/pruebas/analizar_presentaciones_gui.py --solo "Administración de Servicios en Red"
    python tests/presentacion/pruebas/analizar_presentaciones_gui.py --max 1

Requisitos:
    pip install pyautogui pyperclip opencv-python pillow psutil
"""

from __future__ import annotations

import argparse
import ctypes
import os
import re
import sqlite3
import subprocess
import sys
import time
import traceback
import unicodedata
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

# El proceso debe ser DPI-aware para que las coordenadas de pyautogui
# coincidan con los píxeles físicos de la pantalla.
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
    import psutil
    from PIL import Image, ImageGrab
except ImportError as exc:  # pragma: no cover
    print("Faltan dependencias de automatización:", exc)
    print("Instala con: pip install pyautogui pyperclip opencv-python pillow psutil")
    raise SystemExit(1)

# Reutilizamos las utilidades Win32, de captura y de preparación de ventana
# que ya se usaron para la carga de presentaciones.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cargar_presentaciones_gui as base  # noqa: E402

pyautogui.FAILSAFE = True  # mover el mouse a una esquina aborta la automatización
pyautogui.PAUSE = 0.08

# ---------------------------------------------------------------------------
# Rutas y configuración
# ---------------------------------------------------------------------------

RAIZ = base.RAIZ
EVIDENCIAS_BASE = base.EVIDENCIAS_BASE
PLANTILLAS = Path(__file__).resolve().parent / "plantillas"
DB_PATH = RAIZ / "storage" / "DB" / "ai_analyzer.db"

TPL_VER_OPCIONES = PLANTILLAS / "ver_opciones.png"
TPL_ANALIZAR = PLANTILLAS / "analizar_presentacion.png"
TPL_PAPELERA = PLANTILLAS / "papelera.png"
TPL_MATERIAS = {
    "Administración de Servicios en Red": PLANTILLAS / "materia_Administracion_de_Servicios_en_Red.png",
    "Arquitectura de Computadoras": PLANTILLAS / "materia_Arquitectura_de_Computadoras.png",
    "Comunicación oral y escrita": PLANTILLAS / "materia_Comunicacion_oral_y_escrita.png",
    "Procesamiento Digital de Señales": PLANTILLAS / "materia_Procesamiento_Digital_de_Senales.png",
    "Sistemas distribuidos": PLANTILLAS / "materia_Sistemas_distribuidos.png",
}

# Pausa por defecto entre presentaciones. El usuario pidió explícitamente una
# espera para no agotar el límite de tokens por minuto de Gemini.
PAUSA_DEFECTO = 75
PAUSA_ERROR_DEFECTO = 180
TIMEOUT_ANALISIS_DEFECTO = 1800  # 30 minutos máximo por presentación

# ---------------------------------------------------------------------------
# Estado global
# ---------------------------------------------------------------------------

APP_HWND: int | None = None
APP_PID: int | None = None
CARPETA_EVIDENCIAS: Path | None = None
LOG_PATH: Path | None = None
APP_SALIDA_PATH: Path | None = None
APP_SALIDA_FH = None
APP_LOG_OFFSET = 0
RESUMEN: list[str] = []
FALLOS: list[str] = []


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
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)
    nombre = re.sub(r"_+", "_", nombre).strip("._-")
    return nombre[:110] or "captura"


# ---------------------------------------------------------------------------
# Capturas (delegadas al módulo de carga, que ya maneja el contador)
# ---------------------------------------------------------------------------


def capturar_app(nombre: str) -> Path | None:
    return base.capturar_app(nombre)


def capturar_ventana(nombre: str, hwnd: int) -> Path | None:
    return base.capturar_ventana(nombre, hwnd)


# ---------------------------------------------------------------------------
# Búsqueda de plantillas
# ---------------------------------------------------------------------------


def _nms(puntos: list[tuple[int, int, float]], distancia: int = 60) -> list[tuple[int, int, float]]:
    """Elimina detecciones casi idénticas y ordena por fila y columna."""
    elegidos: list[tuple[int, int, float]] = []
    for x, y, score in sorted(puntos, key=lambda p: p[2], reverse=True):
        if all((x - ex) ** 2 + (y - ey) ** 2 >= distancia ** 2 for ex, ey, _ in elegidos):
            elegidos.append((x, y, score))
    return sorted(elegidos, key=lambda p: (p[1], p[0]))


def buscar_todas(
    tpl_path: Path,
    confianza: float = 0.95,
    zona: tuple[int, int, int, int] | None = None,
    distancia: int = 60,
) -> list[tuple[int, int, float]]:
    """Devuelve todas las coincidencias de una plantilla, ordenadas."""
    if not tpl_path.exists():
        return []
    img, hay = base._captura_cv()
    x1, y1, x2, y2 = zona or (0, 0, img.width, img.height)
    x1 = max(0, min(x1, img.width - 1))
    y1 = max(0, min(y1, img.height - 1))
    x2 = max(x1 + 1, min(x2, img.width))
    y2 = max(y1 + 1, min(y2, img.height))
    recorte = hay[y1:y2, x1:x2]
    tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
    if tpl is None or recorte.size == 0:
        return []
    if tpl.shape[0] > recorte.shape[0] or tpl.shape[1] > recorte.shape[1]:
        return []

    res = cv2.matchTemplate(recorte, tpl, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(res >= confianza)
    th, tw = tpl.shape[:2]
    puntos = [(x1 + int(x) + tw // 2, y1 + int(y) + th // 2, float(res[y, x]))
              for x, y in zip(xs, ys)]
    return _nms(puntos, distancia)


# ---------------------------------------------------------------------------
# Geometría de la ventana
# ---------------------------------------------------------------------------


def rect_cliente(hwnd: int) -> tuple[int, int, int, int]:
    """Devuelve (x, y, ancho, alto) del área cliente en coordenadas de pantalla."""
    rc = wintypes.RECT()
    u = ctypes.windll.user32
    u.GetClientRect(hwnd, ctypes.byref(rc))
    pt = wintypes.POINT(0, 0)
    u.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, rc.right, rc.bottom


def localizar_boton_volver() -> tuple[int, int] | None:
    """
    Localiza el botón guinda "← Volver a inicio" del topbar en modo análisis.
    Se busca por color (es el único botón grande guinda en la mitad derecha
    de la barra superior), sin depender del texto ni del nombre de la materia.
    """
    if not APP_HWND:
        return None
    cx, cy, cw, ch = rect_cliente(APP_HWND)
    try:
        img = ImageGrab.grab(bbox=(cx, cy, cx + cw, cy + 68)).convert("RGB")
    except Exception:
        return None
    arr = np.array(img)
    # #6A1B31 = RGB(106, 27, 49)
    mascara = cv2.inRange(arr, np.array([70, 5, 25]), np.array([150, 80, 105]))
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidatos = []
    for c in contornos:
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        if w >= 90 and h >= 24 and area >= 1500 and x > cw * 0.45:
            candidatos.append((area, x, y, w, h))
    if not candidatos:
        return None
    _, x, y, w, h = max(candidatos, key=lambda t: t[0])
    return cx + x + w // 2, cy + y + h // 2


def principal_visible() -> bool:
    """La vista principal muestra las tarjetas con su botón 'Ver opciones'."""
    return len(buscar_todas(TPL_VER_OPCIONES, confianza=0.97, distancia=60)) >= 5


def identificar_materia_visible() -> str | None:
    """Reconoce la materia activa por el título grande del panel de contenido."""
    if not APP_HWND:
        return None
    cx, cy, _, _ = rect_cliente(APP_HWND)
    zona = (cx + 340, cy + 112, cx + 1150, cy + 178)
    img, hay = base._captura_cv()
    x1, y1, x2, y2 = zona
    recorte = hay[y1:y2, x1:x2]
    if recorte.size == 0:
        return None

    mejor_nombre, mejor_score = None, 0.0
    for nombre, tpl_path in TPL_MATERIAS.items():
        if not tpl_path.exists():
            continue
        tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
        if tpl is None or tpl.shape[0] > recorte.shape[0] or tpl.shape[1] > recorte.shape[1]:
            continue
        res = cv2.matchTemplate(recorte, tpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, _ = cv2.minMaxLoc(res)
        if maxv > mejor_score:
            mejor_nombre, mejor_score = nombre, float(maxv)
    if mejor_score >= 0.80:
        return mejor_nombre
    return None


def traer_al_frente() -> None:
    if APP_HWND:
        base.enfocar(APP_HWND, topmost=True, espera=0.3)


# ---------------------------------------------------------------------------
# Base de datos (sólo lectura)
# ---------------------------------------------------------------------------


def conectar_db_ro():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def materias_activas_db() -> list[str]:
    with conectar_db_ro() as conn:
        return [r[0] for r in conn.execute(
            "SELECT unidad_aprendizaje FROM Unidad_de_Aprendizaje "
            "WHERE activa = 1 ORDER BY rowid"
        )]


def presentaciones_db(materia: str) -> list[dict]:
    """
    Presentaciones visibles de una materia en el mismo orden en que la app
    las pinta (orden de inserción / rowid de Presentacion).
    """
    query = """
        SELECT p.presentacion,
               hv.analisis,
               hv.calificacion_presentacion,
               hv.recomendacion_presentacion,
               hv.total_diapositivas
        FROM Presentacion p
        JOIN Unidad_de_Aprendizaje u
             ON u.id_unidad_aprendizaje = p.id_unidad_aprendizaje
        JOIN Historial_de_Versiones hv
             ON hv.id_presentacion = p.id_presentacion
        WHERE u.unidad_aprendizaje = ?
          AND u.activa = 1
          AND p.visible = 1
          AND hv.numero_version = (
              SELECT MAX(numero_version)
              FROM Historial_de_Versiones
              WHERE id_presentacion = p.id_presentacion
          )
        ORDER BY p.rowid
    """
    with conectar_db_ro() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(query, (materia,))]


def metricas_db(materia: str, presentacion: str) -> tuple[float | None, str | None]:
    for fila in presentaciones_db(materia):
        if fila["presentacion"] == presentacion:
            return fila.get("calificacion_presentacion"), fila.get("recomendacion_presentacion")
    return None, None


# ---------------------------------------------------------------------------
# Preparación de la aplicación
# ---------------------------------------------------------------------------


def lanzar_o_reutilizar_app() -> tuple[int, int]:
    global APP_SALIDA_FH, APP_SALIDA_PATH

    existente = base.encontrar_app_existente()
    if existente:
        log(f"Se reutiliza la aplicación ya abierta (PID {existente[0]}).")
        return existente

    log("Abriendo la aplicación principal (main.py)...")
    APP_SALIDA_PATH = CARPETA_EVIDENCIAS / "app_salida.txt" if CARPETA_EVIDENCIAS else None
    if APP_SALIDA_PATH:
        APP_SALIDA_FH = APP_SALIDA_PATH.open("a", encoding="utf-8", buffering=1)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        cwd=str(RAIZ),
        stdout=APP_SALIDA_FH or subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        env=env,
    )

    inicio = time.time()
    while time.time() - inicio < 120:
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(proc.info["cmdline"] or [])
                if proc.info["name"] == "python.exe" and cmd.strip().endswith("main.py"):
                    for v in base.ventanas_visibles(proc.info["pid"]):
                        if "IPN ESCOM" in v["title"]:
                            log(f"Aplicación iniciada (PID {proc.info['pid']}).")
                            return proc.info["pid"], v["hwnd"]
            except Exception:
                continue
        time.sleep(0.8)
    raise RuntimeError("La aplicación no mostró su ventana en 120 segundos.")


def esperar_principal(timeout: float = 15.0) -> bool:
    inicio = time.time()
    while time.time() - inicio < timeout:
        if principal_visible():
            return True
        time.sleep(0.6)
    return False


def volver_a_inicio() -> bool:
    """Pulsa '← Volver a inicio' y comprueba que reaparecen las tarjetas."""
    for intento in range(1, 4):
        boton = localizar_boton_volver()
        if boton:
            log(f"  Volviendo a inicio (botón en {boton[0]},{boton[1]}).")
            pyautogui.click(boton[0], boton[1])
            time.sleep(1.8)
            if esperar_principal(10):
                return True

        # Respaldo: probar posiciones del topbar derecho por si el color no
        # se detectó (tema/escala distinta). Se evita la zona del engrane.
        log(f"  No se detectó el botón de volver; respaldo {intento}.")
        cx, cy, cw, _ = rect_cliente(APP_HWND)
        for x in range(cx + int(cw * 0.82), cx + int(cw * 0.96), 18):
            pyautogui.click(x, cy + 34)
            time.sleep(0.7)
            if esperar_principal(3):
                return True
    return principal_visible()


def asegurar_principal() -> bool:
    if principal_visible():
        return True
    # Si hay un modal de error abierto, se cierra.
    for v in base.ventanas_visibles(APP_PID):
        if v["title"] == "Error de Conexión IA":
            cerrar_advertencia(v)
            break
    if volver_a_inicio():
        return True
    return principal_visible()


# ---------------------------------------------------------------------------
# Selección de materia
# ---------------------------------------------------------------------------


def seleccionar_materia(nombre: str) -> bool:
    actual = identificar_materia_visible()
    if actual == nombre:
        log(f"  Materia ya activa: {nombre}")
        return True

    # Las filas de la barra lateral están separadas por ~64 px; hay que usar
    # una distancia menor para no fusionar dos papeleras contiguas.
    filas = buscar_todas(TPL_PAPELERA, confianza=0.85, distancia=35)
    if len(filas) < 2:
        log(f"  No se localizaron las filas de materias (encontradas: {len(filas)}).")
        return False

    cx, _, _, _ = rect_cliente(APP_HWND)
    for i, (_, y, _) in enumerate(filas, 1):
        pyautogui.click(cx + 100, y)
        time.sleep(1.0)
        detectada = identificar_materia_visible()
        log(f"  Fila {i}/{len(filas)} -> {detectada or 'no identificada'}")
        if detectada == nombre:
            return True
    return False


# ---------------------------------------------------------------------------
# Análisis de una presentación
# ---------------------------------------------------------------------------


def leer_error_app() -> str:
    """Lee las líneas nuevas del log de la app para clasificar el error."""
    if not APP_SALIDA_PATH or not APP_SALIDA_PATH.exists():
        return ""
    try:
        with APP_SALIDA_PATH.open("rb") as fh:
            fh.seek(APP_LOG_OFFSET)
            texto = fh.read().decode("utf-8", errors="replace")
        lineas = [l for l in texto.splitlines() if l.strip()]
        # Conservar el contexto del último error, aunque después se hayan
        # impreso mensajes de estado o trazas adicionales.
        claves = ("error en el análisis", "error", "límite", "limite", "cuota",
                  "quota", "api_key_invalid", "clave inválida", "sin conexión",
                  "traceback", "exception")
        relevantes = [l for l in lineas if any(k in l.lower() for k in claves)]
        seleccion = relevantes[-30:] if relevantes else lineas[-30:]
        return "\n".join(seleccion)
    except Exception:
        return ""


def clasificar_error(texto: str) -> str:
    bajo = (texto or "").lower()
    if "perday" in bajo or "por día" in bajo or "por dia" in bajo or "diarias" in bajo:
        return "cuota_diaria"
    if "cuota" in bajo or "quota" in bajo or "429" in bajo or "exhausted" in bajo:
        return "cuota"
    if "clave inválida" in bajo or "api_key_invalid" in bajo or ("api key" in bajo and "inválid" in bajo):
        return "clave"
    if "temario" in bajo:
        return "temario"
    if "sin conexión" in bajo or "conexion" in bajo or "conexión" in bajo:
        return "red"
    return "otro"


def cerrar_advertencia(v: dict) -> None:
    log(f"  Cerrando advertencia: {v['title']}")
    try:
        x = v["left"] + v["w"] // 2
        y = v["top"] + int(v["h"] * 0.84)
        pyautogui.click(x, y)
        time.sleep(1.0)
        if any(w["hwnd"] == v["hwnd"] for w in base.ventanas_visibles(APP_PID)):
            pyautogui.press("enter")
            time.sleep(0.8)
    except Exception as exc:
        log(f"  No se pudo cerrar la advertencia: {exc}")


def pausar(segundos: int, motivo: str) -> None:
    if segundos <= 0:
        return
    log(f"  Pausa de {segundos}s ({motivo})...")
    restante = segundos
    while restante > 0:
        tramo = min(15, restante)
        time.sleep(tramo)
        restante -= tramo
        if restante > 0:
            log(f"    ...faltan {restante}s")


def capturar_vistas_analisis(materia: str, presentacion: str, total_slides: int | None) -> None:
    stem = sanear(Path(presentacion).stem)
    capturar_app(f"analisis_{sanear(materia)}_{stem}_diapositiva_01")
    # Avanzar dos diapositivas para mostrar también contenido interno.
    for num in (2, 3):
        if total_slides and total_slides < num:
            break
        traer_al_frente()
        pyautogui.press("right")
        time.sleep(1.1)
        capturar_app(f"analisis_{sanear(materia)}_{stem}_diapositiva_{num:02d}")


def analizar_una(
    materia: str,
    presentacion: str,
    indice_tarjeta: int,
    total_slides: int | None,
    max_intentos: int,
    pausa_error: int,
    timeout: int,
) -> str:
    """
    Analiza una presentación concreta. Devuelve:
      'ok', 'error' o 'omitida'.
    """
    nombre_corto = Path(presentacion).stem

    for intento in range(1, max_intentos + 1):
        log(f"  Intento {intento}/{max_intentos}: {presentacion}")
        if not asegurar_principal():
            log("  No fue posible volver a la pantalla principal.")
            return "error"

        botones = buscar_todas(TPL_VER_OPCIONES, confianza=0.97, distancia=60)
        botones.sort(key=lambda p: (round(p[1] / 50), p[0]))
        if len(botones) < 5:
            log(f"  Se esperaban 5 tarjetas y se encontraron {len(botones)}. Se reintenta.")
            time.sleep(2)
            continue
        if indice_tarjeta >= len(botones):
            log("  Índice de tarjeta fuera de rango.")
            return "error"

        bx, by, _ = botones[indice_tarjeta]
        pyautogui.click(bx, by)
        time.sleep(1.0)

        items = buscar_todas(TPL_ANALIZAR, confianza=0.90, distancia=80)
        if not items:
            capturar_app(f"sin_opcion_analizar_{sanear(materia)}_{sanear(nombre_corto)}")
            log("  No se encontró la opción 'Analizar presentación'. "
                "Puede que la tarjeta ya esté analizada o el menú no abrió.")
            # Si ya está analizada en la BD, se considera omitida.
            datos = presentaciones_db(materia)
            if indice_tarjeta < len(datos) and datos[indice_tarjeta]["analisis"]:
                return "omitida"
            return "error"

        ix, iy, score = max(items, key=lambda p: p[2])
        log(f"  Pulsando 'Analizar presentación' (confianza {score:.2f}).")
        pyautogui.click(ix, iy)

        # Esperar el modal de carga.
        modal = base.esperar_ventana(APP_PID, base.es_carga, timeout=60)
        if modal:
            log("  Análisis en curso (modal de carga visible).")
            capturar_ventana(f"cargando_{sanear(materia)}_{sanear(nombre_corto)}", modal["hwnd"])
        else:
            log("  No se vio el modal de carga; se continúa vigilando la vista.")

        inicio = time.time()
        resultado = None
        error_texto = ""
        while time.time() - inicio < timeout:
            ventanas = base.ventanas_visibles(APP_PID)
            advertencias = [v for v in ventanas if v["title"] == "Error de Conexión IA"]
            cargando = [v for v in ventanas if base.es_carga(v)]

            if advertencias:
                adv = advertencias[0]
                log("  Apareció el modal 'Error de Conexión IA'.")
                capturar_app(f"error_{sanear(materia)}_{sanear(nombre_corto)}")
                capturar_ventana(f"error_modal_{sanear(materia)}_{sanear(nombre_corto)}", adv["hwnd"])
                error_texto = leer_error_app()
                if error_texto:
                    log("  Últimas líneas del log de la app:\n" + error_texto)
                cerrar_advertencia(adv)
                resultado = "error"
                break

            if not cargando and localizar_boton_volver():
                # La vista de análisis ya está construida.
                time.sleep(1.5)
                resultado = "ok"
                break

            time.sleep(1.2)

        if resultado is None:
            log(f"  Tiempo de espera agotado ({timeout}s).")
            capturar_app(f"timeout_{sanear(materia)}_{sanear(nombre_corto)}")
            # No se debe continuar con la UI bloqueada por un análisis que
            # sigue vivo en segundo plano.
            raise RuntimeError(
                f"Tiempo de espera agotado analizando '{presentacion}'. "
                "La aplicación puede seguir ocupada; se detiene la corrida."
            )

        if resultado == "ok":
            log("  Análisis terminado correctamente. Capturando evidencia.")
            capturar_vistas_analisis(materia, presentacion, total_slides)
            if not volver_a_inicio():
                log("  ADVERTENCIA: no se pudo volver a la pantalla principal.")
            return "ok"

        # Error: decidir si se reintenta.
        clase = clasificar_error(error_texto)
        log(f"  Error clasificado como: {clase}")
        if clase in ("cuota_diaria", "clave"):
            raise RuntimeError(
                f"Error no recuperable ({clase}) al analizar '{presentacion}'. "
                "Se detiene la corrida para no repetir el mismo fallo."
            )
        if intento < max_intentos and clase != "temario":
            pausar(pausa_error, f"reintento tras error de tipo {clase}")
            continue
        return "error"

    return "error"


# ---------------------------------------------------------------------------
# Flujo principal
# ---------------------------------------------------------------------------


def restaurar_entorno_final() -> None:
    if APP_HWND:
        base.quitar_topmost(APP_HWND)
        try:
            base.enfocar(APP_HWND, topmost=False, espera=0.5)
        except Exception:
            pass
    if base.VENTANA_AL_FONDO:
        try:
            base.u.SetWindowPos(
                base.VENTANA_AL_FONDO, base.HWND_TOP, 0, 0, 0, 0,
                base.SWP_NOMOVE | base.SWP_NOSIZE | base.SWP_SHOWWINDOW,
            )
        except Exception:
            pass


def main() -> int:
    global APP_HWND, APP_PID, CARPETA_EVIDENCIAS, LOG_PATH
    global APP_SALIDA_PATH, APP_LOG_OFFSET

    parser = argparse.ArgumentParser(
        description="Analiza una por una las presentaciones cargadas usando la GUI."
    )
    parser.add_argument("--solo", help="Procesar únicamente la materia indicada.")
    parser.add_argument("--max", type=int, default=5,
                        help="Máximo de presentaciones por materia (default 5).")
    parser.add_argument("--pausa", type=int, default=PAUSA_DEFECTO,
                        help=f"Segundos de pausa entre presentaciones (default {PAUSA_DEFECTO}).")
    parser.add_argument("--pausa-error", type=int, default=PAUSA_ERROR_DEFECTO,
                        help=f"Segundos de pausa antes de reintentar un error (default {PAUSA_ERROR_DEFECTO}).")
    parser.add_argument("--intentos", type=int, default=3,
                        help="Intentos por presentación (default 3).")
    parser.add_argument("--timeout", type=int, default=TIMEOUT_ANALISIS_DEFECTO,
                        help=f"Segundos máximos por análisis (default {TIMEOUT_ANALISIS_DEFECTO}).")
    parser.add_argument("--carpeta", help="Carpeta de evidencias existente para continuar una corrida.")
    args = parser.parse_args()

    if args.carpeta:
        CARPETA_EVIDENCIAS = Path(args.carpeta).expanduser()
        if not CARPETA_EVIDENCIAS.is_absolute():
            CARPETA_EVIDENCIAS = RAIZ / CARPETA_EVIDENCIAS
    else:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        CARPETA_EVIDENCIAS = EVIDENCIAS_BASE / f"analisis_{marca}"
    CARPETA_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    LOG_PATH = CARPETA_EVIDENCIAS / "registro.txt"
    # Si la app ya está abierta y fue lanzada por una corrida anterior en esta
    # misma carpeta, su salida sigue en app_salida.txt y se puede leer para
    # clasificar errores.
    APP_SALIDA_PATH = CARPETA_EVIDENCIAS / "app_salida.txt"
    APP_LOG_OFFSET = APP_SALIDA_PATH.stat().st_size if APP_SALIDA_PATH.exists() else 0
    global RESUMEN, FALLOS
    RESUMEN = []
    FALLOS = []

    # Sincronizar los globales del módulo reutilizado para que sus capturas y
    # su función log escriban en la carpeta de esta corrida.
    base.CARPETA_EVIDENCIAS = CARPETA_EVIDENCIAS
    base.LOG_PATH = LOG_PATH
    # Continuar la numeración si se está reutilizando una carpeta.
    existentes = [int(m.group(1)) for p in CARPETA_EVIDENCIAS.glob("*.png")
                  if (m := re.match(r"^(\d+)_", p.name))]
    base.CONTADOR_CAPTURAS = max(existentes, default=0)

    log(f"Carpeta de evidencias: {CARPETA_EVIDENCIAS}")
    log(f"Pausa entre presentaciones: {args.pausa}s")

    try:
        APP_PID, APP_HWND = lanzar_o_reutilizar_app()
        base.APP_PID = APP_PID
        base.APP_HWND = APP_HWND
        base.preparar_ventana(APP_PID, APP_HWND)
        base.VENTANA_AL_FONDO = base.VENTANA_AL_FONDO  # se conserva para restaurar

        capturar_app("aplicacion_iniciada")
        if not asegurar_principal():
            raise RuntimeError("La aplicación no quedó en la pantalla principal.")

        materias = materias_activas_db()
        if args.solo:
            if args.solo not in materias:
                print(f"No se encontró la materia activa '{args.solo}'. Activas: {', '.join(materias)}")
                return 2
            materias = [args.solo]

        log(f"Materias activas: {', '.join(materias)}")

        # Plan de trabajo: sólo presentaciones aún no analizadas.
        plan: list[tuple[str, list[dict]]] = []
        for materia in materias:
            datos = presentaciones_db(materia)[: args.max]
            pendientes = [d for d in datos if not d["analisis"]]
            log(f"{materia}: {len(datos)} presentaciones, {len(pendientes)} pendientes.")
            plan.append((materia, datos))

        total_pendientes = sum(1 for _, datos in plan for d in datos if not d["analisis"])
        log(f"Total de presentaciones pendientes: {total_pendientes}")
        if total_pendientes == 0:
            log("No hay presentaciones pendientes. Nada que analizar.")

        procesadas = 0
        for materia, datos in plan:
            log("=" * 72)
            log(f"MATERIA: {materia}")
            if not seleccionar_materia(materia):
                log("  No se pudo seleccionar la materia. Se continúa con la siguiente.")
                RESUMEN.append(f"{materia}: ERROR AL SELECCIONAR")
                FALLOS.append(f"{materia}: no se pudo seleccionar")
                continue

            capturar_app(f"materia_{sanear(materia)}_inicio")

            for idx, fila in enumerate(datos):
                presentacion = fila["presentacion"]
                if fila["analisis"]:
                    log(f"  OMITIDA (ya analizada): {presentacion}")
                    RESUMEN.append(f"{materia} | {presentacion} | YA ANALIZADA")
                    continue

                # Si la materia cambió por alguna razón, se vuelve a seleccionar.
                if identificar_materia_visible() != materia:
                    if not seleccionar_materia(materia):
                        log("  Se perdió la materia activa; se omite el resto de esta materia.")
                        break

                log("-" * 72)
                log(f"Presentación: {presentacion}")
                estado = analizar_una(
                    materia=materia,
                    presentacion=presentacion,
                    indice_tarjeta=idx,
                    total_slides=fila.get("total_diapositivas"),
                    max_intentos=args.intentos,
                    pausa_error=args.pausa_error,
                    timeout=args.timeout,
                )
                procesadas += 1

                if estado == "ok":
                    score, zona = metricas_db(materia, presentacion)
                    log(f"  RESULTADO: OK | score={score} | zona={zona}")
                    RESUMEN.append(f"{materia} | {presentacion} | OK | score={score} | zona={zona}")
                elif estado == "omitida":
                    log("  RESULTADO: OMITIDA (ya analizada)")
                    RESUMEN.append(f"{materia} | {presentacion} | YA ANALIZADA")
                else:
                    log("  RESULTADO: ERROR")
                    RESUMEN.append(f"{materia} | {presentacion} | ERROR")
                    FALLOS.append(f"{materia} | {presentacion}")

                # Pausa antes de la siguiente presentación, salvo que sea la última.
                if procesadas < total_pendientes:
                    pausar(args.pausa, "espera para respetar el límite de tokens por minuto")

            # Captura del estado de la materia al terminar.
            asegurar_principal()
            if identificar_materia_visible() != materia:
                seleccionar_materia(materia)
            capturar_app(f"resumen_materia_{sanear(materia)}")

        # Resumen visual final.
        asegurar_principal()
        capturar_app("resumen_final_analisis")

        log("=" * 72)
        log("RESUMEN")
        for linea in RESUMEN:
            log("  " + linea)
        if FALLOS:
            log("FALLOS:")
            for linea in FALLOS:
                log("  " + linea)

        resumen_path = CARPETA_EVIDENCIAS / "resumen.txt"
        fallos_set = set(FALLOS)
        with resumen_path.open("w", encoding="utf-8") as fh:
            fh.write("Análisis secuencial de presentaciones mediante la GUI\n")
            fh.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            fh.write(f"Aplicación: {RAIZ / 'main.py'}\n")
            fh.write(f"Pausa entre presentaciones: {args.pausa} s\n")
            fh.write(f"Pausa antes de reintentos: {args.pausa_error} s\n")
            fh.write(f"Presentaciones procesadas en esta corrida: {procesadas}\n\n")

            fh.write("Estado final de las presentaciones:\n")
            for materia in materias:
                fh.write(f"\n{materia}\n")
                for fila in presentaciones_db(materia)[: args.max]:
                    clave = f"{materia} | {fila['presentacion']}"
                    score = fila.get("calificacion_presentacion")
                    zona = fila.get("recomendacion_presentacion")
                    if clave in fallos_set:
                        estado = "ERROR"
                    elif fila["analisis"]:
                        estado = "ANALIZADA"
                    else:
                        estado = "PENDIENTE"
                    extra = f" | score={score} | zona={zona}" if fila["analisis"] else ""
                    fh.write(f"  - {fila['presentacion']}: {estado}{extra}\n")

            if RESUMEN:
                fh.write("\nResultados de esta corrida:\n")
                for linea in RESUMEN:
                    fh.write(linea + "\n")
            if FALLOS:
                fh.write("\nFallos de esta corrida:\n")
                for linea in FALLOS:
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
        if APP_SALIDA_FH:
            try:
                APP_SALIDA_FH.flush()
            except Exception:
                pass
        restaurar_entorno_final()


if __name__ == "__main__":
    raise SystemExit(main())
