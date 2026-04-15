import re
from typing import Dict, Any, List, Callable, Optional, Set

_STOPWORDS: Set[str] = {
    # (Stopwords en español)
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además", "este", "esta", "estos", 
    "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "aquellos", "aquellas",
    "yo","tú","él","ella","nosotros","ellos","me","te","se","nos","es","son"
}

_ACADEMIC_EXCLUSIONS: Set[str] = {
    "ejemplo", "caso", "importante", "definicion", "concepto", "introduccion", 
    "conclusion", "tema", "unidad", "capitulo", "objetivo", "descripcion", 
    "analisis", "nota", "resumen", "fundamentos", "presentacion"
}

_RE_PERSON_NAME = re.compile(
    r'[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}\s+[A-ZÁÉÍÓÚ][a-záéíóú]{2,}'
)
_RE_KEY_TOKENS = re.compile(r'[a-záéíóúüñ]{4,}', re.IGNORECASE)

def calculate_hss(slide_data: Dict[str, Any], llm_fn: Optional[Callable] = None) -> Dict[str, Any]:
    title = slide_data.get("title", "").strip()
    raw_content = " ".join(slide_data.get("content", []))
    clean_content = _filter_person_names(raw_content)
    
    base_result = {
        "slide_number": slide_data.get("slide_number"),
        "tiene_titulo": bool(title),
        "titulo": title,
        "hss_score": 0.0,
        "coherencia": "sin_titulo",
        "metodo_coherencia": "reglas"
    }

    if not title:
        return base_result

    title_keywords = _get_keywords(title)
    content_keywords = _get_keywords(clean_content)
    
    keyword_overlap = title_keywords.intersection(content_keywords)
    
    if keyword_overlap:
        base_result["hss_score"] = 10.0
        base_result["coherencia"] = "coherente"
        base_result["metodo_coherencia"] = "lexico"
        
    elif llm_fn:
        llm_score = llm_fn(title, clean_content)
        base_result["hss_score"] = float(llm_score) if llm_score is not None else 5.0
        base_result["metodo_coherencia"] = "llm_mistral_eval"
        
        if base_result["hss_score"] >= 8.0:
            base_result["coherencia"] = "coherente"
        elif base_result["hss_score"] >= 5.0:
            base_result["coherencia"] = "debil"
        else:
            base_result["coherencia"] = "no_coherente"
            
    else:
        base_result["hss_score"] = 5.0 if clean_content.strip() else 3.0
        base_result["coherencia"] = "revisar_manualmente"

    return base_result


def calculate_presentation_hss(content_slides: List[Dict[str, Any]], llm_fn: Optional[Callable] = None) -> Dict[str, Any]:
    results = [calculate_hss(s, llm_fn=llm_fn) for s in content_slides]
    scores = [r["hss_score"] for r in results]
    total_slides = len(results)

    return {
        "resultados": results,
        "hss_promedio": round(sum(scores) / total_slides, 2) if total_slides else 0.0,
        "slides_con_titulo": sum(1 for r in results if r["tiene_titulo"]),
        "slides_coherentes": sum(1 for r in results if r["coherencia"] == "coherente"),
        "slides_debiles": sum(1 for r in results if r["coherencia"] == "debil"),
        "slides_no_coherentes": sum(1 for r in results if r["coherencia"] == "no_coherente"),
        "cobertura_titulo": round((sum(1 for r in results if r["tiene_titulo"]) / total_slides * 100), 1) if total_slides else 0.0,
    }

def _get_keywords(text: str) -> Set[str]:
    if not text:
        return set()
    tokens = _RE_KEY_TOKENS.findall(text.lower())
    return {
        t for t in tokens 
        if t not in _STOPWORDS and t not in _ACADEMIC_EXCLUSIONS
    }

def _filter_person_names(text: str) -> str:
    return _RE_PERSON_NAME.sub("", text).strip()