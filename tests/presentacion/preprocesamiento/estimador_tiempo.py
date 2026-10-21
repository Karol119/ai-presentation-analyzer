# tests/presentacion/preprocesamiento/estimador_tiempo.py
"""
Estimador local del tiempo de exposición de una presentación PPTX.

Modelo
------
El tiempo se calcula por diapositiva a partir de:

  1. Palabras que se espera pronunciar:
       - texto visible (título + cuerpo), con un factor de elaboración,
       - notas del orador, si existen.
     Si hay notas, se toma el mayor entre ambas cantidades para no duplicar
     el mismo contenido.
  2. Tiempo de habla = palabras / palabras_por_minuto * 60.
  3. Tiempo visual = imágenes, gráficos y tablas (con topes por diapositiva).
  4. Pausas = base por diapositiva + pausa por párrafo/viñeta.

El resultado se acota entre un mínimo y un máximo por diapositiva. El total es
la suma de los segundos ya redondeados de cada diapositiva, de modo que el
tiempo total siempre coincide con la suma de los tiempos individuales.

No usa servicios de IA ni modifica el archivo original.
"""

from __future__ import annotations

import datetime
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.slide import Slide
from pptx.shapes.base import BaseShape

RAIZ_REPO = Path(__file__).resolve().parents[3]

# Palabras que se excluyen al contar (solo signos de viñeta o numeración).
_RE_PALABRA = re.compile(r"\w+", re.UNICODE)
_RE_SOLO_NUMERO = re.compile(r"^\s*\d{1,3}\s*$")

# Líneas de ruido habituales en las notas (navegación, numeración interna).
_RE_LINEAS_RUIDO = (
    re.compile(r"^\s*slide\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*[a-z]{2}\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*(home|discussion|conclusion|inicio|men[uú])\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$"),
)

_PLACEHOLDERS_IGNORADOS = {
    PP_PLACEHOLDER.DATE,
    PP_PLACEHOLDER.FOOTER,
    PP_PLACEHOLDER.HEADER,
    PP_PLACEHOLDER.SLIDE_NUMBER,
}
_PLACEHOLDERS_TITULO = {
    PP_PLACEHOLDER.TITLE,
    PP_PLACEHOLDER.CENTER_TITLE,
    PP_PLACEHOLDER.VERTICAL_TITLE,
}


# ---------------------------------------------------------------------------
# Parámetros del modelo
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParametrosTiempo:
    """Constantes ajustables del estimador."""

    palabras_por_minuto: float = 140.0
    segundos_base: float = 2.5
    factor_sin_notas: float = 1.10

    segundos_por_imagen: float = 4.0
    segundos_por_grafico: float = 8.0
    segundos_por_tabla: float = 6.0
    max_imagenes: int = 3
    max_graficos: int = 2
    max_tablas: int = 2

    segundos_por_elemento: float = 0.3
    max_elementos: int = 10

    min_contenido: int = 4
    min_visual: int = 8
    min_portada: int = 12
    min_transicion: int = 6
    min_cierre: int = 8
    max_diapositiva: int = 240


# ---------------------------------------------------------------------------
# Estructuras extraídas
# ---------------------------------------------------------------------------

@dataclass
class DiapositivaExtraida:
    numero: int
    titulo: str
    texto_cuerpo: str
    notas: str
    imagenes: int
    graficos: int
    tablas: int
    elementos: int
    tipo: str = "contenido"


# ---------------------------------------------------------------------------
# Utilidades de texto y formato
# ---------------------------------------------------------------------------

def contar_palabras(texto: str) -> int:
    """Cuenta palabras (incluye números y siglas, ignora viñetas sueltas)."""
    return len(_RE_PALABRA.findall(texto))


def formatear_tiempo(segundos: int) -> str:
    """Devuelve MM:SS, o H:MM:SS cuando se supera la hora."""
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{seg:02d}"
    return f"{minutos:02d}:{seg:02d}"


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFC", texto or "").strip()


def _limpiar_notas(texto: str) -> str:
    lineas = []
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        if any(patron.match(limpia) for patron in _RE_LINEAS_RUIDO):
            continue
        lineas.append(limpia)
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Extracción del PPTX
# ---------------------------------------------------------------------------

def _iterar_formas(formas: Any) -> Iterator[BaseShape]:
    """Recorre formas, entrando recursivamente en los grupos."""
    for forma in formas:
        if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iterar_formas(forma.shapes)
        else:
            yield forma


