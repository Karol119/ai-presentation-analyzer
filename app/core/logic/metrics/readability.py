# app/core/logic/metrics/readability.py
from typing import Dict, Any, Optional
from app.core.logic.metrics.text_counter import (
    contar_palabras, contar_silabas, segmentar_frases, preparar_texto_slide
)

def calculate_readability(slide_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = preparar_texto_slide(slide_data)

    word_count = contar_palabras(text)
    if word_count < 5:
        return None

    syllable_count = contar_silabas(text)
    sentences = segmentar_frases(text)
    num_sentences = len(sentences) if sentences else 1

    avg_syllables_per_word = syllable_count / word_count
    avg_words_per_sentence = word_count / num_sentences

    fsz = 206.835 - (62.3 * avg_syllables_per_word) - avg_words_per_sentence
    fsz = max(0.0, min(100.0, fsz))

    cf = (100.0 - fsz) / 100.0
    cf = round(max(0.0, min(1.0, cf)), 4)

    return {
        "palabras":     word_count,
        "silabas":      syllable_count,
        "frases":       num_sentences,
        "prom_sil_pal": round(avg_syllables_per_word, 3),
        "prom_pal_fra": round(avg_words_per_sentence, 3),
        "fsz":          round(fsz, 2),
        "cf":           cf,
        "fsz_zona":     _get_fsz_zone(fsz)
    }

def _get_fsz_zone(fsz: float) -> str:
    if fsz >= 80: return "muy facil"
    if fsz >= 65: return "facil"
    if fsz >= 50: return "normal"
    if fsz >= 35: return "dificil"
    if fsz >= 15: return "muy dificil"
    return "arido"