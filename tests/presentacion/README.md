# Pruebas de presentación en vivo

Suite dedicada a simular una clase real: se abre una presentación con el modo
de presentación del prototipo, se configura la sesión, se navega por las
diapositivas, se controlan los cronómetros y se genera el reporte de tiempos.

Esta carpeta concentra los tres elementos necesarios para esa validación.

## Estructura

```
tests/presentacion/
├── __init__.py
├── README.md
├── presentaciones/          # 1. Archivos .pptx que se van a probar
│   ├── <Unidad académica>/  # Una carpeta por unidad de la base de datos
│   │   ├── *.pptx           # Presentación
│   │   └── *.json           # Predicción de tiempo (mismo nombre base)
│   ├── .gitkeep
│   └── README.md            # Convención de nombres y escenarios
├── pruebas/                 # 2. Código de las pruebas
│   ├── __init__.py
│   ├── crear_carpetas_unidades.py  # Genera las carpetas desde la BD
│   ├── cargar_presentaciones_gui.py  # Automatización de carga por GUI
│   ├── analizar_presentaciones_gui.py # Automatización de análisis por GUI
│   ├── presentar_presentaciones.py   # Presenta en paralelo las pendientes
│   └── plantillas/          # Capturas de referencia para la automatización
├── evidencias/              # Capturas de pantalla de las corridas
│   └── <AAAAMMDD_HHMMSS>/   # Una carpeta por corrida de automatización
├── preprocesamiento/        # Predicción de tiempo de exposición
│   ├── __init__.py
│   ├── estimador_tiempo.py
│   ├── generar_predicciones.py
│   └── README.md
└── reportes/                # 3. Reportes generados por cada corrida
    ├── .gitkeep
    ├── .gitignore
    └── README.md            # Formato de los reportes
```

## Flujo de trabajo previsto

1. Copiar cada presentación de prueba en la carpeta de su unidad académica
   dentro de `presentaciones/`, siguiendo la convención
   `<numero>_<tema>_<n_diapositivas>.pptx`.
2. Ejecutar el preprocesamiento para generar la predicción de tiempo:

   ```bash
   python -m tests.presentacion.preprocesamiento.generar_predicciones
   ```

   Cada `.pptx` produce un `.json` con el mismo nombre base, el tiempo por
   diapositiva, el total y el marcador `presentada`.
3. Implementar los casos en `pruebas/` usando `unittest`, igual que
   `tests/e2e/`.
4. Ejecutar la suite; cada corrida crea `reportes/<AAAAMMDD_HHMMSS>/` con el
   resumen y la salida cruda de cada módulo.

Comando previsto para la suite (aún no implementado):

```bash
python -m tests.presentacion.pruebas.run_presentacion
```

## Automatización de carga por GUI

`pruebas/cargar_presentaciones_gui.py` abre `main.py`, agrega las cinco
unidades solicitadas mediante el modal "Agregar materia" y sube hasta cinco
presentaciones por unidad usando la tarjeta "Subir presentación" y el diálogo
de archivos de Windows. No importa módulos internos ni escribe directamente en
la base de datos: toda la interacción es por clics y teclado sobre la GUI real.

```bash
python tests/presentacion/pruebas/cargar_presentaciones_gui.py
python tests/presentacion/pruebas/cargar_presentaciones_gui.py --solo "Sistemas distribuidos" --max 5
```

- Omite automáticamente los `.pptx` mayores a 30 MB y los reporta en el resumen.
- Guarda una captura por cada paso relevante en
  `evidencias/<AAAAMMDD_HHMMSS>/`, con nombres descriptivos.
- Deja la aplicación abierta al terminar y escribe `resumen.txt` y
  `registro.txt` en la carpeta de evidencias.
- Requiere `pyautogui`, `pyperclip`, `opencv-python`, `pillow` y `psutil`.
- Las plantillas de `pruebas/plantillas/` están calibradas para la escala de
  Windows de este equipo (125 %) y la ventana de 1900x1040. Si cambia la escala
  o el tema de la app, hay que recapturarlas.
- La automatización trae la app al frente y manda al fondo la ventana activa
  (por ejemplo, el editor). Al terminar restaura la ventana y quita el modo
  "siempre visible" de la app.

## Automatización de análisis por GUI

`pruebas/analizar_presentaciones_gui.py` recorre una por una las
presentaciones ya cargadas y dispara el análisis desde el menú
"Ver opciones" de cada tarjeta, usando siempre la GUI real. Espera a que
termine cada análisis antes de continuar y deja una pausa configurable entre
presentaciones para respetar el límite de tokens por minuto de Gemini.

```bash
python tests/presentacion/pruebas/analizar_presentaciones_gui.py
python tests/presentacion/pruebas/analizar_presentaciones_gui.py --pausa 90
python tests/presentacion/pruebas/analizar_presentaciones_gui.py --solo "Administración de Servicios en Red"
python tests/presentacion/pruebas/analizar_presentaciones_gui.py --max 1
python tests/presentacion/pruebas/analizar_presentaciones_gui.py --carpeta tests/presentacion/evidencias/analisis_20261020_071045
```

- Procesa únicamente las presentaciones cuyo historial aún tiene
  `analisis = 0`; si se interrumpe, al volver a ejecutarlo continúa con las
  pendientes.
- `--carpeta` reutiliza una carpeta de evidencias existente, continúa la
  numeración de capturas y escribe un resumen con el estado final de todas
  las presentaciones.