def _tipo_placeholder(forma: BaseShape) -> int | None:
    try:
        if forma.is_placeholder:
            return forma.placeholder_format.type
    except (AttributeError, ValueError):
        pass
    return None


def _es_visual(forma: BaseShape) -> bool:
    if forma.shape_type in (MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.MEDIA):
        return True
    return _tipo_placeholder(forma) == PP_PLACEHOLDER.PICTURE


def _texto_tabla(forma: BaseShape) -> str:
    try:
        celdas = [
            celda.text.strip()
            for fila in forma.table.rows
            for celda in fila.cells
            if celda.text.strip()
        ]
    except (AttributeError, ValueError):
        return ""
    return "\n".join(celdas)


def _extraer_diapositiva(diapositiva: Slide, numero: int, altura: int) -> DiapositivaExtraida:
    titulo = ""
    cuerpos: list[str] = []
    imagenes = graficos = tablas = elementos = 0

    for forma in _iterar_formas(diapositiva.shapes):
        tipo_ph = _tipo_placeholder(forma)

        if tipo_ph in _PLACEHOLDERS_IGNORADOS:
            continue

        if _es_visual(forma):
            imagenes += 1
            continue

        if getattr(forma, "has_chart", False):
            graficos += 1
            continue

        if getattr(forma, "has_table", False):
            tablas += 1
            texto_tabla = _texto_tabla(forma)
            if texto_tabla:
                cuerpos.append(texto_tabla)
            continue

        if not getattr(forma, "has_text_frame", False):
            continue

        texto = _normalizar(forma.text_frame.text)
        if not texto or not _RE_PALABRA.search(texto):
            continue

        if tipo_ph in _PLACEHOLDERS_TITULO:
            if not titulo:
                titulo = texto
            continue

        # Pie de página no declarado como placeholder: texto corto al final.
        try:
            if forma.top is not None and forma.height is not None and altura:
                proporcion_inferior = (forma.top + forma.height) / altura
                if proporcion_inferior >= 0.92 and contar_palabras(texto) <= 10:
                    continue
        except (TypeError, ZeroDivisionError):
            pass

        cuerpos.append(texto)
        elementos += sum(
            1 for parrafo in forma.text_frame.paragraphs if parrafo.text.strip()
        )

    texto_cuerpo = "\n".join(cuerpos)
    notas = ""
    if diapositiva.has_notes_slide:
        notas = _limpiar_notas(diapositiva.notes_slide.notes_text_frame.text)

    palabras_texto = contar_palabras(titulo) + contar_palabras(texto_cuerpo)
    palabras_notas = contar_palabras(notas)
    visuales = imagenes + graficos + tablas

    if numero == 1:
        tipo = "portada"
    elif _es_cierre(titulo, texto_cuerpo, palabras_texto):
        tipo = "cierre"
    elif palabras_texto <= 12 and palabras_notas == 0 and visuales == 0:
        tipo = "transicion"
    else:
        tipo = "contenido"

    return DiapositivaExtraida(
        numero=numero,
        titulo=titulo,
        texto_cuerpo=texto_cuerpo,
        notas=notas,
        imagenes=imagenes,
        graficos=graficos,
        tablas=tablas,
        elementos=elementos,
        tipo=tipo,
    )


def _es_cierre(titulo: str, cuerpo: str, palabras: int) -> bool:
    if palabras > 40:
        return False
    referencia = f"{titulo}\n{cuerpo}".lower()
    return bool(re.search(
        r"\b(gracias|preguntas|referencias|bibliograf[ií]a|cierre|fin de la presentaci[oó]n)\b",
        referencia,
    ))


# ---------------------------------------------------------------------------
# Cálculo del tiempo
# ---------------------------------------------------------------------------

