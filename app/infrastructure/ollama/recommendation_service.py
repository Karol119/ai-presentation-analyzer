"""
recommendation_service.py — v9 (Corregido para Tesis)

Cambios principales integrados:
  1. Corrección de omisión: Ya no omite la recomendación si la complejidad (ICD) necesita mejora.
  2. Límite de caracteres: Se aumentó drásticamente para no truncar párrafos.
  3. Validación de división: Se agregó un ciclo de reintentos para verificar que las nuevas diapositivas cumplan con las métricas.
  4. Contexto completo: Se eliminaron los truncamientos en los prompts para que la IA detecte todos los subtemas.
"""

import json
import re
import requests

OLLAMA_URL          = "http://localhost:11434/api/generate"
MODELO              = "llama3.2"
TIMEOUT_SEG         = 45
# [MODIFICADO - PUNTO 2]: Aumentado a 2500 para evitar que tome solo el primer párrafo
MAX_CONTENIDO_CHARS = 2500 
MAX_REINTENTOS      = 3
UMBRAL_FORZAR_DIV   = 100
UMBRAL_WPS_OMITIR   = 39


# ── Métricas sobre texto generado ────────────────────────────────────────────

def _metricas_texto(titulo, contenido):
    from app.core.logic.metrics.icd        import calcular_icd
    from app.core.logic.metrics.word_count import calcular_wps
    slide_sim = {
        "slide_number": 0, "title": titulo or "",
        "content": [contenido] if contenido else [],
        "footer": [], "images": [],
    }
    r_icd = calcular_icd(slide_sim)
    r_wps = calcular_wps(slide_sim)
    return {
        "icd":        r_icd.get("icd"),
        "icd_zona":   r_icd.get("zona"),
        "calculable": r_icd.get("calculable", False),
        "prom_sil_pal": r_icd.get("prom_sil_pal"),
        "palabras":   r_wps.get("palabras"),
        "wps_zona":   r_wps.get("zona"),
        "wps_score":  r_wps.get("wps_score"),
    }


def _en_rangos(verif, aspectos_mejorar):
    if "icd" in aspectos_mejorar:
        if not verif.get("calculable") or verif.get("icd_zona") != "apropiado":
            return False
    if "wps" in aspectos_mejorar:
        if verif.get("wps_zona") not in ("optima",):
            return False
    return True


def _es_mejor(verif_nuevo, verif_anterior, aspectos_mejorar):
    def score(v):
        s = 0
        if "icd" in aspectos_mejorar and v.get("icd_zona") == "apropiado": s += 2
        if "wps" in aspectos_mejorar and v.get("wps_zona") == "optima":   s += 2
        pal = v.get("palabras", 0) or 0
        if 40 <= pal <= 75: s += 1
        return s
    return score(verif_nuevo) > score(verif_anterior)


# ── Decisión: dividir o reestructurar ────────────────────────────────────────

_PROMPT_DECISION = """Eres un experto en presentaciones académicas universitarias.

La siguiente diapositiva tiene {palabras} palabras (máximo recomendado: 75).

Título: {titulo}
Inicio del contenido:
{contenido}

¿El contenido cubre UN SOLO tema (reestructurar) o MÚLTIPLES temas distintos (dividir)?

Responde SOLO con este JSON:
{{"decision": "reestructurar" o "dividir", "razon": "una oración", "n_slides": número entero si divides}}"""


def _contar_subtemas(contenido):
    lineas = [l.strip() for l in contenido.split("\n") if l.strip()]
    encabezados = sum(1 for l in lineas if len(l.split()) <= 6 and not l.endswith("."))
    return max(2, encabezados)


def _decidir_accion(titulo, contenido, exceso):
    if exceso > UMBRAL_FORZAR_DIV:
        n_temas = _contar_subtemas(contenido)
        return "dividir", max(2, n_temas), f"exceso de {exceso} palabras con múltiples temas"

    # [MODIFICADO - PUNTO 4]: Se eliminó el truncamiento de contenido[:600]
    prompt = _PROMPT_DECISION.format(
        titulo=titulo or "(sin título)",
        contenido=contenido, 
        palabras=len(contenido.split())
    )
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.0, "num_predict": 150}},
            timeout=25
        )
        r.raise_for_status()
        parsed = _parsear_json(r.json().get("response", ""))
        if isinstance(parsed, dict) and parsed.get("decision") in ("reestructurar", "dividir"):
            return parsed["decision"], parsed.get("n_slides", 2), parsed.get("razon", "")
    except Exception as e:
        print(f"[rec] _decidir_accion error: {e}")
    return "reestructurar", 2, "fallback"


