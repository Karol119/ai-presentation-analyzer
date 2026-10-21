# Preprocesamiento: predicción de tiempo de exposición

Genera un JSON por cada presentación `.pptx` con una estimación del tiempo que
puede tomar exponerla, inspirada en el “tiempo de lectura” de los lectores
electrónicos, pero ajustada a una clase presencial.

## Uso

Desde la raíz del repositorio:

```bash
python -m tests.presentacion.preprocesamiento.generar_predicciones
```

Por defecto procesa `tests/presentacion/presentaciones/` y escribe cada JSON
junto a su presentación, con el mismo nombre base:

```
presentaciones/Sistemas distribuidos/Sockets.pptx
presentaciones/Sistemas distribuidos/Sockets.json
```

Opciones:

```bash
# Cambiar la velocidad de habla (palabras por minuto)
python -m tests.presentacion.preprocesamiento.generar_predicciones --wpm 130

# Ignorar las notas del orador
python -m tests.presentacion.preprocesamiento.generar_predicciones --sin-notas

# Guardar en otra carpeta, replicando la estructura de unidades
python -m tests.presentacion.preprocesamiento.generar_predicciones --salida ruta/salida

# Procesar otra carpeta
python -m tests.presentacion.preprocesamiento.generar_predicciones --entrada ruta/pptx
```

## Modelo de estimación

Para cada diapositiva:

1. **Palabras a pronunciar**
   - Texto visible: título + cuerpo.
   - Notas del orador, si existen.
   - Si hay notas, se usa `max(texto × 1.10, notas)` para no duplicar el mismo
     contenido. Sin notas, se aplica un factor de elaboración de 1.10.
2. **Tiempo de habla** = palabras / 140 ppm × 60.
3. **Tiempo visual**:
   - imágenes: 4 s (máximo 3 por diapositiva),
   - gráficos: 8 s (máximo 2),
   - tablas: 6 s (máximo 2).
4. **Pausas**: 2.5 s base + 0.3 s por párrafo/viñeta (máximo 10).
5. **Ajustes por tipo**:
   - portada: +6 s y mínimo 12 s,
   - cierre (“gracias”, “preguntas”, “referencias”): +2 s y mínimo 8 s,
   - transición: mínimo 6 s,
   - contenido con solo elementos visuales: mínimo 8 s,
   - contenido normal: mínimo 4 s.
6. El tiempo se acota a 240 s por diapositiva y se redondea al segundo.

El **tiempo total es la suma de los segundos redondeados** de cada diapositiva,
por lo que siempre coincide con la suma del arreglo `tiempo_por_diapositiva`.

Los parámetros quedan registrados dentro de cada JSON, en el objeto
`parametros`, para que la predicción sea reproducible y auditable.

## Estructura del JSON

```json
{
  "nombre_presentacion": "Sockets.pptx",
  "unidad_academica": "Sistemas distribuidos",
  "ruta_presentacion": "tests/presentacion/presentaciones/Sistemas distribuidos/Sockets.pptx",
  "total_diapositivas": 11,
  "tiempo_por_diapositiva": [
    {
      "numero_diapositiva": 1,
      "tipo": "portada",
      "palabras_texto": 0,
      "palabras_notas": 13,
      "imagenes": 1,
      "graficos": 0,
      "tablas": 0,
      "elementos": 0,
      "tiempo_texto_segundos": 5.6,
      "tiempo_visual_segundos": 4.0,
      "tiempo_pausas_segundos": 0.0,
      "tiempo_segundos": 18,
      "tiempo_formateado": "00:18"
    }
  ],
  "tiempo_total_segundos": 331,
  "tiempo_total_formateado": "05:31",
  "tiempo_total_minutos": 5.5,
  "parametros": { "palabras_por_minuto": 140.0 },
  "fecha_generacion": "2026-10-20T00:00:00",
  "presentada": false
}
```

`presentada` es el marcador solicitado y **siempre queda al final**. Al
regenerar un JSON existente se conserva su valor, de modo que una presentación
marcada como expuesta no vuelve a “pendiente”.

## Notas

- Los `.json` generados están cubiertos por la regla global `*.json` del
  `.gitignore`. Si se quieren versionar como evidencia:
  `git add -f tests/presentacion/presentaciones/<unidad>/<archivo>.json`.
- El programa no modifica el `.pptx` original ni usa la API de Gemini.
- La estimación es una referencia, no una medición real: el ritmo del docente,
  las pausas para preguntas y la interacción con el grupo pueden variar el
  resultado.
