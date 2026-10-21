# tests/e2e/run_e2e.py
"""
Ejecutor de la suite E2E del prototipo final.

Ejecuta las pruebas de integración de negocio y de interfaz gráfica y guarda la
salida CRUDA (stdout + stderr) como evidencia en:

    docs/prototipo_final/evidencias/<fecha_hora>/

Ademas escribe un resumen (`resumen.txt`) con el entorno de ejecucion y el
conteo de resultados.

Uso (desde la raiz del repositorio):

    python -m tests.e2e.run_e2e
"""

from __future__ import annotations

import datetime
import contextlib
import io
import platform
import sqlite3
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIAS = RAIZ / "docs" / "prototipo_final" / "evidencias"

MODULOS = [
    "tests.e2e.test_e2e_negocio",
    "tests.e2e.test_e2e_gui",
    "tests.e2e.test_e2e_rendimiento_gui",
]


class _Tee(io.TextIOBase):
    """Duplica la salida a la consola y a un archivo de evidencia."""

    def __init__(self, *destinos):
        self._destinos = destinos

    def write(self, texto):
        for d in self._destinos:
            try:
                d.write(texto)
                d.flush()
            except Exception:
                pass
        return len(texto)

    def flush(self):
        for d in self._destinos:
            try:
                d.flush()
            except Exception:
                pass


def _entorno() -> str:
    lineas = [
        "===== ENTORNO DE EJECUCION =====",
        f"fecha            : {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"python           : {sys.version.splitlines()[0]}",
        f"ejecutable       : {sys.executable}",
        f"plataforma       : {platform.platform()}",
        f"sqlite (stdlib)  : {sqlite3.sqlite_version}",
        f"tk               : {platform.python_version()} / Tk disponible en runtime",
        f"raiz repo        : {RAIZ}",
        "================================",
        "",
    ]
    return "\n".join(lineas)


def main() -> int:
    carpeta = EVIDENCIAS / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)

    resultados = {}
    consola = sys.stdout
    for modulo in MODULOS:
        nombre = modulo.rsplit(".", 1)[1]
        archivo = carpeta / f"{nombre}.txt"
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(modulo)
        with open(archivo, "w", encoding="utf-8") as fh:
            tee = _Tee(consola, fh)
            with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
                runner = unittest.TextTestRunner(stream=tee, verbosity=2)
                print(f"\n########## EJECUTANDO {modulo} ##########")
                resultado = runner.run(suite)
            resultados[modulo] = resultado

    total = sum(r.testsRun for r in resultados.values())
    fallos = sum(len(r.failures) for r in resultados.values())
    errores = sum(len(r.errors) for r in resultados.values())
    omitidos = sum(len(r.skipped) for r in resultados.values())
    esperados = sum(len(getattr(r, "expectedFailures", [])) for r in resultados.values())
    exito = fallos == 0 and errores == 0

    resumen = [
        _entorno(),
        "===== RESUMEN GLOBAL =====",
        f"modulos          : {', '.join(MODULOS)}",
        f"pruebas totales  : {total}",
        f"fallos           : {fallos}",
        f"errores          : {errores}",
        f"omitidas         : {omitidos}",
        f"fallos esperados : {esperados}",
        f"resultado        : {'OK' if exito else 'FALLIDO'}",
        "",
        "Detalle por modulo:",
    ]
    for modulo, r in resultados.items():
        resumen.append(
            f"  - {modulo}: {r.testsRun} pruebas, "
            f"{len(r.failures)} fallos, {len(r.errors)} errores, "
            f"{len(getattr(r, 'expectedFailures', []))} fallos esperados"
        )
    texto = "\n".join(resumen) + "\n"
    (carpeta / "resumen.txt").write_text(texto, encoding="utf-8")
    print("\n" + texto)

    print(f"Evidencia guardada en: {carpeta}")
    return 0 if exito else 1


if __name__ == "__main__":
    raise SystemExit(main())
