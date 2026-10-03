# app/core/logic/pptx_modifier.py
import os
import re
import copy
import zipfile
import tempfile
import shutil
import xml.etree.ElementTree as ET
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from pptx.text.text import _Paragraph

def aplicar_mejoras_pptx(ruta_original: str, ruta_destino: str, datos_analisis: dict) -> tuple[bool, str]:
    """
    Punto de entrada de la capa lógica. Orquesta la aplicación de mejoras en lote.
    Copia el archivo original y aplica las divisiones/reemplazos de texto
    en orden inverso para no afectar los índices XML.
    """
    try:
        # 1. Asegurar directorio y crear una copia exacta de trabajo
        os.makedirs(os.path.dirname(ruta_destino), exist_ok=True)
        shutil.copyfile(ruta_original, ruta_destino)

        diapositivas_datos = datos_analisis.get("slides", [])

        # 2. Recorrer de atrás hacia adelante (¡Clave para no arruinar los índices!)
        for info_diapositiva in reversed(diapositivas_datos):
            if info_diapositiva.get("requiere_reestructuracion") and info_diapositiva.get("reestructuracion"):
                
                num_diapositiva = info_diapositiva["slide_number"] # Base 1
                sugerencias = info_diapositiva["reestructuracion"].get("diapositivas_generadas", [])

                # Empaquetar los textos generados por la IA para el procesador
                lista_contenidos = []
                for sug in sugerencias:
                    lista_contenidos.append({
                        "titulo": sug.get("titulo_sugerido", ""),
                        "cuerpo": sug.get("contenido_optimizado", ""),
                        "formato": sug.get("formato", "")
                    })

                # 3. Aplicar la clonación y reemplazo físico en el archivo destino
                if lista_contenidos:
                    _dividir_y_reemplazar_diapositiva(ruta_destino, num_diapositiva, lista_contenidos)

        return True, "Presentación optimizada generada con éxito."
    except Exception as e:
        print(f"Error al manipular el PPTX (OpenXML): {e}")
        return False, f"Error al procesar la presentación: {str(e)}"


# =============================================================================
# FUNCIONES DE MANIPULACIÓN OPENXML Y PPTX (NÚCLEO DEL CLONADOR)
# =============================================================================

def _obtener_total_diapositivas(ruta_pptx: str) -> int:
    """Devuelve el total de diapositivas usando python-pptx."""
    presentacion = Presentation(ruta_pptx)
    return len(presentacion.slides)

def _obtener_etiqueta_local(etiqueta: str) -> str:
    """Limpia los namespaces de las etiquetas XML para facilitar la búsqueda."""
    if '}' in etiqueta:
        return etiqueta.split('}', 1)[1]
    return etiqueta

