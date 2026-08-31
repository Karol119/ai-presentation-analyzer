# app/core/logic/text_extractor.py
"""
Extractor de datos de archivos PPTX.

CAMBIO RESPECTO A LA VERSIÓN ANTERIOR:
Se agrega el campo "content_blocks" en cada diapositiva.
content_blocks preserva la estructura real del contenido (párrafos vs listas)
tal como el docente la diseñó en PowerPoint.

  content[]        → igual que antes. Lista plana de strings.
                     La usan las métricas locales (ICD, WPS, etc.). No cambia.

  content_blocks[] → NUEVO. Lista de bloques estructurados.
                     Solo la usan los módulos de IA (ai_restructure.py).
                     Cada bloque es:
                       {"tipo": "parrafo", "texto": "..."}
                       {"tipo": "lista",   "items": ["...", "...", "..."]}

Con esto la IA sabe que "TCP/IP, UDP, HTTP" era un listado de viñetas,
no un párrafo corrido, y lo conserva o restructura respetando ese formato.
"""

import os
import re
from typing import List, Dict, Any, Optional
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

UMBRAL_SUPERIOR_TITULO = 0.25
UMBRAL_SUPERIOR_PIE    = 0.75
MAX_PALABRAS_TITULO    = 25
MAX_CARACTERES_TITULO  = 180

_RE_SOLO_NUMEROS = re.compile(r'^\d{1,3}$')

# Caracteres de viñeta que PowerPoint inserta como texto real
_CHARS_VINETA = frozenset('•·▪▸▹►▻◆◇○●◉✓✔→⇒-–—*')

_PATRONES_META = [
    re.compile(r'\b(materia|asignatura|unidad|semestre|grupo|docente|profesor|instituto|tecnol[oó]gico|universidad|facultad)\b', re.IGNORECASE),
    re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),
    re.compile(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', re.IGNORECASE),
    re.compile(r'\b[A-Z]{2,6}\d{3,4}\b'),
    re.compile(r'^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+$'),
]


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def contar_diapositivas(ruta_pptx: str) -> int:
    try:
        return len(Presentation(ruta_pptx).slides)
    except Exception as e:
        print(f"[text_extractor] Error al contar diapositivas: {e}")
        return 0


def extraer_datos_pptx(ruta_pptx: str) -> Dict[str, Any]:
    presentacion    = Presentation(ruta_pptx)
    altura_diap     = presentacion.slide_height

    resultado = {
        "filename":     os.path.basename(ruta_pptx),
        "total_slides": len(presentacion.slides),
        "slides":       [],
    }

    for indice, diapositiva in enumerate(presentacion.slides):
        resultado["slides"].append(
            _procesar_diapositiva(diapositiva, indice + 1, altura_diap)
        )

    return resultado


# ---------------------------------------------------------------------------
# PROCESAMIENTO POR DIAPOSITIVA
# ---------------------------------------------------------------------------

def _procesar_diapositiva(
    diapositiva: Any,
    numero: int,
    altura_diap: float,
) -> Dict[str, Any]:

    info = {
        "slide_number":      numero,
        "title":             "",
        "content":           [],        # igual que antes — métricas locales
        "content_blocks":    [],        # NUEVO — para módulos de IA
        "footer":            [],
        "images":            [],
        "tiene_solo_imagen": False,
    }

    # Título desde el placeholder oficial de PowerPoint
    if (
        diapositiva.shapes.title
        and diapositiva.shapes.title.has_text_frame
        and diapositiva.shapes.title.text.strip()
    ):
        titulo_crudo = _limpiar_texto_plano(diapositiva.shapes.title.text)
        if not _es_numero_decorativo(diapositiva.shapes.title, titulo_crudo, altura_diap):
            info["title"] = titulo_crudo

    candidatos_titulo: List[Dict[str, Any]] = []

    for forma in diapositiva.shapes:
        _procesar_forma(forma, info, candidatos_titulo, altura_diap)

    # Fallback de título si el placeholder oficial estaba vacío
    if not info["title"] and candidatos_titulo:
        candidatos_titulo.sort(key=lambda x: (x["size"] or 0, -x["top"]), reverse=True)
        mejor = candidatos_titulo[0]

        if mejor["words"] <= MAX_PALABRAS_TITULO and len(mejor["text"]) <= MAX_CARACTERES_TITULO:
            info["title"] = mejor["text"]
            # Los candidatos restantes van al contenido
            for c in candidatos_titulo[1:]:
                info["content"].append(c["text"])
                info["content_blocks"].append({"tipo": "parrafo", "texto": c["text"]})
        else:
            for c in candidatos_titulo:
                info["content"].append(c["text"])
                info["content_blocks"].append({"tipo": "parrafo", "texto": c["text"]})

    sin_texto = not info["content"] and not info["title"]
    info["tiene_solo_imagen"] = sin_texto and bool(info["images"])
    info["image_count"]       = len(info["images"])

    return info


