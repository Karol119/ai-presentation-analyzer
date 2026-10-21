# tests/presentacion/pruebas/crear_carpetas_unidades.py
"""
Crea una carpeta por cada unidad de aprendizaje registrada en la base de datos.

Las carpetas se generan dentro de `tests/presentacion/presentaciones/`, de modo
que cada presentación de prueba quede organizada por la unidad académica a la
que pertenece.

Uso (desde la raíz del repositorio):

    python -m tests.presentacion.pruebas.crear_carpetas_unidades

Opciones:

    --db RUTA          Ruta alternativa a la base de datos SQLite.
    --solo-activas     Crea únicamente las unidades marcadas como activas.
    --sin-gitkeep      No crea el archivo .gitkeep en cada carpeta.

El script es idempotente: si la carpeta ya existe, no falla ni borra su
contenido.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[3]
DB_POR_DEFECTO = RAIZ_REPO / "storage" / "DB" / "ai_analyzer.db"
DESTINO_POR_DEFECTO = RAIZ_REPO / "tests" / "presentacion" / "presentaciones"

# Caracteres no permitidos en nombres de archivo/carpeta de Windows.
_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVADOS = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _nombre_seguro(nombre: str) -> str:
    """Convierte el nombre de la unidad en un nombre de carpeta válido."""
    nombre = unicodedata.normalize("NFC", nombre).strip()
    nombre = _INVALIDOS.sub("-", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    # Windows no admite puntos ni espacios al final.
    nombre = nombre.rstrip(" .")
    if not nombre:
        nombre = "sin-nombre"
    if nombre.upper() in _RESERVADOS:
        nombre = f"_{nombre}"
    return nombre


def _carpetas_unicas(nombres: list[str]) -> dict[str, str]:
    """Resuelve colisiones de nombres sin distinguir mayúsculas."""
    usados: set[str] = set()
    resultado: dict[str, str] = {}
    for original in nombres:
        base = _nombre_seguro(original)
        candidato = base
        contador = 2
        while candidato.casefold() in usados:
            candidato = f"{base} ({contador})"
            contador += 1
        usados.add(candidato.casefold())
        resultado[original] = candidato
    return resultado


def _leer_unidades(db: Path, solo_activas: bool) -> list[str]:
    if not db.exists():
        raise FileNotFoundError(f"No se encontró la base de datos: {db}")

    consulta = (
        "SELECT unidad_aprendizaje "
        "FROM Unidad_de_Aprendizaje "
        "WHERE unidad_aprendizaje IS NOT NULL "
        "AND TRIM(unidad_aprendizaje) <> ''"
    )
    if solo_activas:
        consulta += " AND activa = 1"
    consulta += " ORDER BY unidad_aprendizaje"

    with sqlite3.connect(db) as conexion:
        return [fila[0] for fila in conexion.execute(consulta)]


def crear_carpetas(
    db: Path = DB_POR_DEFECTO,
    destino: Path = DESTINO_POR_DEFECTO,
    solo_activas: bool = False,
    con_gitkeep: bool = True,
) -> list[Path]:
    """Crea las carpetas y devuelve las rutas resultantes."""
    unidades = _leer_unidades(db, solo_activas)
    destino.mkdir(parents=True, exist_ok=True)

    creadas: list[Path] = []
    for carpeta in _carpetas_unicas(unidades).values():
        ruta = destino / carpeta
        ruta.mkdir(exist_ok=True)
        if con_gitkeep:
            (ruta / ".gitkeep").touch(exist_ok=True)
        creadas.append(ruta)
    return creadas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crea una carpeta por unidad de aprendizaje en presentaciones/."
    )
    parser.add_argument("--db", type=Path, default=DB_POR_DEFECTO)
    parser.add_argument("--destino", type=Path, default=DESTINO_POR_DEFECTO)
    parser.add_argument("--solo-activas", action="store_true")
    parser.add_argument("--sin-gitkeep", action="store_true")
    args = parser.parse_args()

    creadas = crear_carpetas(
        db=args.db,
        destino=args.destino,
        solo_activas=args.solo_activas,
        con_gitkeep=not args.sin_gitkeep,
    )

    print(f"Unidades procesadas: {len(creadas)}")
    print(f"Destino: {args.destino}")
    for ruta in creadas:
        print(f"  - {ruta.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