- Pausa por defecto: 75 s entre presentaciones. Los reintentos por error
  esperan 180 s y se detienen si la cuota diaria o la API Key son inválidas.
- Guarda `cargando_*`, `analisis_*_diapositiva_01..03`, `error_*` y
  `resumen_materia_*` en `evidencias/analisis_<AAAAMMDD_HHMMSS>/`.
- Escribe `resumen.txt`, `registro.txt` y, si la app fue lanzada por el
  script, `app_salida.txt` con la salida de la aplicación.
- La materia activa se reconoce por el título del panel, no por el orden de
  la barra lateral. Las plantillas de materias están en `pruebas/plantillas/`.
- Requiere las mismas dependencias y la misma calibración de pantalla que la
  automatización de carga.

## Presentación automática de una materia

`pruebas/presentar_presentaciones.py` abre la aplicación real, pregunta la
materia y el grupo, y presenta **en paralelo** todas las presentaciones
pendientes de esa materia. Cada presentación se ejecuta en un proceso
independiente de la app.

Los procesos se lanzan **en secuencia**: el orquestador espera a que el
anterior marque `"presentada": true` y envíe la señal de inicio, y entonces
lanza el siguiente. No espera a que termine la presentación, por lo que al
final todos avanzan al mismo tiempo. Por defecto se ejecutan en modo
**headless** (sin ventanas visibles) para que las proyecciones no se encimen.

```bash
python tests/presentacion/pruebas/presentar_presentaciones.py
```

El programa:

1. Pregunta la materia (solo materias activas) y el grupo escolar.
2. Verifica que cada presentación cargada tenga análisis y JSON de tiempos.
3. Omite las que ya tienen `presentada: true` (usa `--repetir` para incluirlas).
4. Asigna un tiempo de clase variable: alterna **igual**, **menor** y
   **mayor** respecto al total del JSON (siempre entre 1 y 90 minutos).
5. Lanza un proceso por presentación; cada uno llena el formulario
   "Configuración de Sesión", inicia la proyección y avanza las diapositivas
   según el JSON.
6. Al iniciar cada proyección escribe `presentada: true` y avisa al
   orquestador para que lance el siguiente proceso.
7. Espera a que todos terminen y guarda `registro.txt`, `resumen.txt`, los
   `.out.txt` y `.result.json` de cada trabajador en
   `evidencias/presentacion_<AAAAMMDD_HHMMSS>/`.

Opciones útiles:

```bash
# Sin preguntas (materia y grupo por argumento)
python tests/presentacion/pruebas/presentar_presentaciones.py \
  --materia "Sistemas distribuidos" --grupo 7CM1

# Incluir también las ya presentadas (útil para volver a probar)
python tests/presentacion/pruebas/presentar_presentaciones.py \
  --materia "Sistemas distribuidos" --grupo 7CM1 --repetir

# Solo mostrar el plan, sin abrir la app
python tests/presentacion/pruebas/presentar_presentaciones.py \
  --materia "Sistemas distribuidos" --grupo 7CM1 --dry-run

# Prueba rápida de dos presentaciones en paralelo
python tests/presentacion/pruebas/presentar_presentaciones.py \
  --materia "Sistemas distribuidos" --grupo 7CM1 \
  --repetir --limite 2 --escala-tiempo 0.03 --sin-mensaje
```

- `--repetir`: incluye las presentaciones que ya tienen `presentada: true`.
- `--limite N`: toma solo las primeras N presentaciones.
- `--escala-tiempo F`: multiplica los tiempos del JSON (solo para pruebas).
- `--visible`: muestra las ventanas; las proyecciones se encimarán.
- `--cerrar`: cierra cada app al terminar.
- `--sin-mensaje`: omite la confirmación y el cuadro final (pruebas).
- `--timeout-inicio S`: espera máxima para la señal de inicio de cada proceso.
- `--timeout-total S`: duración máxima permitida a cada proceso.

Si una presentación cargada no tiene análisis o JSON, el programa se detiene
antes de abrir la app y enumera las que faltan. La presentación se marca como
`presentada` en el JSON al iniciar la proyección, no al finalizar. En modo
headless no se rasterizan las diapositivas, pero se conservan los cambios de
página y los cronómetros que alimentan el reporte de tiempos.

## Áreas a cubrir

Según el protocolo de pruebas del prototipo (módulo de presentación en vivo):

- Acceso al modo presentación desde una versión ya analizada.
- Formulario de configuración de la sesión (materia, grupo, modo, duración).
- Ensamblaje del visor y del panel de datos.
- Navegación entre diapositivas y sincronización con la proyección.
- Cronómetros por diapositiva y tiempo total de exposición.
- Detención de la sesión y guardado del reporte JSON de tiempos.
- Salida de la vista sin perder el avance registrado.

## Aislamiento

Las pruebas deben seguir el patrón de `tests/e2e/sandbox.py`: trabajar sobre
una copia temporal de `app/` y un `storage/` propio, de modo que la base de
datos, las presentaciones y los archivos del usuario no se modifiquen.

## Estado

Estructura inicial creada en la rama `Entorno-de-pruebas`. El
preprocesamiento de tiempos está implementado y ejecutado sobre las 49
presentaciones disponibles; las carpetas `pruebas/` y `reportes/` están
preparadas para recibir el código y la evidencia de las siguientes iteraciones.