def _duplicar_diapositiva_en_paquete(ruta_pptx: str, indice_objetivo: int, num_copias: int):
    """
    Duplicación limpia y nativa a nivel de paquete OpenXML físico (ZIP).
    Clona los archivos .xml internos para preservar fondos y másteres.
    """
    if num_copias <= 1:
        return ruta_pptx

    directorio_temp = tempfile.mkdtemp()
    try:
        # 1. Descomprimir PPTX como si fuera un ZIP
        with zipfile.ZipFile(ruta_pptx, 'r') as zip_ref:
            zip_ref.extractall(directorio_temp)

        # Rutas a los manifiestos XML principales
        ruta_pres_xml = os.path.join(directorio_temp, "ppt", "presentation.xml")
        ruta_pres_rels = os.path.join(directorio_temp, "ppt", "_rels", "presentation.xml.rels")
        ruta_content_types = os.path.join(directorio_temp, "[Content_Types].xml")

        arbol_pres = ET.parse(ruta_pres_xml)
        raiz_pres = arbol_pres.getroot()

        arbol_rels = ET.parse(ruta_pres_rels)
        raiz_rels = arbol_rels.getroot()

        arbol_ct = ET.parse(ruta_content_types)
        raiz_ct = arbol_ct.getroot()

        # 2. Localizar la lista de diapositivas
        lista_ids_diapositivas = None
        for elemento in raiz_pres.iter():
            if _obtener_etiqueta_local(elemento.tag) == "sldIdLst":
                lista_ids_diapositivas = elemento
                break

        if lista_ids_diapositivas is None:
            raise ValueError("No se encontró la lista de diapositivas en presentation.xml")

        elementos_id_diapositiva = [hijo for hijo in lista_ids_diapositivas if _obtener_etiqueta_local(hijo.tag) == "sldId"]
        elemento_objetivo = elementos_id_diapositiva[indice_objetivo]

        id_relacion_objetivo = None
        for clave_attr, valor_attr in elemento_objetivo.attrib.items():
            if clave_attr.endswith("id") and valor_attr.startswith("rId"):
                id_relacion_objetivo = valor_attr
                break

        # 3. Localizar las dependencias de la diapositiva objetivo
        relacion_objetivo = None
        for relacion in raiz_rels.iter():
            if _obtener_etiqueta_local(relacion.tag) == "Relationship":
                if relacion.attrib.get("Id") == id_relacion_objetivo:
                    relacion_objetivo = relacion
                    break

        archivo_diapositiva_objetivo = os.path.basename(relacion_objetivo.attrib.get("Target", ""))
        ruta_diapositiva_objetivo = os.path.join(directorio_temp, "ppt", "slides", archivo_diapositiva_objetivo)
        ruta_rels_objetivo = os.path.join(directorio_temp, "ppt", "slides", "_rels", f"{archivo_diapositiva_objetivo}.rels")

        # 4. Calcular identificadores máximos actuales para no causar conflictos
        dir_diapositivas = os.path.join(directorio_temp, "ppt", "slides")
        archivos_existentes = [f for f in os.listdir(dir_diapositivas) if f.startswith("slide") and f.endswith(".xml")]
        
        numeros_diapositivas = [int(f.replace("slide", "").replace(".xml", "")) for f in archivos_existentes if f.replace("slide", "").replace(".xml", "").isdigit()]
        max_num_diapositiva = max(numeros_diapositivas) if numeros_diapositivas else 0

        ids_relaciones = []
        for rel in raiz_rels.iter():
            if _obtener_etiqueta_local(rel.tag) == "Relationship":
                str_rid = rel.attrib.get("Id", "")
                if str_rid.startswith("rId") and str_rid[3:].isdigit():
                    ids_relaciones.append(int(str_rid[3:]))
        max_rid = max(ids_relaciones) if ids_relaciones else 0

        ids_sld = [int(elem.attrib.get("id")) for elem in elementos_id_diapositiva if elem.attrib.get("id", "").isdigit()]
        max_id_sld = max(ids_sld) if ids_sld else 255

        # Espacios de nombres (Namespaces) obligatorios de OpenXML
        ns_rels = "http://schemas.openxmlformats.org/package/2006/relationships"
        ns_p = "http://schemas.openxmlformats.org/presentationml/2006/main"
        ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        ns_ct = "http://schemas.openxmlformats.org/package/2006/content-types"

        indice_insercion = list(lista_ids_diapositivas).index(elemento_objetivo) + 1

        # 5. Generar copias físicas en el directorio temporal
        for i in range(1, num_copias):
            max_num_diapositiva += 1
            max_rid += 1
            max_id_sld += 1

            nuevo_archivo = f"slide{max_num_diapositiva}.xml"
            nueva_ruta_xml = os.path.join(directorio_temp, "ppt", "slides", nuevo_archivo)
            nueva_ruta_rels = os.path.join(directorio_temp, "ppt", "slides", "_rels", f"{nuevo_archivo}.rels")
            nuevo_rid = f"rId{max_rid}"
            nuevo_id_str = str(max_id_sld)

            shutil.copyfile(ruta_diapositiva_objetivo, nueva_ruta_xml)
            if os.path.exists(ruta_rels_objetivo):
                shutil.copyfile(ruta_rels_objetivo, nueva_ruta_rels)

            # Registrar en content_types
            elemento_override = ET.Element(f"{{{ns_ct}}}Override", {
                "PartName": f"/ppt/slides/{nuevo_archivo}",
                "ContentType": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
            })
            raiz_ct.append(elemento_override)

            # Registrar relación
            elemento_relacion = ET.Element(f"{{{ns_rels}}}Relationship", {
                "Id": nuevo_rid,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
                "Target": f"slides/{nuevo_archivo}"
            })
            raiz_rels.append(elemento_relacion)

            # Insertar en la presentación visible
            nuevo_elemento_sldid = ET.Element(f"{{{ns_p}}}sldId", {
                "id": nuevo_id_str,
                f"{{{ns_r}}}id": nuevo_rid
            })
            lista_ids_diapositivas.insert(indice_insercion, nuevo_elemento_sldid)
            indice_insercion += 1

        # 6. Guardar manifiestos modificados
        arbol_pres.write(ruta_pres_xml, encoding="utf-8", xml_declaration=True)
        arbol_rels.write(ruta_pres_rels, encoding="utf-8", xml_declaration=True)
        arbol_ct.write(ruta_content_types, encoding="utf-8", xml_declaration=True)

        ruta_respaldo = ruta_pptx + ".bak"
        shutil.copyfile(ruta_pptx, ruta_respaldo)

        # 7. Volver a comprimir a .pptx
        with zipfile.ZipFile(ruta_pptx, 'w', zipfile.ZIP_DEFLATED) as zip_salida:
            for nombre_carpeta, _, nombres_archivos in os.walk(directorio_temp):
                for nombre_archivo in nombres_archivos:
                    ruta_archivo = os.path.join(nombre_carpeta, nombre_archivo)
                    nombre_relativo = os.path.relpath(ruta_archivo, directorio_temp)
                    zip_salida.write(ruta_archivo, nombre_relativo)

        if os.path.exists(ruta_respaldo):
            os.remove(ruta_respaldo)

    finally:
        shutil.rmtree(directorio_temp, ignore_errors=True)

