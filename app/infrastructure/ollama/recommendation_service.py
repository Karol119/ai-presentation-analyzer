"""
recommendation_service.py — Arquitectura Task Chaining

Integraciones activas:
  1. Extracción robusta de JSON mediante expresiones regulares.
  2. Cadena de Tareas (Task Chaining): División de inferencia (Contenido -> Título).
  3. Presupuesto de palabras ajustado (Max 69 contenido + Max 6 título = 75 total).
  4. Control determinista en la API de Ollama (temperature=0.0, seed=42).
  5. Instrucciones explícitas de conectores discursivos (NTS) y reducción léxica (ICD).
  6. Lógica estricta de omisión para diapositivas intencionalmente cortas.
"""
from app.core.logic.metrics.narrative_thread import calcular_similitud

import json
import re
import requests

OLLAMA_URL          = "http://localhost:11434/api/generate"
MODELO              = "mistral"
TIMEOUT_SEG         = 45
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
        if not verif.get("calculable") or verif.get("icd_zona") not in ("apropiado", "normal"):
            return False
    if "wps" in aspectos_mejorar:
        if verif.get("wps_zona") not in ("optima",):
            return False
    return True


def _es_mejor(verif_nuevo, verif_anterior, aspectos_mejorar):
    def score(v):
        s = 0
        if "icd" in aspectos_mejorar and v.get("icd_zona") in ("apropiado", "normal"): s += 2
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

    prompt = _PROMPT_DECISION.format(
        titulo=titulo or "(sin título)",
        contenido=contenido, 
        palabras=len(contenido.split())
    )
    
    parsed = _llamar_ollama(prompt, num_predict=150, temperatura=0.0)
    if isinstance(parsed, dict) and parsed.get("decision") in ("reestructurar", "dividir"):
        return parsed["decision"], parsed.get("n_slides", 2), parsed.get("razon", "")
        
    return "reestructurar", 2, "fallback"


# ── Prompts Task Chaining ─────────────────────────────────────────────────────
_PROMPT_DIVIDIR_CONTENIDO = """Eres un experto en presentaciones académicas universitarias.
El usuario requiere DIVIDIR la siguiente diapositiva en {n} partes porque excede el límite de palabras ({palabras} palabras).

REGLAS ESTRICTAS:
1. NO RESUMAS NI OMITAS CONCEPTOS. Transcribe la idea completa. En educación de nivel superior, no se pueden omitir definiciones.
2. REDUCIR COMPLEJIDAD (ICD): Expande las explicaciones utilizando un lenguaje natural y descriptivo para diluir la densidad léxica. Explica los términos técnicos como si estuvieras dando la clase en voz alta.
3. LONGITUD: Cada parte DEBE tener entre 50 y 70 palabras. No uses viñetas ni listas.
4. HILO NARRATIVO: La parte 2 y posteriores DEBEN comenzar con una frase de conexión que repita un concepto de la parte anterior (Ej. "Continuando con [concepto anterior]..."). Si los temas son inconexos, inicia explícitamente con "Cambiando de tema hacia...".

Contenido original:
{contenido}

Responde ÚNICAMENTE con un objeto JSON que contenga la clave "diapositivas", cuyo valor sea un array de {n} objetos. Usa esta estructura exacta:
{{
  "diapositivas": [
    {{"contenido": "texto expandido de la primera parte..."}},
    {{"contenido": "texto expandido de la segunda parte..."}}
  ]
}}"""

_PROMPT_REESTRUCTURAR = """Eres un experto en redacción académica para nivel universitario.
Tu tarea es REFORMULAR el siguiente texto para que sea más fácil de leer, sin perder ningún concepto.

MÉTRICAS ACTUALES (quieres bajar ambas):
- Promedio sílabas por palabra: {prom_sil_pal:.2f} → objetivo: menos de 2.3
- Promedio palabras por frase: {prom_pal_fra:.2f} → objetivo: menos de 12

REGLAS — en orden de prioridad:
1. PARTE LAS FRASES LARGAS. Cada oración debe tener máximo 12 palabras. Si una frase supera eso, divídela en dos con un punto.
2. SUSTITUYE palabras largas por sinónimos más cortos cuando existan. Ejemplos: "constituye" → "es", "mediante" → "con", "asimismo" → "también", "caracterizado por" → "que tiene".
3. Conserva TODOS los términos técnicos que no tienen sinónimo simple (ej. "fotosíntesis", "glucólisis"). Esos no se tocan.
4. NO añadas texto nuevo ni explicaciones extra. Solo reformula lo que ya existe.
5. El resultado debe tener máximo {max_pal} palabras.
6. Responde SIEMPRE en español.

TEXTO ORIGINAL:
Título: {titulo}
Cuerpo:
{contenido}

{contexto}

Responde ÚNICAMENTE con este JSON exacto (sin texto adicional):
{{"titulo_nuevo": "string en español, máximo 6 palabras, comprensible sin leer el contenido", "contenido_nuevo": "texto reformulado", "cambios_realizados": ["cambio 1", "cambio 2"], "justificacion": "una oración"}}"""   


