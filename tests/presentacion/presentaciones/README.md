# Presentaciones de prueba

Carpeta destinada a los archivos `.pptx` que se usarán durante las pruebas de
exposición en vivo.

## Organización por unidad académica

Cada unidad de aprendizaje registrada en `Unidad_de_Aprendizaje` tiene su
propia carpeta, generada a partir de la base de datos
`storage/DB/ai_analyzer.db`:

```
presentaciones/
├── Administración de Servicios en Red/
├── Álgebra Lineal/
├── Algoritmos y estructuras de datos/
├── ...
└── Teoría de la Computación/
```

Cada carpeta conserva un `.gitkeep` para que la estructura se mantenga en el
repositorio. Para regenerarlas después de agregar o renombrar unidades:

```bash
python -m tests.presentacion.pruebas.crear_carpetas_unidades
```

Opciones útiles:

```bash
# Solo las unidades marcadas como activas (activa = 1)
python -m tests.presentacion.pruebas.crear_carpetas_unidades --solo-activas

# Usar otra base de datos
python -m tests.presentacion.pruebas.crear_carpetas_unidades --db ruta/a/otra.db
```

## Predicciones de tiempo

Junto a cada presentación se genera un JSON con el mismo nombre base, por
ejemplo `Sockets.pptx` → `Sockets.json`. Contiene el tiempo estimado por
diapositiva, el total y el marcador `presentada`.

Para regenerar todas las predicciones:

```bash
python -m tests.presentacion.preprocesamiento.generar_predicciones
```

Consulta `../preprocesamiento/README.md` para conocer el modelo y las opciones.

## Convención de nombres

```
<numero>_<tema>_<n_diapositivas>.pptx
```

Ejemplos:

```
01_introduccion_10.pptx
02_caso_practico_25.pptx
03_conferencia_extensa_80.pptx
```

Se recomienda cubrir, como mínimo, estos escenarios:

| Escenario | Diapositivas sugeridas |
|---|---|
| Presentación corta | 3 a 5 |
| Presentación típica de clase | 15 a 25 |
| Presentación extensa | 50 o más |
| Presentación con imágenes/tablas | Variable |

## Nota sobre Git

La regla `*.pptx` del `.gitignore` raíz excluye estos archivos por defecto,
para evitar subir presentaciones reales al repositorio. Los `.json` de
predicción también están cubiertos por la regla `*.json`. Si una presentación o
su predicción deben versionarse como fixture, agrégalos explícitamente:

```bash
git add -f tests/presentacion/presentaciones/01_introduccion_10.pptx
git add -f tests/presentacion/presentaciones/01_introduccion_10.json
```

No se deben versionar presentaciones con información personal o confidencial.
