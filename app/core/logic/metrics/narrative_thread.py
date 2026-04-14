# app/core/logic/metrics/narrative_thread.py
import re
import math
from app.infrastructure.ollama.narrativa_service import verificar_hilo_narrativo

# Umbrales definidos por literatura de lingüística de corpus
UMBRAL_RELACIONADA = 0.15
UMBRAL_DEBIL       = 0.05
UMBRAL_FUERTE      = 0.30

_STOPWORDS = {
    "el","la","los","las","un","una","unos","unas","a","ante","bajo","con","contra",
    "de","desde","en","entre","hacia","hasta","para","por","según","sin","sobre",
    "tras","y","e","ni","o","u","pero","sino","aunque","porque","que","si","como",
    "cuando","donde","mientras","ya","también","además","yo","tú","él","ella",
    "nosotros","ellos","me","te","se","nos","es","son","era","fue","ser","estar"
}

def calcular_nts(slides_contenido, llm_fn=verificar_hilo_narrativo):
    
    if not slides_contenido:
        return _resumen_vacio()

    if len(slides_contenido) == 1:
        n = slides_contenido[0].get("slide_number")
        return {
            "resultados": [{
                "slide_number":  n,
                "sim_anterior":  None,
                "sim_siguiente": None,
                "sim_promedio":  1.0,   # puntuación perfecta
                "nts_score":     10.0,
                "estado":        "relacionada",
            }],
            "nts_promedio":        10.0,
            "slides_relacionadas": 1,
            "slides_debiles":      0,
            "slides_desconectadas":0,
        }
    
    if not slides_contenido or len(slides_contenido) < 2:
        return _resumen_vacio()

    vectores = [_vectorizar(_texto_completo(s)) for s in slides_contenido]
    n = len(vectores)
    resultados = []

    for i in range(n):
        # Calculamos similitudes individuales
        sim_ant = _evaluar_conexion(i-1, i, slides_contenido, vectores, llm_fn) if i > 0 else None
        sim_sig = _evaluar_conexion(i, i+1, slides_contenido, vectores, llm_fn) if i < n-1 else None

        sims_validas = [s for s in [sim_ant, sim_sig] if s is not None]
        sim_prom = sum(sims_validas) / len(sims_validas) if sims_validas else 0.0

        nts_score = _score_tramos(sim_prom)
        
        # AGREGAR: sim_anterior y sim_siguiente para el reporte detallado
        resultados.append({
            "slide_number":  slides_contenido[i].get("slide_number"),
            "sim_anterior":  round(sim_ant, 4) if sim_ant is not None else None,
            "sim_siguiente": round(sim_sig, 4) if sim_sig is not None else None,
            "sim_promedio":  round(sim_prom, 4),
            "nts_score":     nts_score,
            "estado":        _determinar_estado(sim_prom)
        })

    scores = [r["nts_score"] for r in resultados]

    return {
        "resultados": resultados,
        "nts_promedio": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "slides_relacionadas": sum(1 for r in resultados if r["estado"] == "relacionada"),
        "slides_debiles": sum(1 for r in resultados if r["estado"] == "debil"),
        "slides_desconectadas": sum(1 for r in resultados if r["estado"] == "desconectada"),
    }

# ── Helpers de Cálculo ───────────────────────────────────────────────────────

def _evaluar_conexion(idx1, idx2, slides, vectores, llm_fn):
    """
    Lógica híbrida: Coseno (rápido) -> Mistral (semántico).
    """
    coseno = _coseno(vectores[idx1], vectores[idx2])
    
    # Si la relación léxica es baja, pedimos juicio semántico al modelo
    if coseno < UMBRAL_RELACIONADA and llm_fn:
        t1 = _texto_completo(slides[idx1])
        t2 = _texto_completo(slides[idx2])
        nota_llm = llm_fn(t1, t2)
        
        if nota_llm:
            # Mapeamos la nota 1-10 del LLM al espacio de similitud (0.0 a 0.4)
            sim_llm = (nota_llm / 10.0) * 0.4
            return max(coseno, sim_llm)
            
    return coseno

def _score_tramos(sim):
    """Cálculo de score basado en los tramos definidos en el archivo de tesis."""
    if sim >= UMBRAL_FUERTE: return 10.0
    if sim >= UMBRAL_RELACIONADA:
        t = (sim - UMBRAL_RELACIONADA) / (UMBRAL_FUERTE - UMBRAL_RELACIONADA)
        return round(7.0 + t * 3.0, 2)
    if sim >= UMBRAL_DEBIL:
        t = (sim - UMBRAL_DEBIL) / (UMBRAL_RELACIONADA - UMBRAL_DEBIL)
        return round(3.0 + t * 4.0, 2)
    return round((sim / UMBRAL_DEBIL) * 3.0, 2)

def _vectorizar(texto):
    tokens = re.findall(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]{3,}', texto.lower())
    tokens = [t for t in tokens if t not in _STOPWORDS]
    if not tokens: return {}
    tf = {}
    for t in tokens: tf[t] = tf.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in tf.items()}

def _coseno(v1, v2):
    if not v1 or not v2: return 0.0
    comunes = set(v1.keys()) & set(v2.keys())
    if not comunes: return 0.0
    dot = sum(v1[t] * v2[t] for t in comunes)
    mag1 = math.sqrt(sum(x**2 for x in v1.values()))
    mag2 = math.sqrt(sum(x**2 for x in v2.values()))
    return dot / (mag1 * mag2)

def _texto_completo(slide_data):
    partes = [slide_data.get("title", "")] + slide_data.get("content", [])
    return " ".join([p.strip() for p in partes if p.strip()])

def _determinar_estado(sim):
    if sim >= UMBRAL_RELACIONADA: return "relacionada"
    if sim >= UMBRAL_DEBIL: return "debil"
    return "desconectada"

def _resumen_vacio():
    return {
        "resultados": [], "nts_promedio": 0.0,
        "slides_relacionadas": 0, "slides_debiles": 0,
        "slides_desconectadas": 0
    }