def calcular_tiempo_diapositiva(
    diapositiva: DiapositivaExtraida,
    parametros: ParametrosTiempo,
    usar_notas: bool = True,
) -> dict[str, Any]:
    """Calcula el tiempo de una diapositiva y su desglose."""
    if parametros.palabras_por_minuto <= 0:
        raise ValueError("palabras_por_minuto debe ser mayor que cero")

    palabras_texto = contar_palabras(diapositiva.titulo) + contar_palabras(diapositiva.texto_cuerpo)
    palabras_notas = contar_palabras(diapositiva.notas) if usar_notas else 0

    palabras_habladas = palabras_texto * parametros.factor_sin_notas
    if palabras_notas > 0:
        palabras_habladas = max(palabras_habladas, palabras_notas)

    tiempo_texto = palabras_habladas / parametros.palabras_por_minuto * 60.0
    tiempo_visual = (
        min(diapositiva.imagenes, parametros.max_imagenes) * parametros.segundos_por_imagen
        + min(diapositiva.graficos, parametros.max_graficos) * parametros.segundos_por_grafico
        + min(diapositiva.tablas, parametros.max_tablas) * parametros.segundos_por_tabla
    )
    tiempo_pausas = (
        min(diapositiva.elementos, parametros.max_elementos)
        * parametros.segundos_por_elemento
    )

    bruto = parametros.segundos_base + tiempo_texto + tiempo_visual + tiempo_pausas

    if diapositiva.tipo == "portada":
        bruto += 6.0
        minimo = parametros.min_portada
    elif diapositiva.tipo == "cierre":
        bruto += 2.0
        minimo = parametros.min_cierre
    elif diapositiva.tipo == "transicion":
        minimo = parametros.min_transicion
    else:
        minimo = parametros.min_visual if (
            diapositiva.imagenes + diapositiva.graficos + diapositiva.tablas > 0
            and palabras_texto == 0
            and palabras_notas == 0
        ) else parametros.min_contenido

    segundos = min(max(bruto, minimo), parametros.max_diapositiva)
    segundos_enteros = int(math.floor(segundos + 0.5))

    return {
        "numero_diapositiva": diapositiva.numero,
        "tipo": diapositiva.tipo,
        "palabras_texto": palabras_texto,
        "palabras_notas": palabras_notas,
        "imagenes": diapositiva.imagenes,
        "graficos": diapositiva.graficos,
        "tablas": diapositiva.tablas,
        "elementos": diapositiva.elementos,
        "tiempo_texto_segundos": round(tiempo_texto, 1),
        "tiempo_visual_segundos": round(tiempo_visual, 1),
        "tiempo_pausas_segundos": round(tiempo_pausas, 1),
        "tiempo_segundos": segundos_enteros,
        "tiempo_formateado": formatear_tiempo(segundos_enteros),
    }


def estimar_presentacion(
    ruta_pptx: str | Path,
    parametros: ParametrosTiempo | None = None,
    usar_notas: bool = True,
    presentada: bool = False,
) -> dict[str, Any]:
    """Genera el diccionario que se serializa a JSON para una presentación."""
    ruta = Path(ruta_pptx)
    parametros = parametros or ParametrosTiempo()

    presentacion = Presentation(str(ruta))
    altura = int(presentacion.slide_height or 0)
    diapositivas = [
        _extraer_diapositiva(diapositiva, indice, altura)
        for indice, diapositiva in enumerate(presentacion.slides, start=1)
    ]

    tiempos = [
        calcular_tiempo_diapositiva(diapositiva, parametros, usar_notas)
        for diapositiva in diapositivas
    ]
    total = sum(item["tiempo_segundos"] for item in tiempos)

    try:
        ruta_relativa = ruta.resolve().relative_to(RAIZ_REPO).as_posix()
    except ValueError:
        ruta_relativa = ruta.as_posix()

    return {
        "nombre_presentacion": ruta.name,
        "unidad_academica": ruta.parent.name,
        "ruta_presentacion": ruta_relativa,
        "total_diapositivas": len(tiempos),
        "tiempo_por_diapositiva": tiempos,
        "tiempo_total_segundos": total,
        "tiempo_total_formateado": formatear_tiempo(total),
        "tiempo_total_minutos": round(total / 60.0, 1),
        "parametros": asdict(parametros),
        "fecha_generacion": datetime.datetime.now().isoformat(timespec="seconds"),
        "presentada": bool(presentada),
    }


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def escribir_json(ruta_json: str | Path, datos: dict[str, Any]) -> None:
    ruta = Path(ruta_json)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def leer_presentada(ruta_json: str | Path) -> bool:
    """Recupera el marcador si el JSON ya existía; si no, devuelve False."""
    ruta = Path(ruta_json)
    if not ruta.exists():
        return False
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    valor = datos.get("presentada", False)
    if isinstance(valor, str):
        return valor.strip().lower() in {"true", "1", "sí", "si", "presentada"}
    return bool(valor)