def _obtener_formas_texto_recursivo(coleccion_formas) -> list:
    """Extrae recursivamente todas las formas con texto, evaluando grupos."""
    formas_texto = []
    for forma in coleccion_formas:
        if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
            formas_texto.extend(_obtener_formas_texto_recursivo(forma.shapes))
        elif forma.has_text_frame:
            formas_texto.append(forma)
    return formas_texto

def _extraer_estilo_fuente(forma) -> dict:
    """Extrae con precisión las propiedades tipográficas existentes."""
    estilo = {"name": None, "size": None, "bold": None, "italic": None, "color_rgb": None}
    if forma.has_text_frame and forma.text_frame.paragraphs:
        for parrafo in forma.text_frame.paragraphs:
            for run in parrafo.runs:
                if run.text.strip():
                    estilo["name"] = run.font.name
                    estilo["size"] = run.font.size
                    estilo["bold"] = run.font.bold
                    estilo["italic"] = run.font.italic
                    try:
                        if run.font.color and run.font.color.rgb:
                            estilo["color_rgb"] = run.font.color.rgb
                    except Exception:
                        pass
                    return estilo
    return estilo

def _establecer_texto_preservando_estilo(forma, texto: str):
    """Sobreescribe un cuadro de texto existente manteniendo su tipografía original."""
    estilo = _extraer_estilo_fuente(forma)
    marco_texto = forma.text_frame
    
    # Mantener únicamente el primer párrafo y eliminar residuales
    while len(marco_texto.paragraphs) > 1:
        parrafo_extra = marco_texto.paragraphs[-1]._p
        parrafo_extra.getparent().remove(parrafo_extra)
        
    parrafo = marco_texto.paragraphs[0]
    parrafo.text = ""
    run = parrafo.add_run()
    run.text = texto
    
    if estilo.get("name"): run.font.name = estilo["name"]
    if estilo.get("size"): run.font.size = estilo["size"]
    if estilo.get("bold") is not None: run.font.bold = estilo["bold"]
    if estilo.get("italic") is not None: run.font.italic = estilo["italic"]
    if estilo.get("color_rgb"): run.font.color.rgb = estilo["color_rgb"]

def _aplicar_estilo_run(run, estilo: dict):
    if estilo.get("name"): run.font.name = estilo["name"]
    if estilo.get("size"): run.font.size = estilo["size"]
    if estilo.get("bold") is not None: run.font.bold = estilo["bold"]
    if estilo.get("italic") is not None: run.font.italic = estilo["italic"]
    if estilo.get("color_rgb"): run.font.color.rgb = estilo["color_rgb"]