# ── Prompts ───────────────────────────────────────────────────────────────────

_PROMPT_DIVIDIR = """Eres un experto en presentaciones académicas universitarias.

Divide el siguiente contenido en exactamente {n} diapositivas separadas.
Cada diapositiva debe:
- Tener un título claro de 3-6 palabras
- Tener entre 40 y 75 palabras de contenido
- Cubrir un solo subtema o concepto
- Conservar TODOS los conceptos del original sin eliminar ninguno

Título general: {titulo}
Contenido completo ({palabras} palabras):
{contenido}

IMPORTANTE: No elimines ningún concepto. Si hay N temas, cada diapositiva cubre uno.

Responde SOLO con un array JSON de {n} objetos:
[{{"titulo": "string de 3-6 palabras", "contenido": "string de 40-75 palabras"}}, ...]"""


_PROMPT_REESTRUCTURAR = """Eres un experto en presentaciones académicas universitarias.

Tu tarea es REESTRUCTURAR el contenido de esta diapositiva.

IMPORTANTE: NO es un resumen. NO elimines conceptos. Todos los conceptos del original deben aparecer en el resultado.

REGLAS:
1. Conserva TODOS los conceptos e ideas del contenido original
2. SOLO cambia la forma de presentarlos: oraciones más cortas, vocabulario más accesible
3. El resultado debe tener ENTRE {min_pal} Y {max_pal} PALABRAS
4. CONSERVA lo marcado con ✓
5. MEJORA lo marcado con MEJORAR
6. Responde SOLO con el JSON

CONTENIDO ORIGINAL ({pal_orig} palabras — todos los conceptos deben preservarse):
Título: {titulo}
Cuerpo:
{contenido}

{contexto}

{{"titulo_nuevo": "string", "contenido_nuevo": "string con TODOS los conceptos del original reorganizados", "cambios_realizados": ["cambio 1"], "justificacion": "una oración"}}"""


# ── Sugerencia de división cuando el LLM falla ───────────────────────────────

def _generar_sugerencia_division(titulo, contenido, n_slides):
    lineas = [l.strip() for l in contenido.split("\n") if l.strip()]
    encabezados = [l for l in lineas if len(l.split()) <= 6 and not l.endswith(".")]

    if encabezados:
        temas = encabezados[:n_slides]
        return (
            f"Se sugiere dividir en {n_slides} diapositivas con los siguientes títulos: "
            + ", ".join(f'"{t}"' for t in temas)
            + ". Cada diapositiva debe contener entre 40 y 75 palabras sobre ese subtema."
        )
    return (
        f"Se sugiere dividir en {n_slides} diapositivas de 40-75 palabras cada una, "
        f"distribuyendo los conceptos del contenido original de forma equitativa."
    )


# ── División con logging ──────────────────────────────────────────────────────

# [MODIFICADO - PUNTO 4]: Se eliminó el truncamiento de contenido[:1200] y se agregó parámetro de temperatura
def _generar_division(titulo, contenido, palabras, n_slides, temperatura=0.2):
    prompt = _PROMPT_DIVIDIR.format(
        n=n_slides, palabras=palabras, titulo=titulo,
        contenido=contenido 
    )
    print(f"[rec] _generar_division: solicitando {n_slides} slides para {palabras} palabras")
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": temperatura, "num_predict": 2000}},
            timeout=90
        )
        r.raise_for_status()
        texto = r.json().get("response", "")
        parsed = _parsear_json(texto)
        print(f"[rec] _generar_division: parsed type={type(parsed).__name__}")
        if isinstance(parsed, list) and len(parsed) >= 2:
            return parsed
    except Exception as e:
        print(f"[rec] _generar_division error: {e}")
    return None


# ── Función principal ─────────────────────────────────────────────────────────

