# tests/presentacion/preprocesamiento/generar_predicciones.py
"""
Genera un JSON de predicción de tiempo por cada presentación `.pptx`.

Por defecto, el JSON se escribe junto al archivo original y con el mismo
nombre base:

    .../Redes de Computadoras/10 - OSPF_Presentacion 1.pptx
    .../Redes de Computadoras/10 - OSPF_Presentacion 1.json

Uso (desde la raíz del repositorio):

    python -m tests.presentacion.preprocesamiento.generar_predicciones

Opciones:

    --entrada RUTA     Carpeta que contiene las presentaciones.
    --salida RUTA      Carpeta alternativa; replica la estructura de --entrada.
    --wpm N            Palabras por minuto (por defecto 140).
    --sin-notas        Ignora las notas del orador.
    --quiet            Solo muestra el resumen final.

Si un JSON ya existe, se regeneran los tiempos pero se conserva el valor de
`presentada`. Así, una presentación marcada como expuesta no vuelve a quedar
como pendiente al repetir el preprocesamiento.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .estimador_tiempo import (
    ParametrosTiempo,
    estimar_presentacion,
    escribir_json,
    formatear_tiempo,
    leer_presentada,
)

RAIZ_REPO = Path(__file__).resolve().parents[3]
ENTRADA_POR_DEFECTO = RAIZ_REPO / "tests" / "presentacion" / "presentaciones"


def _destino_json(ruta_pptx: Path, entrada: Path, salida: Path | None) -> Path:
    if salida is None:
        return ruta_pptx.with_suffix(".json")
    relativa = ruta_pptx.relative_to(entrada)
    return (salida / relativa).with_suffix(".json")


def generar_predicciones(
    entrada: Path = ENTRADA_POR_DEFECTO,
    salida: Path | None = None,
    parametros: ParametrosTiempo | None = None,
    usar_notas: bool = True,
    quiet: bool = False,
) -> tuple[list[dict], list[tuple[Path, str]]]:
    """Procesa todas las presentaciones y devuelve (resultados, errores)."""
    entrada = entrada.resolve()
    salida = salida.resolve() if salida else None
    parametros = parametros or ParametrosTiempo()

    if not entrada.exists():
        raise FileNotFoundError(f"No existe la carpeta de entrada: {entrada}")

    archivos = sorted(
        ruta
        for ruta in entrada.rglob("*.pptx")
        if not ruta.name.startswith("~$")
    )
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos .pptx en: {entrada}")

    resultados: list[dict] = []
    errores: list[tuple[Path, str]] = []

    for indice, ruta in enumerate(archivos, start=1):
        destino = _destino_json(ruta, entrada, salida)
        try:
            presentada = leer_presentada(destino)
            datos = estimar_presentacion(
                ruta,
                parametros=parametros,
                usar_notas=usar_notas,
                presentada=presentada,
            )
            escribir_json(destino, datos)
            resultados.append(datos)
            if not quiet:
                print(
                    f"[{indice:>2}/{len(archivos)}] "
                    f"{datos['nombre_presentacion'][:60]:<60} "
                    f"{datos['total_diapositivas']:>3} diap.  "
                    f"{datos['tiempo_total_formateado']:>8}"
                )
        except Exception as error:  # noqa: BLE001 - se reporta y se continúa
            errores.append((ruta, f"{type(error).__name__}: {error}"))
            print(f"[{indice:>2}/{len(archivos)}] ERROR {ruta.name}: {error}", file=sys.stderr)

    return resultados, errores


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera predicciones de tiempo de exposición para archivos PPTX."
    )
    parser.add_argument("--entrada", type=Path, default=ENTRADA_POR_DEFECTO)
    parser.add_argument("--salida", type=Path, default=None)
    parser.add_argument(
        "--wpm",
        type=float,
        default=ParametrosTiempo.palabras_por_minuto,
        help="Palabras por minuto (por defecto 140).",
    )
    parser.add_argument("--sin-notas", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.wpm <= 0:
        parser.error("--wpm debe ser mayor que cero")

    parametros = ParametrosTiempo(palabras_por_minuto=args.wpm)

    try:
        resultados, errores = generar_predicciones(
            entrada=args.entrada,
            salida=args.salida,
            parametros=parametros,
            usar_notas=not args.sin_notas,
            quiet=args.quiet,
        )
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    total_segundos = sum(item["tiempo_total_segundos"] for item in resultados)
    total_diapositivas = sum(item["total_diapositivas"] for item in resultados)

    print()
    print("===== RESUMEN DE PREPROCESAMIENTO =====")
    print(f"presentaciones : {len(resultados)}")
    print(f"diapositivas   : {total_diapositivas}")
    print(f"tiempo total   : {formatear_tiempo(total_segundos)}")
    print(f"errores        : {len(errores)}")
    if errores:
        for ruta, mensaje in errores:
            print(f"  - {ruta}: {mensaje}")

    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
