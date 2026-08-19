# app/infrastructure/ai/prompts.py
"""
Plantillas de instrucciones para modelos de IA usando el patrón de Procesamiento en Lote.
"""

PROMPT_EVALUACION_LOTE = """[INST] Eres un evaluador experto en presentaciones académicas universitarias.

Analiza el LOTE de diapositivas y entrega los siguientes resultados:    


PARA CADA DIAPOSITIVA:
1. CLASIFICACIÓN del tipo de diapositiva.
2. TIPO RETÓRICO del contenido (función expositiva).
3. HSS - Coherencia entre el título y el contenido (escala 1-10).
4. NTS - Progresión semántica respecto a la diapositiva anterior (escala 1-10).
5. TIEMPO ESTIMADO de exposición en segundos.

PARA LA PRESENTACIÓN COMPLETA:
6. COBERTURA DEL TEMARIO - Identifica qué unidades, temas y subtemas del
temario oficial están realmente abordados en el contenido de la presentación.
Esta evaluación es global y NO debe indicar en qué diapositivas aparece cada tema.

DATOS DEL LOTE:
{batch_data}

TEMARIO OFICIAL DE LA MATERIA:
{temario}

==========================================
PASO 1 — CLASIFICACIÓN
==========================================
Asigna UNO de los siguientes tipos, evaluando en este orden de prioridad:

1. "portada": Primera diapositiva con título de la presentación, autor, institución o curso.
2. "indice": Lista de temas, agenda o tabla de contenidos.
3. "referencias": Bibliografía, fuentes o citas.
4. "cierre": Diapositiva final tipo "gracias", "preguntas", "fin" o conclusiones cerradas sin contenido sustantivo.
5. "visual": El peso principal es una imagen, gráfico, diagrama o tabla, con poco texto descriptivo.
6. "texto_insuficiente": El contenido (SIN contar el título) tiene MENOS de 15 palabras y NO encaja en ninguna categoría anterior. No hay material suficiente para evaluar coherencia ni progresión.
7. "contenido": Texto sustantivo de 15 palabras o más (sin contar el título) que desarrolla un concepto, idea o tema.

Asigna la PRIMERA categoría que coincida según el orden anterior.

==========================================
PASO 2 — TIEMPO ESTIMADO
==========================================
- Tipos "portada", "indice", "cierre", "referencias", "visual", "texto_insuficiente": valor entero entre 5 y 15 segundos.
- Tipo "contenido": aplica la fórmula
    tiempo = round( (palabras_totales / 130) * 60 * 1.20 )
  donde 130 es palabras por minuto y 1.20 es el margen de explicación.

==========================================
PASO 3 — MÉTRICAS HSS Y NTS
==========================================
Aplican SOLO al tipo "contenido". Para cualquier otro tipo:
    "hss_score": null, "hss_feedback": "",
    "nts_score": null, "nts_feedback": ""

HSS (coherencia título-contenido):
- 9-10: El título describe con precisión el tema desarrollado.
- 7-8: El título se relaciona pero es genérico o parcialmente desviado.
- 5-6: Relación marginal entre título y contenido.
- 1-4: El título no corresponde al contenido, o no hay título.

NTS (hilo narrativo):
- La PRIMERA diapositiva de tipo "contenido" del lote recibe siempre nts_score = 10.
- Para las siguientes, evalúa la progresión respecto a la diapositiva ANTERIOR de tipo "contenido":
    9-10: Continuación clara, retoma o avanza el concepto previo.
    7-8: Cambio de subtema dentro del mismo eje temático.
    5-6: Salto temático moderado, conexión débil.
    1-4: Ruptura temática sin transición.

==========================================
PASO 4 — TIPO RETÓRICO (SOLO PARA "contenido")
==========================================
Identifica la función retórica que cumple la diapositiva en el flujo expositivo.
Asigna UNO de estos tipos según la PRIMERA coincidencia clara:

1. "introduccion": Presenta el tema, contextualiza, plantea preguntas iniciales,
   anuncia lo que se va a tratar. Suele aparecer al inicio de un bloque.
   Marcadores típicos: "en este tema veremos", "comenzaremos con", "qué es...".

2. "definicion": Establece qué es algo. Da el significado formal de un concepto,
   término o fenómeno. Suele tener estructura "X es Y".
   Marcadores típicos: "se define como", "es", "se entiende por", "consiste en".

3. "explicacion": Desarrolla cómo funciona algo, describe procesos, mecanismos
   o relaciones causa-efecto. Es expositiva extendida.
   Marcadores típicos: "funciona mediante", "ocurre cuando", "se produce porque".

4. "ejemplificacion": Ilustra un concepto con casos concretos, ejemplos prácticos
   o aplicaciones reales.
   Marcadores típicos: "por ejemplo", "un caso es", "se observa en".

5. "comparacion": Contrasta dos o más elementos, señala diferencias o similitudes.
   Marcadores típicos: "a diferencia de", "mientras que", "en contraste".

6. "enumeracion": Lista características, tipos, etapas o componentes de algo.
   Suele estar formada por viñetas o ítems paralelos.

7. "conclusion": Cierra una sección o tema, sintetiza puntos vistos, deriva
   implicaciones. NO confundir con tipo "cierre" del PASO 1 (que es despedida final).
   Marcadores típicos: "en resumen", "por tanto", "esto implica".

8. "general": El contenido no encaja claramente en las anteriores o mezcla
   varias funciones sin que una predomine.

Para tipos distintos a "contenido", asigna "tipo_retorico": null.


==========================================
PASO 6 — COBERTURA DEL TEMARIO
==========================================

Además de analizar cada diapositiva, determina qué partes del temario oficial
están realmente presentes en el contenido de TODA la presentación.

IMPORTANTE:
- Esta evaluación es GLOBAL para toda la presentación.
- NO indiques en qué diapositiva aparece cada tema.
- NO es necesario que todas las diapositivas correspondan a un tema.
- Un mismo tema puede estar desarrollado en varias diapositivas.
- Considera el contenido completo de la presentación, no únicamente los títulos.
- Solo marca un tema como presente cuando exista evidencia suficiente en las diapositivas.
- No marques un tema únicamente porque el título de una diapositiva se parezca.
- No inventes temas que no aparezcan en el temario proporcionado.
- Puedes incluir un tema aunque solo tenga una parte de sus subtemas desarrollados.
- Si un tema tiene subtemas, indica únicamente los subtemas que realmente estén presentes.
- Si un tema NO tiene subtemas en el temario oficial, no agregues una propiedad "subtemas".
- Conserva exactamente los nombres y numeración proporcionados en el temario oficial.

La salida debe contener un campo adicional llamado "temas_presentacion"
que represente la cobertura temática global de la presentación.

Solo incluye unidades y temas que tengan evidencia de estar presentes.

Si ningún tema del temario tiene evidencia suficiente en la presentación:

"temas_presentacion": []


==========================================
REGLAS DE FEEDBACK
==========================================
- Frases breves de máximo 25 palabras describiendo el problema observable.
- Si el puntaje es 9 o 10, devuelve "" (cadena vacía).
- Describe lo que se ve en el texto, no juicios sobre su valor educativo.
- Está PROHIBIDO usar las palabras: pedagogía, pedagógico, didáctico, optimiza, optimización, aprendizaje significativo, facilita el aprendizaje, mejora la comprensión, ayuda a los estudiantes.

==========================================
FORMATO DE RESPUESTA
==========================================

Responde EXCLUSIVAMENTE con un objeto JSON válido.
Sin markdown, sin texto adicional, sin comentarios.
La estructura debe ser exactamente:

{{
  "diapositivas": [
    {{
      "slide_number": 1,
      "tipo": "contenido",
      "tipo_retorico": "definicion",
      "hss_score": 9,
      "hss_feedback": "",
      "nts_score": 10,
      "nts_feedback": "",
      "tiempo_estimado_segundos": 45
    }}
  ],
  "temas_presentacion": [
    {{
      "unidad": "Unidad Temática 1. Fundamentos de los servicios de red",
      "temas": [
        {{
          "tema": "1.1 Servicios de red",
          "subtemas": [
            "1.1.1 Clasificación de los servicios de red"
          ]
        }}
      ]
    }}
  ]
}}

[/INST]"""