_PROMPT_GENERAR_TITULO = """Eres un experto en diseño de presentaciones educativas para nivel universitario en México.
Lee el siguiente texto y genera un título claro y directo que resuma el concepto principal.

REGLAS:
- El título DEBE estar en español.
- El título DEBE tener entre 3 y 6 palabras.
- El título debe ser comprensible para un estudiante sin necesidad de leer el contenido.
- Prefiere frases simples sobre sustantivos técnicos encadenados.
- MALO: "Mecanismos de autorregulación y biodiversidad funcional en estabilidad ecosistémica"
- BUENO: "Cómo se estabiliza un ecosistema"
- NO uses comillas.

Texto:
{contenido}

Responde SOLO con este JSON (sin texto adicional):
{{"titulo": "tu titulo aqui"}}"""

# ── Sugerencia de división cuando el LLM falla ───────────────────────────────

def _generar_sugerencia_division(titulo, contenido, n_slides):
    lineas = [l.strip() for l in contenido.split("\n") if l.strip()]
    encabezados = [l for l in lineas if len(l.split()) <= 6 and not l.endswith(".")]

    if encabezados:
        temas = encabezados[:n_slides]
        return (
            f"Se sugiere dividir en {n_slides} diapositivas con los siguientes títulos: "
            + ", ".join(f'"{t}"' for t in temas)
            + ". Cada diapositiva debe contener entre 40 y 75 palabras."
        )
    return (
        f"Se sugiere dividir en {n_slides} diapositivas de 40-75 palabras cada una, "
        f"distribuyendo los conceptos de forma equitativa."
    )


# ── Generación Encadenada (Task Chaining) ─────────────────────────────────────