def generar_recomendacion_slide(slide_data, score_slide):
    from app.core.logic.recommendation_prompt import construir_contexto_metricas

    num  = score_slide.get("slide_number")
    metr = score_slide.get("metricas", {})
    aspectos_mejorar = score_slide.get("aspectos_mejorar", [])

    base = {
        "slide_number":           num,
        "necesitaba_rec":         False,
        "omitida_razon":          None,
        "decision":               None,
        "titulo_nuevo":           None,
        "contenido_nuevo":        None,
        "slides_division":        None,
        "sugerencia_division":    None,
        "cambios_realizados":     [],
        "justificacion":          None,
        "verificacion":           None,
        "verificacion_division":  None,
        "intentos":               0,
        "no_resuelto":            False,
        "error":                  None,
    }

    if not score_slide.get("necesita_recomendacion"):
        return base

    icd_m = metr.get("icd", {})
    wps_m = metr.get("wps", {})

    if icd_m.get("irreducible") and "icd" in aspectos_mejorar:
        exceso_wps = wps_m.get("exceso", 0)
        if not (exceso_wps > 0 and wps_m.get("zona") in ("saturada", "densa")):
            base["omitida_razon"] = (
                "El texto tiene vocabulario técnico de nivel posgrado. "
                "Se recomienda revisar si el nivel es apropiado para el grupo."
            )
            return base

    palabras_orig = wps_m.get("palabras", 0)
    solo_wps      = aspectos_mejorar == ["wps"]
    tiene_imagen  = bool(slide_data.get("images", []))

    # [MODIFICADO - PUNTO 1]: Solo se omite si el ICD NO está entre los aspectos a mejorar.
    if palabras_orig <= UMBRAL_WPS_OMITIR:
        if "icd" not in aspectos_mejorar:
            base["omitida_razon"] = (
                f"La diapositiva tiene {palabras_orig} palabras. "
                "Las diapositivas cortas son válidas y su complejidad es adecuada."
            )
            return base

    if solo_wps and tiene_imagen:
        base["omitida_razon"] = "La diapositiva incluye imagen — decisión de diseño válida."
        return base

    base["necesitaba_rec"] = True

    titulo    = slide_data.get("title", "").strip() or "(sin título)"
    contenido = "\n".join(slide_data.get("content", []))
    exceso    = wps_m.get("exceso", 0)

    # ── Bloque de división ────────────────────────────────────────────────────
    if wps_m.get("zona") in ("saturada", "densa") and exceso > 0:
        decision, n_slides, razon = _decidir_accion(titulo, contenido, exceso)
        base["decision"] = decision

        if decision == "dividir":
            mejor_div = None
            mejor_verif_div = None
            todas_en_rango = False

            # [MODIFICADO - PUNTO 3]: Ciclo de validación para la división
            for intento in range(1, MAX_REINTENTOS + 1):
                base["intentos"] = intento
                temp_dinamica = 0.2 + (intento * 0.1) # Variamos ligeramente para evitar repetir error
                
                slides_div = _generar_division(titulo, contenido, palabras_orig, n_slides, temperatura=temp_dinamica)

                if isinstance(slides_div, list) and len(slides_div) >= 2:
                    verificacion_div = []
                    todas_en_rango_intento = True

                    for s in slides_div:
                        v = _metricas_texto(s.get("titulo", ""), s.get("contenido", ""))
                        en_rango = (v.get("wps_zona") == "optima" and v.get("icd_zona") == "apropiado")
                        
                        verificacion_div.append({
                            "titulo":   s.get("titulo", ""),
                            "palabras": v.get("palabras"),
                            "wps_zona": v.get("wps_zona"),
                            "icd":      v.get("icd"),
                            "icd_zona": v.get("icd_zona"),
                            "en_rango": en_rango,
                        })
                        
                        if not en_rango:
                            todas_en_rango_intento = False

                    mejor_div = slides_div
                    mejor_verif_div = verificacion_div

                    if todas_en_rango_intento:
                        todas_en_rango = True
                        break # Si todas cumplen, rompemos el ciclo de intentos

            if mejor_div:
                base["slides_division"]       = mejor_div
                base["verificacion_division"] = mejor_verif_div
                base["sugerencia_division"]   = f"Dividido en {len(mejor_div)} diapositivas tras {base['intentos']} intentos. {razon}"
                
                # Si terminaron los intentos y no todas quedaron en rango, se marca
                if not todas_en_rango:
                    base["no_resuelto"] = True
                return base 
            else:
                print(f"[rec] División falló para slide {num} — generando sugerencia")
                base["decision"]            = "division_fallida"
                base["sugerencia_division"] = _generar_sugerencia_division(titulo, contenido, n_slides)
                base["omitida_razon"] = (
                    f"El contenido ({palabras_orig} palabras) necesita dividirse en "
                    f"{n_slides} diapositivas. {base['sugerencia_division']}"
                )
                return base

    # ── Ciclo de reestructuración ─────────────────────────────────────────────
    contexto           = construir_contexto_metricas(score_slide)
    contenido_truncado = contenido[:MAX_CONTENIDO_CHARS]
    mejor_resultado    = None
    mejor_verif        = None

    for intento in range(1, MAX_REINTENTOS + 1):
        base["intentos"] = intento
        contexto_iter = contexto

        if intento > 1 and base.get("verificacion"):
            v        = base["verificacion"]
            pal_act  = v.get("palabras", 0) or 0
            wps_zona = v.get("wps_zona", "")
            icd_zona = v.get("icd_zona", "")
            notas    = []

            if "wps" in aspectos_mejorar:
                if wps_zona in ("escasa", "insuficiente"):
                    notas.append(
                        f"PROBLEMA: tu respuesta tenía {pal_act} palabras — muy corto. "
                        f"Recuerda: NO elimines conceptos. Reorganiza el contenido COMPLETO "
                        f"del original en entre 40 y 75 palabras."
                    )
                elif wps_zona in ("densa", "saturada"):
                    notas.append(
                        f"PROBLEMA: tu respuesta tenía {pal_act} palabras — muy largo. "
                        f"Usa oraciones más cortas para presentar los mismos conceptos "
                        f"en entre 40 y 75 palabras."
                    )

            if "icd" in aspectos_mejorar and icd_zona not in ("apropiado",):
                notas.append(
                    "PROBLEMA: el texto sigue siendo complejo. "
                    "Usa palabras cotidianas sin eliminar los conceptos: "
                    "'modifica' en vez de 'modula', "
                    "'depende de' en vez de 'está condicionado por', "
                    "oraciones de máximo 15 palabras."
                )

            if notas:
                contexto_iter += f"\n⚠ CORRECCIÓN INTENTO {intento}:\n" + "\n".join(notas)

        prompt = _PROMPT_REESTRUCTURAR.format(
            titulo=titulo,
            contenido=contenido_truncado,
            contexto=contexto_iter,
            pal_orig=palabras_orig,
            min_pal=40,
            max_pal=75
        )

        temp      = 0.1 if intento == 1 else 0.0
        resultado = _llamar_ollama(prompt, num_predict=1000, temperatura=temp)

        if not isinstance(resultado, dict):
            base["error"] = f"Respuesta no es dict (intento {intento})"
            continue

        titulo_nuevo    = resultado.get("titulo_nuevo", titulo)
        contenido_nuevo = resultado.get("contenido_nuevo", "")

        verif = _metricas_texto(titulo_nuevo, contenido_nuevo)
        base["verificacion"] = verif

        base.update({
            "titulo_nuevo":       titulo_nuevo,
            "contenido_nuevo":    contenido_nuevo,
            "cambios_realizados": resultado.get("cambios_realizados", []),
            "justificacion":      resultado.get("justificacion", ""),
            "error":              None,
        })

        if mejor_verif is None or _es_mejor(verif, mejor_verif, aspectos_mejorar):
            mejor_resultado = dict(base)
            mejor_verif     = verif

        if _en_rangos(verif, aspectos_mejorar):
            break

    if not _en_rangos(base.get("verificacion") or {}, aspectos_mejorar):
        base["no_resuelto"] = True
        if mejor_resultado:
            base.update({k: v for k, v in mejor_resultado.items()
                         if k in ("titulo_nuevo","contenido_nuevo",
                                  "cambios_realizados","justificacion","verificacion")})

    return base