# ---------------------------------------------------------------------------
# PROCESAMIENTO POR FORMA
# ---------------------------------------------------------------------------

def _procesar_forma(
    forma: Any,
    info: Dict[str, Any],
    candidatos_titulo: List[Dict[str, Any]],
    altura_diap: float,
) -> None:
    # Grupos: procesar hijos recursivamente
    if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
        for hijo in forma.shapes:
            _procesar_forma(hijo, info, candidatos_titulo, altura_diap)
        return

    # Imágenes y tablas (tratadas como visuales)
    es_imagen = (
        forma.shape_type == MSO_SHAPE_TYPE.PICTURE
        or (getattr(forma, "is_placeholder", False) and hasattr(forma, "image"))
        or forma.shape_type == MSO_SHAPE_TYPE.TABLE
    )
    if es_imagen:
        info["images"].append(getattr(forma, "name", "Tabla_o_Imagen"))
        return

    # Sin texto: ignorar
    if not getattr(forma, "has_text_frame", False) or not forma.text.strip():
        return

    texto_plano = _limpiar_texto_plano(forma.text)
    if not texto_plano or texto_plano == info["title"]:
        return

    if _es_numero_decorativo(forma, texto_plano, altura_diap):
        return

    proporcion_superior = forma.top / altura_diap
    conteo_palabras     = len(texto_plano.split())

    # Pie de página
    if proporcion_superior >= UMBRAL_SUPERIOR_PIE:
        if _es_pie_de_pagina(texto_plano, conteo_palabras, proporcion_superior):
            info["footer"].append(texto_plano)
            return

    # Candidato a título (zona superior, sin título aún)
    if not info["title"] and proporcion_superior < UMBRAL_SUPERIOR_TITULO:
        tamano = _obtener_tamano_fuente(forma)
        candidatos_titulo.append({
            "text":  texto_plano,
            "size":  tamano,
            "top":   forma.top,
            "words": conteo_palabras,
        })
        return

    # ── Contenido: aquí está el cambio principal ────────────────────────────
    # Extraemos los bloques estructurados de este cuadro de texto
    bloques = _extraer_bloques(forma)

    for bloque in bloques:
        if bloque["tipo"] == "parrafo":
            info["content"].append(bloque["texto"])
        else:  # lista
            # Para las métricas locales, cada ítem va como string plano
            info["content"].extend(bloque["items"])

    # Para los módulos de IA, van los bloques con su estructura
    info["content_blocks"].extend(bloques)


# ---------------------------------------------------------------------------
# EXTRACCIÓN DE BLOQUES ESTRUCTURADOS
# ---------------------------------------------------------------------------

def _extraer_bloques(forma: Any) -> List[Dict[str, Any]]:
    """
    Lee el text_frame de una forma y devuelve una lista de bloques.
    Cada bloque es {"tipo": "parrafo", "texto": "..."} o
                   {"tipo": "lista",   "items": [...]}.

    Estrategia:
    1. Recorre los párrafos del text_frame.
    2. Un párrafo es ítem de lista si:
       a) su nivel de indentación (level) es > 0, O
       b) tiene formato de bullet en el XML (buChar, buAutoNum), O
       c) su texto empieza con un carácter de viñeta conocido.
    3. Párrafos consecutivos de lista se agrupan en un bloque "lista".
    4. Párrafos que no son lista se emiten como bloques "parrafo" individuales.
    5. Si el text_frame tiene UN SOLO párrafo → siempre es "parrafo".
    """
    if not getattr(forma, "has_text_frame", False):
        return []

    paragraphs = forma.text_frame.paragraphs

    # Recopilar info de cada párrafo
    items_info: List[Dict] = []
    for p in paragraphs:
        texto = _texto_parrafo(p)
        if not texto:
            continue
        items_info.append({
            "texto":    texto,
            "es_lista": _parrafo_es_lista(p, texto),
        })

    if not items_info:
        return []

    # Un solo párrafo → siempre párrafo
    if len(items_info) == 1:
        return [{"tipo": "parrafo", "texto": items_info[0]["texto"]}]

    # Agrupar párrafos consecutivos
    bloques: List[Dict[str, Any]] = []
    acum_lista: List[str] = []

    for item in items_info:
        if item["es_lista"]:
            acum_lista.append(item["texto"])
        else:
            # Volcar lista acumulada si había
            if acum_lista:
                bloques.append({"tipo": "lista", "items": acum_lista})
                acum_lista = []
            bloques.append({"tipo": "parrafo", "texto": item["texto"]})

    # Volcar lista pendiente al final
    if acum_lista:
        bloques.append({"tipo": "lista", "items": acum_lista})

    return bloques