def _generar_division_encadenada(titulo, contenido, palabras, n_slides, temperatura=0.0):
    print(f"[rec] _generar_division: Paso 1 (Contenidos) - {n_slides} slides para {palabras} palabras")
    
    # PASO 1: Generar únicamente el contenido reestructurado
    prompt_contenido = _PROMPT_DIVIDIR_CONTENIDO.format(
        n=n_slides, palabras=palabras, contenido=contenido 
    )
    
    parsed_contenidos = _llamar_ollama(prompt_contenido, num_predict=2000, temperatura=temperatura)
    
    # --- NUEVA LÓGICA DE EXTRACCIÓN ---
    # Si Ollama devuelve un diccionario, buscamos el array en sus valores
    if isinstance(parsed_contenidos, dict):
        if "diapositivas" in parsed_contenidos:
            parsed_contenidos = parsed_contenidos["diapositivas"]
        else:
            # Fallback robusto: buscar el primer valor que sea una lista
            for val in parsed_contenidos.values():
                if isinstance(val, list):
                    parsed_contenidos = val
                    break
    # ----------------------------------
    
    if not isinstance(parsed_contenidos, list) or len(parsed_contenidos) < 2:
        print("[rec] Error en Paso 1: No se generó la lista de contenidos adecuadamente.")
        return None
        
    slides_completas = []
    
    # PASO 2: Generar título coherente para cada bloque de contenido
    for idx, item in enumerate(parsed_contenidos):
        # Llama a veces anida las respuestas si no sigue la estructura al 100%
        cont = item.get("contenido", "") if isinstance(item, dict) else str(item)
        if not cont:
            continue
            
        print(f"[rec] _generar_division: Paso 2 (Título) - fragmento {idx + 1}")
        prompt_tit = _PROMPT_GENERAR_TITULO.format(contenido=cont)
        
        parsed_tit = _llamar_ollama(prompt_tit, num_predict=150, temperatura=0.0)
        tit_generado = parsed_tit.get("titulo", f"Subtema {idx + 1}") if isinstance(parsed_tit, dict) else f"Subtema {idx + 1}"
        
        slides_completas.append({
            "titulo": tit_generado,
            "contenido": cont
        })
        
    return slides_completas


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
    tiene_imagen  = bool(slide_data.get("images", []))

    # Control estricto de omisión para diapositivas cortas
    if palabras_orig < 40 and "wps" in aspectos_mejorar:
        if len(aspectos_mejorar) == 1:
            base["omitida_razon"] = "Las diapositivas con bajo conteo de palabras son decisiones de diseño válidas."
            return base

    if aspectos_mejorar == ["wps"] and tiene_imagen:
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

            for intento in range(1, MAX_REINTENTOS + 1):
                base["intentos"] = intento
                temp_dinamica = 0.0 if intento == 1 else 0.2
                
                slides_div = _generar_division_encadenada(titulo, contenido, palabras_orig, n_slides, temperatura=temp_dinamica)

                if isinstance(slides_div, list) and len(slides_div) >= 2:
                    # AQUÍ SE MANDA A LLAMAR TU NUEVA FUNCIÓN
                    verificacion_div = _verificar_division_con_nts(slides_div)
                    todas_en_rango_intento = True

                    # Verificamos si pasaron el filtro
                    for s_verif in verificacion_div:
                        if not s_verif["en_rango"]:
                            todas_en_rango_intento = False

                    # --- NUEVA LÓGICA: Tolerancia a Complejidad Irreductible ---
                    if intento == MAX_REINTENTOS and not todas_en_rango_intento:
                        es_aceptable = True
                        for s_verif in verificacion_div:
                            # Si las palabras están bien, pero el ICD sigue alto tras 3 intentos, lo aceptamos
                            if s_verif["wps_zona"] == "optima" and s_verif["icd_zona"] in ("complejo", "muy complejo"):
                                s_verif["en_rango"] = True
                                s_verif["justificacion_icd"] = "Complejidad irreductible: la terminología técnica es esencial para el nivel superior."
                            elif not s_verif["en_rango"]:
                                es_aceptable = False # Falló por otra cosa (ej. WPS malo)
                        
                        if es_aceptable:
                            todas_en_rango_intento = True

                    mejor_div = slides_div
                    mejor_verif_div = verificacion_div

                    if todas_en_rango_intento:
                        todas_en_rango = True
                        break
            if mejor_div:
                base["slides_division"]       = mejor_div
                base["verificacion_division"] = mejor_verif_div
                base["sugerencia_division"]   = f"Dividido en {len(mejor_div)} diapositivas tras {base['intentos']} intentos. {razon}"
                
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
                        f"Conserva TODOS los conceptos del original en entre 40 y 69 palabras."
                    )
                elif wps_zona in ("densa", "saturada"):
                    notas.append(
                        f"PROBLEMA: tu respuesta tenía {pal_act} palabras — muy largo. "
                        f"Usa oraciones más cortas para presentar los mismos conceptos en máximo 69 palabras."
                    )

            if "icd" in aspectos_mejorar and icd_zona not in ("apropiado", "normal"):
                notas.append(
                    "PROBLEMA: el texto sigue siendo complejo. "
                    "Simplifica la redacción usando oraciones de máximo 15 palabras sin perder los conceptos técnicos."
                )

            if notas:
                contexto_iter += f"\n⚠ CORRECCIÓN INTENTO {intento}:\n" + "\n".join(notas)

        icd_data = next((r for r in score_slide.get("icd_resultados", [])), {})

        prompt = _PROMPT_REESTRUCTURAR.format(
            titulo=titulo,
            contenido=contenido_truncado,
            contexto=contexto_iter,
            max_pal=69,
            prom_sil_pal=icd_data.get("prom_sil_pal", 2.5),   # <-- nuevo
            prom_pal_fra=icd_data.get("prom_pal_fra", 14.0),   # <-- nuevo
        )

        temp      = 0.1 if intento > 1 else 0.0
        resultado = _llamar_ollama(prompt, num_predict=1000, temperatura=temp)

        # Manejo de error si Llama lo metió dentro de un array por accidente
        if isinstance(resultado, list) and len(resultado) > 0:
            resultado = resultado[0]

        if not isinstance(resultado, dict):
            base["error"] = f"Respuesta no es dict (intento {intento})"
            continue
