# app/core/logic/text_extractor.py
import os
import re
from typing import List, Dict, Any
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

# --- CONFIGURATION & THRESHOLDS ---
TITLE_TOP_THRESHOLD   = 0.25
FOOTER_TOP_THRESHOLD  = 0.75  
MAX_TITLE_WORDS       = 25
MAX_TITLE_CHARS       = 180

_RE_ONLY_NUMBERS = re.compile(r'^\d{1,3}$')

_META_PATTERNS = [
    re.compile(r'\b(materia|asignatura|unidad|semestre|grupo|docente|profesor|instituto|tecnol[oó]gico|universidad|facultad)\b', re.IGNORECASE),
    re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'),
    re.compile(r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', re.IGNORECASE),
    re.compile(r'\b[A-Z]{2,6}\d{3,4}\b'),
    re.compile(r'^[A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+ [A-ZÁÉÍÓÚ][a-záéíóú]+$'),
]

def count_slides(pptx_path: str) -> int:
    try:
        return len(Presentation(pptx_path).slides)
    except Exception as e:
        print(f"[text_extractor] Error counting slides: {e}")
        return 0

def extract_pptx_data(pptx_path: str) -> Dict[str, Any]:
    presentation = Presentation(pptx_path)
    slide_height = presentation.slide_height

    result = {
        "filename":     os.path.basename(pptx_path),
        "total_slides": len(presentation.slides),
        "slides":       []
    }

    for idx, slide in enumerate(presentation.slides):
        result["slides"].append(
            _process_slide(slide, idx + 1, slide_height)
        )

    return result

def _process_slide(slide: Any, slide_number: int, slide_height: float) -> Dict[str, Any]:
    slide_info = {
        "slide_number":      slide_number,
        "title":             "",
        "content":           [],
        "footer":            [],
        "images":            [],
        "tiene_solo_imagen": False,
    }

    if slide.shapes.title and slide.shapes.title.has_text_frame and slide.shapes.title.text.strip():
        raw_title = _clean_text(slide.shapes.title.text)
        if not _is_decorative_number(slide.shapes.title, raw_title, slide_height):
            slide_info["title"] = raw_title

    title_candidates: List[Dict[str, Any]] = []

    for shape in slide.shapes:
        _process_shape(shape, slide_info, title_candidates, slide_height)

    # Lógica para elegir el mejor candidato a título
    if not slide_info["title"] and title_candidates:
        title_candidates.sort(key=lambda x: (x["size"] or 0, -x["top"]), reverse=True)
        best_candidate = title_candidates[0]
        
        if best_candidate["words"] <= MAX_TITLE_WORDS and len(best_candidate["text"]) <= MAX_TITLE_CHARS:
            slide_info["title"] = best_candidate["text"]
            slide_info["content"].extend([c["text"] for c in title_candidates[1:]])
        else:
            slide_info["content"].extend([c["text"] for c in title_candidates])

    # Variables booleanas de control
    is_textless = len(slide_info["content"]) == 0 and slide_info["title"] == ""
    slide_info["tiene_solo_imagen"] = is_textless and len(slide_info["images"]) > 0
    
    # --- LA CONEXIÓN CON EL CORTAFUEGOS ---
    # Exportamos explícitamente el conteo de imágenes para que la IA sepa evadirlas
    slide_info["image_count"] = len(slide_info["images"])

    return slide_info

def _process_shape(shape: Any, slide_info: Dict[str, Any], title_candidates: List[Dict[str, Any]], slide_height: float) -> None:
    # Manejo de agrupaciones (Busca imágenes dentro de grupos)
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            _process_shape(child, slide_info, title_candidates, slide_height)
        return

    # Detección de Imágenes
    is_image = False
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        is_image = True
    elif getattr(shape, "is_placeholder", False) and hasattr(shape, "image"):
        is_image = True

    if is_image:
        slide_info["images"].append(shape.name)
        return

    # Detección de Tablas
    if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
        for row in shape.table.rows:
            for cell in row.cells:
                cell_text = _clean_text(cell.text)
                # CORRECCIÓN AQUÍ: Se pasa 'shape' (la tabla) en lugar de 'cell'
                if cell_text and not _is_decorative_number(shape, cell_text, slide_height):
                    slide_info["content"].append(cell_text)
        return

    # Extracción de Texto Normal
    if not getattr(shape, "has_text_frame", False) or not shape.has_text_frame or not shape.text.strip():
        return

    text = _clean_text(shape.text)
    if not text or text == slide_info["title"]:
        return

    if _is_decorative_number(shape, text, slide_height):
        return

    top_ratio = shape.top / slide_height
    word_count = len(text.split())

    # Detección de Pie de Página
    if top_ratio >= FOOTER_TOP_THRESHOLD:
        if _is_footer(text, word_count, top_ratio):
            slide_info["footer"].append(text)
            return

    # Detección de Títulos huérfanos
    if not slide_info["title"] and top_ratio < TITLE_TOP_THRESHOLD:
        font_size = _get_font_size(shape)
        title_candidates.append({
            "text": text, 
            "size": font_size,
            "top": shape.top, 
            "words": word_count
        })
        return

    slide_info["content"].append(text)
    
def _is_footer(text: str, word_count: int, top_ratio: float) -> bool:
    if top_ratio >= 0.85 and word_count <= 25:
        return True
    if word_count <= 6:
        return True
    if word_count <= 15:
        for pattern in _META_PATTERNS:
            if pattern.search(text):
                return True
    return False

def _is_decorative_number(shape: Any, text: str, slide_height: float) -> bool:
    clean_text = text.strip()
    if not bool(_RE_ONLY_NUMBERS.match(clean_text)):
        return False
    
    top_ratio = shape.top / slide_height
    is_numbering_zone = top_ratio < 0.05 or top_ratio > 0.90
    
    obj_name = shape.name.lower()
    is_page_num_type = "slide number" in obj_name or "page" in obj_name

    return is_numbering_zone or is_page_num_type

def _get_font_size(shape: Any) -> int:
    if getattr(shape, "has_text_frame", False):
        try:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.font and run.font.size:
                        return int(run.font.size)
        except Exception:
            pass
    return 0

def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return " \n ".join(lines)

def clean_for_metrics(text: str) -> str:
    if not text: return ""
    temp_text = re.sub(r'\s+', ' ', text)
    return temp_text.strip()