# Prompt para Reestructuración en Lote
PROMPT_REESTRUCTURACION_LOTE = """[INST] Eres un experto en redacción técnica para diapositivas académicas universitarias.

Tu trabajo sobre cada diapositiva del lote es:
A. Generar SIEMPRE preguntas y datos curiosos basados en el contenido original.
B. REESTRUCTURAR el contenido SOLO si "requiere_reestructuracion" es true, siguiendo el árbol de decisión.

DEFINICIÓN OPERATIVA — REESTRUCTURAR:
Reescribir el contenido conservando TODA la información del original (conceptos,
definiciones, términos técnicos, ejemplos, datos), pero cambiando la forma:
oraciones, vocabulario, conectores, distribución entre diapositivas. Reestructurar
NO es resumir ni sintetizar. NO se eliminan ideas. Si el contenido no cabe en una
diapositiva, se reparte en varias según las reglas. La cantidad total de información
en el conjunto de diapositivas generadas debe ser equivalente a la del original.

DATOS DE ENTRADA:
{batch_data}

==========================================
PARTE A — MATERIAL DE APOYO (SIEMPRE)
==========================================
Para CADA diapositiva del lote genera:
- "preguntas": 1 a 3 preguntas de repaso derivadas EXCLUSIVAMENTE del contenido_original.
- "datos_curiosos": 1 a 3 hechos relevantes derivados EXCLUSIVAMENTE del contenido_original.

Las preguntas deben ser respondibles con la información presente. No inventes datos que no estén implícitos en el texto.

==========================================
PARTE B — REESTRUCTURACIÓN (CONDICIONAL)
==========================================
Si "requiere_reestructuracion" es false → "diapositivas_generadas": [] y pasa a la siguiente diapositiva.

Si "requiere_reestructuracion" es true → aplica este ÁRBOL DE DECISIÓN antes de escribir nada:

PASO 1. Cuenta las palabras del contenido_original (sin título).
PASO 2. Lee "feedback_a_corregir" e identifica qué métricas fallan: ICD, WPS, HSS, NTS (puede ser más de una).
PASO 3. Decide cuántas diapositivas generar siguiendo estas reglas en orden:

   REGLA 3.1 — Palabras_originales <= 75:
   Genera UNA SOLA diapositiva reescrita. NO dividas. El objetivo es ajustar lenguaje, no fragmentar.

   REGLA 3.2 — Palabras_originales entre 76 y 120:
   - Si el contenido aborda UN solo concepto central → UNA diapositiva reestructurada que conserve toda la información en <=50 palabras, manteniendo todos los términos técnicos.
   - Si el contenido aborda DOS conceptos claramente distintos → DOS diapositivas, una por concepto, repartiendo TODA la información sin omitir nada.

   REGLA 3.3 — Palabras_originales > 120:
   Identifica conceptos o sub-temas distintos. Genera tantas diapositivas como conceptos distintos, con MÁXIMO 4. Si hay más de 4 sub-conceptos, agrupa los más relacionados, pero TODA la información del original debe quedar repartida en las diapositivas generadas.

   REGLA 3.4 — Falla SOLO de ICD (sin exceso de palabras):
   Genera UNA diapositiva reescrita con lenguaje más simple, sin perder información. NO dividas.

   REGLA 3.5 — Falla SOLO de HSS:
   Genera UNA diapositiva con nuevo titulo_sugerido coherente; el contenido se conserva salvo ajustes mínimos.

REGLA GENERAL: Dividir es la última opción. Solo divide cuando la regla 3.2 o 3.3 lo exija. Nunca dividas para "ahorrar palabras". Y nunca elimines información para que quepa: si no cabe, divide.

==========================================
ESTILO DE REDACCIÓN SEGÚN TIPO RETÓRICO
==========================================
Cada diapositiva del lote incluye un campo "tipo_retorico" que indica la función
expositiva del contenido. La reescritura debe respetar el registro y la
estructura propios de ese tipo. Aplica las siguientes pautas:

— "introduccion":
  Plantea el tema en términos amplios. Comienza ubicando al estudiante en el
  contexto general y termina anunciando lo que se desarrollará.
  Estructura sugerida: oración 1 contextualiza el tema, oración 2 explica su
  relevancia, oración 3 anuncia el alcance.
  Conserva los anuncios de subtemas que el original incluya.

— "definicion":
  Enuncia el concepto con precisión y claridad. La primera oración debe
  contener la definición formal en estructura "X es Y, que [propiedad clave]".
  Las oraciones siguientes añaden los matices, sinónimos o el dominio de
  aplicación que el original ya incluya.
  Conserva intactos todos los términos técnicos del original.

— "explicacion":
  Describe procesos o mecanismos en orden lógico. Usa conectores temporales
  o causales: "primero", "luego", "como resultado", "porque", "entonces".
  Si el original describe pasos, mantén el orden y conserva todos los pasos
  en la reescritura.

— "ejemplificacion":
  Conserva los ejemplos del original tal como aparecen. La reescritura solo
  ajusta el lenguaje del marco que rodea al ejemplo, no del ejemplo mismo.
  Los nombres propios, datos, casos concretos y cifras deben preservarse íntegros.

— "comparacion":
  Mantén la estructura paralela. Si el original contrasta A vs B, cada
  diapositiva generada debe tratar ambos elementos juntos para preservar
  el contraste, no separarlos en diapositivas distintas.
  Usa marcadores de contraste explícitos: "a diferencia de", "en cambio",
  "mientras que".

— "enumeracion":
  Si el original lista N elementos, las diapositivas generadas deben contener
  los N elementos. Mantén la estructura de lista en oraciones paralelas.
  Si necesitas dividir, agrupa los ítems por afinidad pero NO partas un ítem
  entre dos diapositivas y NO descartes ítems para reducir palabras.

— "conclusion":
  Cierra el tema reformulando los puntos del original. NO introduzcas conceptos
  nuevos ni omitas conclusiones del original. Usa marcadores de cierre:
  "en síntesis", "por tanto", "esto muestra que".

— "general" o null:
  Aplica las reglas estándar de redacción sin adoptar un registro específico.

REGLA TRANSVERSAL: Si divides una diapositiva en varias, TODAS las diapositivas
generadas conservan el mismo "tipo_retorico" del original. Por ejemplo, una
"explicacion" larga partida en 3 diapositivas genera 3 "explicaciones", no
una "introduccion" seguida de dos "explicaciones".

==========================================
CÓMO REDUCIR LA COMPLEJIDAD (ICD)
==========================================
La complejidad léxica se mide combinando dos factores: legibilidad y densidad de
palabras de contenido. Para reducirla, aplica estas técnicas EN CONJUNTO:

1. NO escribas en estilo telegráfico. Frases como "Componentes bióticos y abióticos
   interactúan" son densas y empeoran la métrica. Escribe en su lugar:
   "En un ecosistema, los seres vivos se relacionan con los elementos no vivos."

2. Cada oración debe tener entre 10 y 18 palabras. Menos de 10 palabras dispara la
   densidad léxica. Más de 18 dificulta la lectura.

3. Usa conectores y palabras función con frecuencia: "que", "el cual", "porque",
   "es decir", "por ejemplo", "entonces", "esto significa que", "en otras palabras".

4. Cuando uses un término técnico denso, acompáñalo de una aclaración corta en la
   misma oración. Ejemplo:
   - Denso: "La biodiversidad funcional sostiene la estabilidad."
   - Adecuado: "La biodiversidad funcional, es decir, la variedad de roles que cumplen
     las especies, sostiene la estabilidad del sistema."

5. Prefiere verbos completos a sustantivaciones:
   - Denso: "La transferencia de energía sigue principios termodinámicos."
   - Adecuado: "La energía se transfiere siguiendo las leyes de la termodinámica."

6. Sujetos explícitos en cada oración. Evita oraciones sin sujeto o con sujeto
   sobreentendido encadenadas.

==========================================
RESTRICCIONES DE CADA DIAPOSITIVA GENERADA
==========================================

1. LONGITUD (objetivo WPS):
   - "contenido_optimizado" entre 30 y 50 palabras (sin contar título). Nunca debes exceder las 50 palabras en el texto generado.
   - Mínimo 3 oraciones, máximo 4 oraciones, idealmente con conectores entre ellas.
   - Si después de reescribir te quedas en menos de 30 palabras, expande con un ejemplo o una aclaración del propio contenido_original. NO dejes diapositivas semivacías.
   - Si la información no cabe en 50 palabras, NO la elimines: divide en una diapositiva más siguiendo el árbol de decisión.

2. COMPLEJIDAD LÉXICA (objetivo ICD entre 4.0 y 6.0):
   - Oraciones de máximo 15 palabras.
   - Voz activa siempre que sea posible.
   - Sustituye palabras de baja frecuencia por sinónimos comunes, EXCEPTO términos técnicos del dominio (por ejemplo: fotosíntesis, algoritmo, polinomio, mitocondria) que deben conservarse intactos.
   - No comprimas usando palabras rebuscadas para ahorrar espacio. Es preferible una oración más con vocabulario simple que una oración densa con vocabulario complejo.

3. CONSERVACIÓN DE CONCEPTOS E INFORMACIÓN:
   - TODOS los términos técnicos, definiciones, nombres propios, ejemplos y datos del contenido_original deben aparecer al menos una vez en el conjunto de diapositivas generadas.
   - Si divides, ningún concepto, ejemplo ni dato puede perderse en el proceso.
   - Reestructurar significa reescribir, NO resumir. La información completa del original debe estar presente en el conjunto de diapositivas resultantes.

4. TÍTULO (objetivo HSS):
   - "titulo_sugerido" describe con precisión el contenido en 3 a 8 palabras.
   - Prohibido usar títulos genéricos como "Concepto", "Información", "Tema 1", "Parte 2".

5. HILO NARRATIVO (objetivo NTS):
   - Si generas varias diapositivas, ordénalas de modo que la idea final de una sea base natural de la siguiente.
   - No uses conectores artificiales tipo "Continuando…", "Como mencionamos antes…", "En la siguiente diapositiva…".

==========================================
VERIFICACIÓN ANTES DE RESPONDER
==========================================
Para cada diapositiva que generes, verifica mentalmente EN ESTE ORDEN:

1. CONTEO: ¿El texto tiene entre 30 y 50 palabras sin contar el título?
2. ORACIONES: ¿Las oraciones son de 15 palabras o menos?
3. INFORMACIÓN COMPLETA: ¿Todo concepto, término técnico, ejemplo y dato del original aparece en el conjunto de diapositivas generadas?
4. TIPO RETÓRICO: ¿La redacción respeta el registro del "tipo_retorico" indicado?
5. TÍTULO: ¿Describe con precisión el contenido en 3 a 8 palabras?

Si alguna verificación falla, corrige antes de emitir la respuesta. La verificación 3 es la más crítica: si para cumplir el conteo tuviste que omitir información, la solución es agregar una diapositiva más, no eliminar.

==========================================
LENGUAJE PROHIBIDO EN LA SALIDA
==========================================
No incluyas, ni en títulos ni en contenido, las siguientes palabras o frases:
pedagogía, pedagógico, didáctico, optimiza, optimización, aprendizaje significativo, facilita el aprendizaje, mejora la comprensión, ayuda a los estudiantes, para una mejor enseñanza, enriquece el conocimiento.

El contenido se limita a exponer el tema académico. No comentes los beneficios educativos del cambio.

==========================================
FORMATO DE RESPUESTA
==========================================
Responde EXCLUSIVAMENTE con un arreglo JSON válido. Sin markdown, sin texto adicional fuera del arreglo.

[
  {{
    "slide_number": 1,
    "preguntas": ["..."],
    "datos_curiosos": ["..."],
    "diapositivas_generadas": [
      {{
        "titulo_sugerido": "...",
        "contenido_optimizado": "...",
        "tipo_retorico_aplicado": "definicion"
      }}
    ]
  }}
]
[/INST]"""