def _parrafo_es_lista(parrafo: Any, texto: str) -> bool:
    """
    Determina si un párrafo de python-pptx corresponde a un ítem de lista.
    Combina tres señales en orden de fiabilidad:
      1. nivel de indentación > 0 (más confiable)
      2. presencia de bullet en el XML
      3. el texto empieza con un carácter de viñeta (fallback)
    """
    # Señal 1: nivel de indentación
    try:
        if parrafo.level > 0:
            return True
    except Exception:
        pass

    # Señal 2: bullet declarado en el XML del párrafo
    try:
        pPr = parrafo._p.pPr
        if pPr is not None:
            nsmap = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            # buNone = bullet explícitamente desactivado
            bu_none   = pPr.find("a:buNone",   nsmap)
            # buChar   = bullet con carácter (•, -, etc.)
            bu_char   = pPr.find("a:buChar",   nsmap)
            # buAutoNum = lista numerada automática
            bu_auto   = pPr.find("a:buAutoNum", nsmap)
            # buFont   = tiene fuente de bullet definida (señal débil pero útil)
            bu_font   = pPr.find("a:buFont",   nsmap)

            if bu_none is None and (bu_char is not None or bu_auto is not None):
                return True
            # buFont sin buNone también indica viñeta heredada del tema
            if bu_none is None and bu_font is not None:
                return True
    except Exception:
        pass

    # Señal 3: carácter de viñeta al inicio del texto
    if texto and texto[0] in _CHARS_VINETA:
        return True

    return False


def _texto_parrafo(parrafo: Any) -> str:
    """Extrae el texto de un párrafo y lo limpia, eliminando caracteres de viñeta iniciales."""
    try:
        texto = parrafo.text.strip()
    except Exception:
        return ""

    if not texto:
        return ""

    # Eliminar carácter de viñeta al inicio (PowerPoint a veces los incluye en el texto)
    if texto and texto[0] in _CHARS_VINETA:
        texto = texto[1:].strip()

    return texto


# ---------------------------------------------------------------------------
# SERIALIZACIÓN PARA PROMPTS DE IA
# ---------------------------------------------------------------------------

def serializar_bloques_para_prompt(content_blocks: List[Dict[str, Any]]) -> str:
    """
    Convierte content_blocks[] en un string legible para la IA que preserva
    la distinción entre párrafos y listados.

    Resultado ejemplo:
      "Las redes permiten compartir recursos.
       - TCP/IP: protocolo estándar
       - UDP: sin garantía de entrega
       - HTTP: protocolo de la web
       Ejemplo: cuando abres un navegador usas HTTP sobre TCP/IP."

    Esta función la llama ai_restructure.py en lugar de hacer " ".join(content[]).
    """
    if not content_blocks:
        return ""

    partes: List[str] = []
    for bloque in content_blocks:
        if bloque["tipo"] == "parrafo":
            partes.append(bloque["texto"])
        elif bloque["tipo"] == "lista":
            items_formateados = "\n".join(f"- {item}" for item in bloque["items"])
            partes.append(items_formateados)

    return "\n".join(partes)


# ---------------------------------------------------------------------------
# UTILIDADES (sin cambios respecto a la versión anterior)
# ---------------------------------------------------------------------------

def _limpiar_texto_plano(texto: str) -> str:
    """
    Limpia un texto para uso en métricas locales y como título.
    Produce un string plano sin estructura (igual que _limpiar_texto anterior).
    """
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    return " ".join(lineas)


def limpiar_para_metricas(texto: str) -> str:
    if not texto:
        return ""
    return re.sub(r'\s+', ' ', texto).strip()


def _es_pie_de_pagina(texto: str, conteo_palabras: int, proporcion_superior: float) -> bool:
    if proporcion_superior >= 0.85 and conteo_palabras <= 25:
        return True
    if conteo_palabras <= 6:
        return True
    if conteo_palabras <= 15:
        for patron in _PATRONES_META:
            if patron.search(texto):
                return True
    return False


def _es_numero_decorativo(forma: Any, texto: str, altura_diap: float) -> bool:
    texto_limpio = texto.strip()
    if not _RE_SOLO_NUMEROS.match(texto_limpio):
        return False
    proporcion_superior = forma.top / altura_diap
    es_zona_num         = proporcion_superior < 0.05 or proporcion_superior > 0.90
    nombre_obj          = forma.name.lower()
    es_tipo_num_pagina  = "slide number" in nombre_obj or "page" in nombre_obj
    return es_zona_num or es_tipo_num_pagina


def _obtener_tamano_fuente(forma: Any) -> int:
    if getattr(forma, "has_text_frame", False):
        try:
            for parrafo in forma.text_frame.paragraphs:
                for run in parrafo.runs:
                    if run.font and run.font.size:
                        return int(run.font.size)
        except Exception:
            pass
    return 0