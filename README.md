# 🎓 AI Presentation Analyzer

> Analizador de presentaciones impulsado por **IA**, dirigido a los docentes de la **Escuela Superior de Cómputo (ESCOM – IPN)**.

![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python&logoColor=white)
![Conda](https://img.shields.io/badge/Conda-environment-44A833?logo=anaconda&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy-003B57?logo=sqlite&logoColor=white)
![Gemini](https://img.shields.io/badge/IA-Google%20Gemini-8E75B2?logo=googlegemini&logoColor=white)
![Ollama](https://img.shields.io/badge/LLM%20local-Ollama-000000?logo=ollama&logoColor=white)
![Status](https://img.shields.io/badge/Estado-En%20desarrollo-orange)

AI Presentation Analyzer es un prototipo de escritorio que evalúa la **calidad pedagógica de presentaciones `.pptx`** mediante un conjunto de métricas objetivas y modelos de lenguaje. Permite al docente analizar cada diapositiva, comparar su contenido contra el temario oficial de la unidad de aprendizaje, recibir recomendaciones de mejora y, durante la exposición en vivo, medir la gestión del tiempo.

> ⚠️ **Nombre provisional:** el proyecto aún no cuenta con un nombre oficial; por ahora se identifica como `ai-presentation-analyzer`.

---

## 📑 Tabla de contenidos

- [¿Qué hace?](#-qué-hace)
- [Métricas de análisis](#-métricas-de-análisis)
- [Arquitectura](#-arquitectura)
- [Tecnologías y dependencias](#-tecnologías-y-dependencias)
- [Instalación](#-instalación)
- [Configuración](#-configuración)
- [Uso](#-uso)
- [Requerimientos funcionales](#-requerimientos-funcionales)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Pruebas](#-pruebas)
- [Estado del proyecto](#-estado-del-proyecto)
- [Notas](#-notas)

---

## ✨ ¿Qué hace?

- **Organiza materiales por unidad de aprendizaje:** agrupa las presentaciones por clase y permite gestionarlas de forma independiente.
- **Carga y almacena presentaciones `.pptx`:** genera una copia controlada en un directorio dedicado a cada unidad de aprendizaje.
- **Extrae contenido relevante:** obtiene número, encabezado y cuerpo de cada diapositiva, omitiendo imágenes, animaciones, elementos decorativos y pies de página.
- **Verifica cobertura del temario:** compara los encabezados con los temas y subtemas oficiales de ESCOM y marca con un indicador visual los temas abordados.
- **Analiza cada diapositiva** con cuatro métricas ponderadas y produce una **valoración global** en escala de 0 a 10.
- **Genera recomendaciones con IA** (Google Gemini) para las diapositivas que no cumplen los criterios, preservando los conceptos originales del docente.
- **Genera preguntas de comprensión y datos de interés** de apoyo opcional para la exposición.
- **Sesión en vivo:** vista del docente con contadores de tiempo y vista limpia de proyección para los estudiantes.
- **Informe de rendimiento:** compara el tiempo real, el estimado por el docente y el recomendado por la IA, e identifica las diapositivas con mayor desviación.
- **Historial de versiones:** conserva el análisis de cada versión para revisar la evolución del material.

---

## 🧠 Métricas de análisis

La valoración global de la presentación se calcula mediante la suma ponderada de cuatro métricas:

| Métrica | Descripción | Ponderación |
|---|---|:---:|
| **Complejidad del contenido (ICD)** | Índice de Complejidad de Diapositiva. Se mide el porcentaje de diapositivas con ICD dentro del rango óptimo (4.0 – 6.0). | **0.30** |
| **Cantidad de palabras** | Conteo del cuerpo (sin encabezado). ≤ 50 palabras = 10 pts; se descuenta 1 pt por cada 15 palabras adicionales, con mínimo de 0. | **0.30** |
| **Estructura de la diapositiva** | Presencia de encabezado detectable + coherencia semántica encabezado–contenido (1 a 10 vía Gemini). | **0.25** |
| **Hilo narrativo** | Coherencia y progresión temática entre diapositivas adyacentes (1 a 10 vía Gemini). | **0.15** |

**Fórmula del ICD:**

$$\mathrm{ICD} = (0.6 \times \mathrm{CF} + 0.4 \times \mathrm{DLN}) \times 10$$

Donde **CF** es el complemento normalizado del índice **Flesch-Szigriszt** y **DLN** es la **densidad léxica normalizada**.

---

## 🏗 Arquitectura

El prototipo sigue una **arquitectura en capas**, lo que favorece la testabilidad independiente, la sustitución del modelo de IA sin reescribir la lógica y el desarrollo simultáneo del equipo.

| Capa | Ubicación | Responsabilidad |
|---|---|---|
| **Presentación** | `app/presentation` | Interfaz gráfica: vistas (carga, análisis, navegación) y widgets. |
| **Lógica de negocio** | `app/core/controller` · `app/core/logic` | Coordina el flujo entre interfaz y datos; concentra los algoritmos de métricas (complejidad, conteo, densidad léxica, hilo narrativo, estructura). |
| **Infraestructura / IA** | `app/infrastructure` | Integración con Gemini y Ollama mediante una *factory* de proveedores LLM. |
| **Datos** | `app/data` | Persistencia con SQLite, repositorio de presentaciones y consultas locales. |

El modelo relacional se organiza en torno a dos ejes: el **catálogo institucional** (unidades de aprendizaje, unidades temáticas, temas y subtemas) y el **eje operativo** (presentaciones, versiones y resultados de análisis).

---

## 🛠 Tecnologías y dependencias

| Componente | Uso |
|---|---|
| **Python 3.10** | Lenguaje base |
| **SQLAlchemy + aiosqlite** | ORM y persistencia sobre SQLite |
| **Google Gemini** (`google-generativeai`, `google-genai`) | Recomendaciones, coherencia semántica e hilo narrativo |
| **Ollama** | Modelos de lenguaje locales (servicios de coherencia, narrativa, reestructuración) |
| **python-pptx / aspose-slides** | Lectura y procesamiento de archivos `.pptx` |
| **PyMuPDF / pypdf** | Manejo de PDF (temarios y miniaturas) |
| **sentence-transformers / transformers / torch** | Embeddings y similitud semántica |
| **scikit-learn, numpy, scipy, pandas** | Cálculo numérico y análisis de datos |
| **textstat / pyphen / nltk** | Legibilidad (Flesch-Szigriszt) y densidad léxica |
| **CustomTkinter** | Interfaz gráfica de escritorio |
| **llama-index** | Indexación y recuperación de contexto |

> Entorno completo en [`environment.yml`](environment.yml) y [`requirements.txt`](requirements.txt).

---

## 📦 Instalación

### Opción A — Conda (recomendada)

```bash
git clone https://github.com/tuusuario/ai-presentation-analyzer.git
cd ai-presentation-analyzer

conda env create -f environment.yml
conda activate ai-presentation-analyzer
```

### Opción B — venv + pip

```bash
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Requisito adicional: Ollama

Para las funciones de IA local, instala [Ollama](https://ollama.com) y descarga el modelo correspondiente:

```bash
ollama pull <modelo>
```

---

## ⚙️ Configuración

Crea un archivo `.env` en la raíz del proyecto con tus credenciales:

```env
GEMINI_API_KEY=tu_api_key_de_gemini
# Otras variables de configuración del entorno
```

Inicialización de datos:

```bash
# Cargar los temarios oficiales en la base de datos
python seed_temarios.py

# Migración de esquema (si aplica)
python migrate_add_ruta_pdf.py
```

> Los temarios y presentaciones se almacenan en `storage/` (`storage/temarios`, `storage/presentaciones`, `storage/DB`).

---

## 🚀 Uso

Ejecutar la aplicación de escritorio:

```bash
python main.py
```

Flujo básico:

1. Selecciona la **unidad de aprendizaje** (obligatorio antes de cargar).
2. Carga una presentación **`.pptx`** (máx. 30 MB, sin nombres duplicados en la unidad).
3. Ejecuta el **análisis**: el prototipo aplica las cuatro métricas y muestra resultados por diapositiva.
4. Consulta **recomendaciones**, **cobertura del temario** y, opcionalmente, inicia una **sesión en vivo**.
5. Al finalizar la exposición, revisa el **informe de rendimiento** y el **historial de versiones**.

---

## 📋 Requerimientos funcionales

| ID | Nombre | Resumen |
|---|---|---|
| **RF-01** | Selección de unidad de aprendizaje | Selección obligatoria antes de cargar. |
| RF-01.1 | Carga de presentación | Permite cargar archivos `.pptx`. |
| RF-01.2 | Almacenamiento | Copia el archivo en el directorio de su unidad. |
| RF-01.3 | Organización por unidad | Agrupa las presentaciones por clase. |
| RF-01.4 | Visualización del temario | Muestra temas y subtemas oficiales. |
| RF-01.5 | Extracción de contenido | Número, encabezado y cuerpo de cada diapositiva. |
| RF-01.6 | Correspondencia con el temario | Marca los temas cubiertos por la presentación. |
| RF-01.7 | Eliminación de presentación | Borrado permanente con sus datos asociados. |
| RF-01.8 | Eliminación por unidad | Borrado en cascada con confirmación explícita. |
| **RF-02** | Análisis de presentación | Evalúa cada diapositiva con las métricas definidas. |
| RF-02.1 | Complejidad del contenido (ICD) | Métrica ponderada 0.30. |
| RF-02.2 | Cantidad de palabras | Métrica ponderada 0.30. |
| RF-02.3 | Estructura de la diapositiva | Métrica ponderada 0.25. |
| RF-02.3.1 | Presencia de encabezado | Detección y sugerencia vía Gemini. |
| RF-02.3.2 | Coherencia semántica encabezado–contenido | Calificación 1–10 vía Gemini. |
| RF-02.4 | Hilo narrativo | Métrica ponderada 0.15. |
| RF-02.5 | Valoración global | Suma ponderada en escala 0–10. |
| RF-02.6 | Generación de recomendaciones | Sugerencias específicas por diapositiva. |
| RF-02.7 | Preguntas y datos de interés | Apoyo opcional para la exposición. |
| **RF-03** | Sesión en vivo *(en desarrollo)* | Proyección desde el prototipo. |
| RF-03.1–03.5 | Tiempos, vistas docente/estudiante, modo estático | — |
| **RF-04** | Informe de rendimiento *(en desarrollo)* | Comparativa y desviaciones de tiempo. |
| **RF-05** | Historial de presentaciones *(en desarrollo)* | Resultados y reportes por versión. |

---

## 🗂 Estructura del proyecto

```text
.
├── main.py                     # Punto de entrada de la aplicación
├── modelos.py                  # Modelos de datos / ORM
├── seed_temarios.py            # Carga inicial de temarios
├── migrate_add_ruta_pdf.py     # Script de migración de esquema
├── environment.yml             # Entorno Conda
├── requirements.txt            # Dependencias pip
│
├── app/
│   ├── core/
│   │   ├── controller/         # analyzer, presentation, subject controllers
│   │   └── logic/              # Validación, hashing, clasificación de slides
│   │       ├── metrics/        # ICD, word_count, lexical_density, readability,
│   │       │                   #   narrative_thread, header_structure, ...
│   │       ├── parameters/     # syllabus_coverage (cobertura del temario)
│   │       └── utils/          # Utilidades de texto
│   │
│   ├── data/                   # database_manager, persistence, repositorios, queries
│   │
│   ├── infrastructure/
│   │   ├── ai/                 # Proveedor LLM y prompts
│   │   ├── gemini/             # Cliente de Google Gemini
│   │   └── ollama/             # Servicios locales (coherencia, narrativa, ...)
│   │
│   └── presentation/
│       ├── views/              # main_gui, analysis_gui, history_gui, navigator
│       ├── widgets/            # sidebar, topbar, paneles, diálogos
│       └── utils/              # thread_manager
│
├── storage/
│   ├── DB/                     # Base de datos SQLite
│   ├── presentaciones/         # Presentaciones por unidad de aprendizaje
│   └── temarios/               # Temarios oficiales (PDF / JSON)
│
└── tests/                      # Pruebas unitarias e integración
```

---

## 🧪 Pruebas

```bash
python -m unittest discover tests/
```

---

## 🚧 Estado del proyecto

El desarrollo sigue una metodología de **prototipado evolutivo**.

- ✅ **Implementado:** desde `RF-01` hasta `RF-02.7` (carga, organización, extracción, cobertura del temario, análisis con las cuatro métricas, recomendaciones y generación de preguntas).
- 🔄 **En desarrollo:** `RF-03` en adelante (sesión en vivo, informe de rendimiento e historial de presentaciones).

---

## 📝 Notas

- El análisis con IA (Gemini) **requiere conexión a internet**; las funciones de Ollama operan de forma local.
- La eliminación de presentaciones y unidades de aprendizaje se realiza **en cascada** y exige **confirmación explícita**.
- Las animaciones y transiciones del archivo original se ignoran: las diapositivas se procesan y muestran de forma **estática**.

---

<p align="center">
  Desarrollado para los docentes de la <strong>Escuela Superior de Cómputo (ESCOM – IPN)</strong>.
</p>