def _inferir_formato(texto: str) -> str:
    """Deduce el formato del contenido cuando la IA no lo declaró."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    n_vinetas = sum(1 for l in lineas if re.match(r"^\s*[-•]\s+", l))
    n_numeradas = sum(1 for l in lineas if re.match(r"^\s*\d+[.)]\s+", l))
    if n_numeradas > 0 and n_numeradas >= n_vinetas:
        return "numerada"
    if n_vinetas > 0:
        return "vinetas"
    return "parrafo"


def _marcar_item(parrafo, formato: str):
    """Aplica viñeta o numeración real (buChar/buAutoNum) al párrafo."""
    pPr = parrafo._p.get_or_add_pPr()
    pPr.set('marL', '228600')
    pPr.set('indent', '-228600')
    for tag in ('a:buNone', 'a:buChar', 'a:buAutoNum', 'a:buFont'):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    if formato == "vinetas":
        pPr.append(pPr.makeelement(qn('a:buFont'), {'typeface': 'Arial'}))
        pPr.append(pPr.makeelement(qn('a:buChar'), {'char': '•'}))
    elif formato == "numerada":
        pPr.append(pPr.makeelement(qn('a:buAutoNum'), {'type': 'arabicPeriod'}))


def _activar_autofit(forma):
    """Activa normAutofit para que PowerPoint reduzca la fuente si hay desbordamiento."""
    try:
        bodyPr = forma.text_frame._txBody.find(qn('a:bodyPr'))
        if bodyPr is None:
            return
        for tag in ('a:noAutofit', 'a:spAutoFit', 'a:normAutofit'):
            for el in bodyPr.findall(qn(tag)):
                bodyPr.remove(el)
        bodyPr.append(bodyPr.makeelement(qn('a:normAutofit'), {}))
        forma.text_frame.word_wrap = True
    except Exception:
        pass


def _crear_caja_titulo(diapositiva, texto: str):
    """Crea una caja de título cuando la diapositiva no tiene placeholder de título."""
    try:
        prs = diapositiva.part.package.main_document_part.presentation
        ancho = prs.slide_width
        alto = prs.slide_height
    except Exception:
        ancho, alto = 12192000, 6858000

    from pptx.util import Emu
    izquierda = Emu(int(ancho * 0.05))
    arriba = Emu(int(alto * 0.04))
    caja_ancho = Emu(int(ancho * 0.90))
    caja_alto = Emu(int(alto * 0.15))

    tb = diapositiva.shapes.add_textbox(izquierda, arriba, caja_ancho, caja_alto)
    tb.text_frame.word_wrap = True
    parrafo = tb.text_frame.paragraphs[0]
    run = parrafo.add_run()
    from pptx.util import Pt
    run.text = texto
    run.font.size = Pt(28)
    run.font.bold = True
    return tb


def _asegurar_sin_viñeta(parrafo):
    """Fuerza buNone en párrafos normales (evita viñetas heredadas del layout)."""
    pPr = parrafo._p.get_or_add_pPr()
    for tag in ('a:buChar', 'a:buAutoNum'):
        for el in pPr.findall(qn(tag)):
            pPr.remove(el)
    if pPr.find(qn('a:buNone')) is None:
        pPr.append(pPr.makeelement(qn('a:buNone'), {}))


def _insertar_cuerpo_con_formato(forma, texto: str, formato: str = ""):
    """
    Inserta el cuerpo respetando la clasificación de la IA:
      - "parrafo": cada línea es un párrafo de texto corrido.
      - "vinetas": oraciones introductorias como párrafo; ítems con viñeta (buChar).
      - "numerada": oraciones introductorias como párrafo; ítems con numeración
        automática (buAutoNum), descartando los números literales del texto.
    """
    formato = (formato or "").strip().lower()
    if formato not in ("parrafo", "vinetas", "numerada"):
        formato = _inferir_formato(texto)

    estilo = _extraer_estilo_fuente(forma)
    marco = forma.text_frame

    # Clasificar cada línea del contenido
    bloques = []  # (tipo, texto) — tipo: "parrafo" | "item"
    for linea in texto.splitlines():
        limpia = linea.strip()
        if not limpia:
            continue
        es_item = bool(re.match(r"^[-•]\s+", limpia) or re.match(r"^\d+[.)]\s+", limpia))
        if formato in ("vinetas", "numerada") and es_item:
            limpia = re.sub(r"^([-•]\s+|\d+[.)]\s+)", "", limpia)
            bloques.append(("item", limpia))
        else:
            bloques.append(("parrafo", limpia))

    if not bloques:
        return

    # Limpiar el marco: dejar solo el primer párrafo
    while len(marco.paragraphs) > 1:
        elem = marco.paragraphs[-1]._p
        elem.getparent().remove(elem)

    # Crear los párrafos adicionales clonando el primero (hereda estilos del layout)
    parrafos = [marco.paragraphs[0]]
    for _ in range(len(bloques) - 1):
        nuevo = copy.deepcopy(marco.paragraphs[0]._p)
        for r in nuevo.findall(qn('a:r')):
            nuevo.remove(r)
        for br in nuevo.findall(qn('a:br')):
            nuevo.remove(br)
        marco.paragraphs[-1]._p.addnext(nuevo)
        parrafos.append(_Paragraph(nuevo, marco))

    # Volcado con el formato correspondiente
    for parrafo, (tipo, contenido) in zip(parrafos, bloques):
        for r in list(parrafo.runs):
            r._r.getparent().remove(r._r)
        run = parrafo.add_run()
        run.text = contenido
        _aplicar_estilo_run(run, estilo)

        if tipo == "item" and formato in ("vinetas", "numerada"):
            _marcar_item(parrafo, formato)
        else:
            _asegurar_sin_viñeta(parrafo)


def _es_grafica(forma) -> bool:
    """Detecta imágenes, tablas, gráficos y marcos multimedia."""
    try:
        return forma.shape_type in (
            MSO_SHAPE_TYPE.PICTURE,
            MSO_SHAPE_TYPE.GRAPHIC_FRAME,
            MSO_SHAPE_TYPE.CHART,
            MSO_SHAPE_TYPE.MEDIA,
        )
    except Exception:
        return False


def _formas_graficas_recursivo(coleccion_formas) -> list:
    graficas = []
    for forma in coleccion_formas:
        if forma.shape_type == MSO_SHAPE_TYPE.GROUP:
            graficas.extend(_formas_graficas_recursivo(forma.shapes))
        elif _es_grafica(forma):
            graficas.append(forma)
    return graficas


def _rectangulos_solapan(a, b) -> bool:
    return not (
        a.left + a.width <= b.left or b.left + b.width <= a.left or
        a.top + a.height <= b.top or b.top + b.height <= a.top
    )


def _reducir_fuente(forma, factor: float = 0.8):
    """Reduce el tamaño de fuente de todos los runs como último recurso."""
    if not forma.has_text_frame:
        return
    for parrafo in forma.text_frame.paragraphs:
        for run in parrafo.runs:
            if run.font.size is not None:
                run.font.size = int(run.font.size * factor)


def _resolver_solape_cuerpo(forma, graficas, alto_slide):
    """
    Si el cuerpo se traslapa con una imagen/figura:
      1. Intenta moverlo debajo de la gráfica.
      2. Si no cabe, moverlo arriba.
      3. Si no cabe, ajusta su altura al espacio libre bajo la gráfica.
      4. Si aún se traslapa, reduce la fuente.
    """
    for grafica in graficas:
        if not _rectangulos_solapan(forma, grafica):
            continue

        margen = 91440  # 0.1 pulgada
        debajo = grafica.top + grafica.height + margen
        if debajo + forma.height <= alto_slide:
            forma.top = debajo
            continue

        arriba = grafica.top - forma.height - margen
        if arriba >= 0:
            forma.top = arriba
            continue

        disponible = alto_slide - debajo
        if disponible > 457200:  # al menos ~0.5"
            forma.top = debajo
            forma.height = disponible
        else:
            _reducir_fuente(forma)


def _localizar_cuerpo(diapositiva, formas_con_contenido):
    """
    Prioriza el placeholder de cuerpo real de la diapositiva;
    si no existe, usa la heurística de la segunda caja más alta.
    """
    try:
        from pptx.enum.shapes import PP_PLACEHOLDER
        tipos_cuerpo = (
            PP_PLACEHOLDER.BODY,
            PP_PLACEHOLDER.OBJECT,
            PP_PLACEHOLDER.VERTICAL_BODY,
            PP_PLACEHOLDER.VERTICAL_OBJECT,
        )
        for forma in diapositiva.shapes:
            if not forma.is_placeholder:
                continue
            if forma.placeholder_format.type in tipos_cuerpo and forma.has_text_frame:
                return forma
    except Exception:
        pass

    if len(formas_con_contenido) >= 2:
        return formas_con_contenido[1]
    return None


def _actualizar_diapositiva_jerarquica(diapositiva, texto_titulo: str, texto_cuerpo: str, formato: str = ""):
    """
    Escribe el título en el placeholder de título real de la diapositiva
    (si existe) y el cuerpo en el placeholder de cuerpo correspondiente.
    Como respaldo, usa la heurística de cajas de texto ordenadas verticalmente.
    """
    todas_las_formas = _obtener_formas_texto_recursivo(diapositiva.shapes)

    # Filtrar formas que tengan texto real y ordenarlas de arriba hacia abajo
    formas_con_contenido = [f for f in todas_las_formas if f.text_frame.text.strip()]
    formas_con_contenido.sort(key=lambda f: f.top)

    if not formas_con_contenido:
        return

    # --- TÍTULO: placeholder real primero, heurística de respaldo ---
    forma_titulo = None
    try:
        if diapositiva.shapes.title is not None and diapositiva.shapes.title.has_text_frame:
            forma_titulo = diapositiva.shapes.title
    except Exception:
        pass
    if forma_titulo is None and formas_con_contenido:
        forma_titulo = formas_con_contenido[0]

    if forma_titulo is None and texto_titulo:
        # La diapositiva no trae placeholder de título: crear uno nuevo
        forma_titulo = _crear_caja_titulo(diapositiva, texto_titulo)

    if forma_titulo is not None:
        if texto_titulo and forma_titulo.text_frame.text.strip() != texto_titulo:
            _establecer_texto_preservando_estilo(forma_titulo, texto_titulo)
        elif not texto_titulo:
            forma_titulo.text_frame.text = ""

    # --- CUERPO: placeholder de cuerpo primero, heurística de respaldo ---
    forma_cuerpo = _localizar_cuerpo(diapositiva, formas_con_contenido)

    if forma_cuerpo is not None:
        if texto_cuerpo:
            _insertar_cuerpo_con_formato(forma_cuerpo, texto_cuerpo, formato)
            _activar_autofit(forma_cuerpo)
        else:
            forma_cuerpo.text_frame.text = ""

        # Evitar sobreposición con imágenes/figuras
        try:
            alto_slide = diapositiva.part.package.main_document_part.presentation.slide_height
        except Exception:
            alto_slide = 6858000
        graficas = _formas_graficas_recursivo(diapositiva.shapes)
        if graficas:
            _resolver_solape_cuerpo(forma_cuerpo, graficas, alto_slide)

    # Limpiar notas o subtítulos sobrantes del diseño original
    usados = set()
    for f in (forma_titulo, forma_cuerpo):
        if f is not None:
            try:
                usados.add(f._element)
            except Exception:
                pass
    for forma_extra in formas_con_contenido:
        if forma_extra._element not in usados:
            forma_extra.text_frame.text = ""

    # Si la diapositiva tenía una sola gran caja y no se usó placeholder,
    # volcar título + cuerpo juntos con el formato correspondiente.
    if len(formas_con_contenido) == 1 and forma_cuerpo is None and forma_titulo is not None:
        texto_completo = f"{texto_titulo}\n{texto_cuerpo}".strip() if texto_titulo else texto_cuerpo
        if texto_completo:
            _insertar_cuerpo_con_formato(forma_titulo, texto_completo, formato)

def _dividir_y_reemplazar_diapositiva(ruta_pptx: str, num_diapositiva_objetivo: int, lista_contenidos: list):
    """
    Orquesta la clonación a nivel de paquete y la inyección jerárquica de texto.
    Abre y guarda el archivo en la misma ruta provista.
    """
    total = _obtener_total_diapositivas(ruta_pptx)
    if num_diapositiva_objetivo < 1 or num_diapositiva_objetivo > total:
        raise ValueError(f"Número de diapositiva inválido (1 a {total}).")

    indice_objetivo = num_diapositiva_objetivo - 1
    num_copias = len(lista_contenidos)

    # 1. Duplicación estricta a nivel XML ZIP
    _duplicar_diapositiva_en_paquete(ruta_pptx, indice_objetivo, num_copias)

    # 2. Inyección limpia de los textos sugeridos por la IA
    presentacion = Presentation(ruta_pptx)
    for i, contenido in enumerate(lista_contenidos):
        diapositiva_actual = presentacion.slides[indice_objetivo + i]
        _actualizar_diapositiva_jerarquica(
            diapositiva_actual,
            texto_titulo=contenido.get("titulo", ""),
            texto_cuerpo=contenido.get("cuerpo", ""),
            formato=contenido.get("formato", "")
        )

    # Sobreescribimos el archivo (que ya es el archivo destino temporal)
    presentacion.save(ruta_pptx)