# ... (código existente del prompt y llamado a ollama) ...
        
        titulo_nuevo    = resultado.get("titulo_nuevo", titulo)
        contenido_nuevo = resultado.get("contenido_nuevo", "")

        verif = _metricas_texto(titulo_nuevo, contenido_nuevo)
        base["verificacion"] = verif

        # --- NUEVA LÓGICA: Tolerancia a Complejidad Irreductible ---
        en_rango = _en_rangos(verif, aspectos_mejorar)
        
        if not en_rango and intento == MAX_REINTENTOS:
            if verif.get("wps_zona") == "optima" and verif.get("icd_zona") in ("complejo", "muy complejo") and "icd" in aspectos_mejorar:
                en_rango = True
                resultado["justificacion"] += " (Nota: Complejidad irreductible detectada debido al rigor técnico necesario)."

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

        if en_rango:
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
                  "options": {"temperature": 0.3, "top_p": 0.1, "seed": 42, "num_predict": 400}},
            timeout=TIMEOUT_SEG
        )
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception as e:
        return f"[Error: {e}]"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _llamar_ollama(prompt, num_predict=1000, temperatura=0.0):
    for i in range(2):
        try:
            # Si es el segundo intento, somos más explícitos
            p = prompt if i == 0 else prompt + "\n\nResponde ÚNICAMENTE con JSON válido."
            r = requests.post(
                OLLAMA_URL,
                json={
                    "model": MODELO, 
                    "prompt": p, 
                    "stream": False,
                    "format": "json", # <-- CLAVE PARA EVITAR ERRORES DE PARSEO
                    "options": {
                        "temperature": temperatura,
                        "top_p": 0.1,
                        "seed": 42,
                        "num_predict": num_predict
                    }
                },
                timeout=TIMEOUT_SEG
            )
            r.raise_for_status()
            
            respuesta_texto = r.json().get("response", "").strip()
            if not respuesta_texto:
                return None
                
            parsed = json.loads(respuesta_texto) # <-- Parseo directo, sin Regex
            if isinstance(parsed, (dict, list)):
                return parsed
                
        except Exception as e:
            print(f"[rec] _llamar_ollama intento {i+1} error: {e}")
    return None


def _parsear_json(texto):
    if not texto:
        return None
        
    match = re.search(r'(\[.*\]|\{.*\})', texto, re.DOTALL)
    
    if match:
        bloque_json = match.group(1)
        try:
            return json.loads(bloque_json)
        except json.JSONDecodeError as e:
            print(f"[parser] Error de decodificación JSON: {e}")
            return None
            
    return None

def _verificar_division_con_nts(slides_div):
    """Calcula métricas de cada slide incluyendo similitud con sus vecinas."""
    
    verificacion_div = []
    for idx, s in enumerate(slides_div):
        v = _metricas_texto(s.get("titulo", ""), s.get("contenido", ""))
        
        # Calcular similitud con slide anterior y siguiente
        texto_actual = s.get("contenido", "")
        texto_anterior = slides_div[idx - 1].get("contenido", "") if idx > 0 else None
        texto_siguiente = slides_div[idx + 1].get("contenido", "") if idx < len(slides_div) - 1 else None
        
        sim_ant = calcular_similitud(texto_anterior, texto_actual) if texto_anterior else None
        sim_sig = calcular_similitud(texto_actual, texto_siguiente) if texto_siguiente else None
        sims = [s for s in [sim_ant, sim_sig] if s is not None]
        nts_score = (sum(sims) / len(sims)) * 10 if sims else 0.0
        
        en_rango_wps = v.get("wps_zona") == "optima"
        en_rango_icd = v.get("icd_zona") in ("apropiado", "normal")
        
        verificacion_div.append({
            "titulo":   s.get("titulo", ""),
            "palabras": v.get("palabras"),
            "wps_zona": v.get("wps_zona"),
            "icd":      v.get("icd"),
            "icd_zona": v.get("icd_zona"),
            "nts_score": round(nts_score, 2),      # <-- nuevo
            "en_rango": en_rango_wps,
            "justificacion_icd": None,
        })
    
    return verificacion_div