def generar_resumen_presentacion(nombre, score_global, icd, wps, hss, nts):
    from app.core.logic.recommendation_prompt import generar_prompt_resumen
    prompt = generar_prompt_resumen(nombre, score_global, icd, wps, hss, nts)
    try:
        r = requests.post(
            OLLAMA_URL,
            json={"model": MODELO, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.3, "num_predict": 400}},
            timeout=TIMEOUT_SEG
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[Error: {e}]"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llamar_ollama(prompt, num_predict=1000, temperatura=0.1):
    for i in range(2):
        try:
            p = prompt if i == 0 else prompt + "\n\nResponde SOLO con el JSON entre llaves {}."
            r = requests.post(
                OLLAMA_URL,
                json={"model": MODELO, "prompt": p, "stream": False,
                      "options": {"temperature": temperatura,
                                  "num_predict": num_predict}},
                timeout=TIMEOUT_SEG
            )
            r.raise_for_status()
            parsed = _parsear_json(r.json().get("response", ""))
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            print(f"[rec] _llamar_ollama intento {i+1} error: {e}")
    return None


def _parsear_json(texto):
    if not texto:
        return None
        
    # Extracción de estructura JSON omitiendo texto conversacional o markdown
    match = re.search(r'(\[.*\]|\{.*\})', texto, re.DOTALL)
    
    if match:
        bloque_json = match.group(1)
        try:
            return json.loads(bloque_json)
        except json.JSONDecodeError as e:
            print(f"[parser] Error de decodificación JSON: {e}")
            return None
            
    return None