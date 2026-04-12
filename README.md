<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/streamlit-1.36+-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/polars-1.0+-CD792C?logo=polars&logoColor=white" alt="Polars">
  <img src="https://img.shields.io/badge/scikit--learn-1.4+-F7931E?logo=scikit-learn&logoColor=white" alt="scikit-learn">
</p>

# NYC Crime Analysis Dashboard

**Dashboard interactivo de análisis criminal para la ciudad de Nueva York**, construido como trabajo de tesis de Ingeniería en Sistemas.

El proyecto implementa un pipeline ETL completo que descarga, transforma y analiza datos públicos del NYPD (2020-2025), cruzándolos con datos de infraestructura urbana (comisarías y transporte público) provenientes de OpenStreetMap. Los resultados se visualizan en un dashboard interactivo con 10 secciones que incluyen estadísticas descriptivas, análisis geoespacial, modelos de machine learning y detección de anomalías.

---

## Tabla de Contenidos

- [Requisitos Previos](#requisitos-previos)
- [Instalación y Setup](#instalación-y-setup)
  - [1. Clonar el Repositorio](#1-clonar-el-repositorio)
  - [2. Instalar Docker](#2-instalar-docker)
  - [3. Ejecutar el Pipeline ETL](#3-ejecutar-el-pipeline-etl)
  - [4. Levantar el Dashboard](#4-levantar-el-dashboard)
  - [5. Verificar que Todo Funcione](#5-verificar-que-todo-funcione)
- [Comandos Útiles](#comandos-útiles)
- [Arquitectura del Proyecto](#arquitectura-del-proyecto)
  - [Estructura de Directorios](#estructura-de-directorios)
  - [Flujo de Datos](#flujo-de-datos)
  - [Stack Tecnológico](#stack-tecnológico)
- [Pipeline ETL](#pipeline-etl)
  - [Fase 1: Extracción](#fase-1-extracción)
  - [Fase 2: Transformación](#fase-2-transformación)
  - [Fase 3: Carga](#fase-3-carga)
- [Dashboard: Pestañas y Funcionalidades](#dashboard-pestañas-y-funcionalidades)
  - [Filtros Globales](#filtros-globales)
  - [Estadísticas Descriptivas](#estadísticas-descriptivas)
  - [Análisis Avanzado](#análisis-avanzado)
- [Fuentes de Datos](#fuentes-de-datos)
- [Configuración Avanzada](#configuración-avanzada)
- [Solución de Problemas](#solución-de-problemas)

---

## Requisitos Previos

| Requisito | Versión Mínima | Notas |
|-----------|----------------|-------|
| **Docker** | 20.10+ | Incluye Docker Compose V2 |
| **RAM disponible** | 4 GB mínimo | 8 GB recomendado para el pipeline ETL completo |
| **Disco** | 2 GB libres | Para imágenes Docker + datos procesados |
| **Conexión a internet** | Solo para el pipeline | La descarga de datos requiere acceso a APIs públicas |

> **Nota:** No es necesario instalar Python, Streamlit ni ninguna dependencia de forma local. Todo corre dentro de contenedores Docker.

---

## Instalación y Setup

### 1. Clonar el Repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd Tesis-Repo-main
```

### 2. Instalar Docker

<details>
<summary><b>Windows</b></summary>

1. Descargar [Docker Desktop para Windows](https://docs.docker.com/desktop/install/windows-install/).
2. Ejecutar el instalador y seguir los pasos.
3. **Importante:** Si el sistema solicita activar WSL 2 (Windows Subsystem for Linux), aceptar. Docker Desktop lo necesita para funcionar.
4. Reiniciar el equipo si se solicita.
5. Abrir Docker Desktop y esperar a que el ícono de la barra de tareas indique "Docker is running".
6. Verificar en una terminal (PowerShell o CMD):

```powershell
docker --version
docker compose version
```

> **Nota para Windows:** Si `docker compose` no funciona, probar con `docker-compose` (con guión).

</details>

<details>
<summary><b>macOS</b></summary>

**Opción A: Docker Desktop (recomendado para la mayoría)**

1. Descargar [Docker Desktop para Mac](https://docs.docker.com/desktop/install/mac-install/).
   - **Apple Silicon (M1/M2/M3/M4):** descargar la versión "Apple Silicon".
   - **Intel:** descargar la versión "Intel chip".
2. Abrir el `.dmg`, arrastrar Docker a Aplicaciones.
3. Abrir Docker desde Aplicaciones y esperar a que inicie.

**Opción B: Colima (alternativa ligera, sin interfaz gráfica)**

```bash
brew install docker docker-compose colima
colima start --cpu 4 --memory 8
```

Verificar:

```bash
docker --version
docker compose version
```

</details>

<details>
<summary><b>Linux (Ubuntu/Debian)</b></summary>

```bash
# Instalar Docker Engine
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin

# Permitir ejecutar Docker sin sudo
sudo usermod -aG docker $USER
newgrp docker

# Verificar
docker --version
docker compose version
```

Para otras distribuciones, seguir la [guía oficial de Docker](https://docs.docker.com/engine/install/).

</details>

### 3. Ejecutar el Pipeline ETL

El pipeline descarga los datos del NYPD y de OpenStreetMap, los transforma y los deja listos para el dashboard. **Este paso se ejecuta una sola vez** (o cuando se quieran actualizar los datos).

```bash
docker compose run --rm pipeline
```

Esto puede tardar entre **5 y 20 minutos** dependiendo de la conexión a internet, ya que descarga aproximadamente 3 millones de registros del NYPD y datos de infraestructura de OpenStreetMap.

Al finalizar, debería aparecer un resumen similar a:

```
Pipeline completed — 6 artifacts produced
  complaints_2020.parquet  (11 MB)
  complaints_2021.parquet  (12 MB)
  complaints_2022.parquet  (14 MB)
  complaints_2023.parquet  (15 MB)
  complaints_2024.parquet  (15 MB)
  complaints_2025.parquet  (15 MB)
```

> **Si solo se quieren re-procesar datos ya descargados** (sin volver a descargar):
> ```bash
> docker compose run --rm pipeline python -m src.pipeline --skip-extract
> ```

### 4. Levantar el Dashboard

```bash
docker compose up dashboard
```

Abrir en el navegador: **http://localhost:8501**

Para correr el dashboard en segundo plano (sin ocupar la terminal):

```bash
docker compose up -d dashboard
```

### 5. Verificar que Todo Funcione

1. Abrir **http://localhost:8501** en el navegador.
2. La página de inicio ("Resumen General") debe mostrar:
   - Total de registros: ~3.000.000+
   - Los 5 boroughs de NYC
   - El rango de años (2020-2025)
3. Navegar por las pestañas del menú lateral para verificar que cada sección carga correctamente.

---

## Comandos Útiles

El proyecto incluye un `Makefile` con atajos para las operaciones más comunes:

| Comando | Descripción |
|---------|-------------|
| `make all` | Build + Pipeline ETL + Dashboard (setup completo) |
| `make pipeline` | Ejecutar el pipeline ETL |
| `make transform` | Solo transformar (sin descargar datos nuevos) |
| `make dashboard` | Levantar el dashboard (modo foreground) |
| `make dashboard-bg` | Levantar el dashboard (modo background) |
| `make test` | Ejecutar la suite de tests |
| `make logs` | Ver logs del dashboard en tiempo real |
| `make stop` | Detener todos los contenedores |
| `make clean` | Eliminar contenedores, imágenes y volúmenes |

> **Sin Make instalado:** Los mismos comandos se pueden ejecutar directamente con `docker compose`. Por ejemplo, `make dashboard` equivale a `docker compose up dashboard`.

---

## Arquitectura del Proyecto

### Estructura de Directorios

```
.
├── app/                          # Dashboard (Streamlit)
│   ├── main.py                   #   Punto de entrada, navegación y filtros globales
│   ├── components/               #   Módulos compartidos
│   │   ├── background.py         #     Tareas en segundo plano con progreso
│   │   ├── distances.py          #     Haversine vectorizado (numpy)
│   │   └── filters.py            #     Helpers de session_state y filtros
│   └── pages/                    #   10 páginas del dashboard
│       ├── overview.py           #     Resumen general (KPIs)
│       ├── temporal.py           #     Análisis temporal
│       ├── geospatial.py         #     Mapas de calor y densidad
│       ├── demographic.py        #     Perfil de víctimas y delitos
│       ├── comparative.py        #     Crimen vs. infraestructura
│       ├── proximity.py          #     Boxplots cerca/lejos de comisarías
│       ├── clustering.py         #     K-Means geoespacial
│       ├── associations.py       #     Reglas de asociación (FP-Growth)
│       ├── prediction.py         #     Clasificación ML (RF + GB)
│       └── anomalies.py          #     Detección de anomalías (Isolation Forest)
│
├── src/                          # Pipeline ETL
│   ├── pipeline.py               #   Orquestador principal
│   ├── extract/                  #   Descarga de datos
│   │   ├── nypd_complaints.py    #     API Socrata (NYC Open Data)
│   │   └── osm_infrastructure.py #     API Overpass (OpenStreetMap)
│   ├── transform/                #   Limpieza y transformación
│   │   ├── complaints.py         #     Renombrado, tipado, features derivadas
│   │   └── geospatial.py         #     Validación de coordenadas
│   ├── load/                     #   Escritura a Parquet
│   │   └── parquet_writer.py     #     Compresión zstd, particionado por año
│   └── utils/
│       └── logging.py            #   Logging estructurado (structlog)
│
├── config/
│   └── settings.py               # Configuración centralizada (Pydantic)
│
├── tests/                        # Tests unitarios (pytest)
├── data/                         # Datos (generados por el pipeline, no versionados)
│   ├── raw/                      #   Datos crudos descargados
│   ├── processed/                #   Parquet transformados (leídos por el dashboard)
│   └── reference/                #   Comisarías y estaciones de transporte
│
├── Dockerfile                    # Imagen Docker multi-stage (Python 3.12)
├── docker-compose.yml            # Servicios: pipeline, dashboard, test
├── pyproject.toml                # Dependencias y metadata del proyecto
├── Makefile                      # Atajos de comandos
└── .gitignore
```

### Flujo de Datos

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FUENTES EXTERNAS                             │
│                                                                      │
│  NYC Open Data (Socrata API)          OpenStreetMap (Overpass API)   │
│  ├─ NYPD Complaints Historic          ├─ Comisarías de policía       │
│  └─ NYPD Complaints YTD               └─ Estaciones de transporte   │
└──────────────────┬───────────────────────────────┬───────────────────┘
                   │                               │
                   ▼                               ▼
         ┌─────────────────────────────────────────────────┐
         │              PIPELINE ETL (src/)                 │
         │                                                  │
         │  Extract ──► Transform ──► Load                  │
         │  (descarga)  (limpieza)    (parquet + zstd)      │
         └──────────────────┬──────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │    data/processed/       │
              │    data/reference/       │
              │   (archivos .parquet)    │
              └────────────┬────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────────────┐
         │           DASHBOARD (app/)                       │
         │                                                  │
         │  ┌────────────────┐  ┌────────────────────────┐ │
         │  │ Estadísticas   │  │ Análisis Avanzado      │ │
         │  │ Descriptivas   │  │                        │ │
         │  │                │  │  • Comparativo         │ │
         │  │  • Resumen     │  │  • Proximidad          │ │
         │  │  • Temporal    │  │  • Clustering          │ │
         │  │  • Geoespacial │  │  • Asociaciones        │ │
         │  │  • Demográfico │  │  • Predicción ML       │ │
         │  │                │  │  • Anomalías           │ │
         │  └────────────────┘  └────────────────────────┘ │
         └─────────────────────────────────────────────────┘
                           │
                           ▼
                  http://localhost:8501
```

### Stack Tecnológico

| Capa | Tecnología | Propósito |
|------|------------|-----------|
| **Datos** | Polars + PyArrow | Procesamiento columnar de ~3M filas con bajo consumo de memoria |
| **Almacenamiento** | Parquet (zstd) | Compresión eficiente, lectura selectiva de columnas |
| **ETL** | httpx + tenacity | Descarga asíncrona con reintentos y backoff exponencial |
| **Dashboard** | Streamlit | Interfaz web reactiva sin necesidad de frontend |
| **Visualización** | Plotly + Folium | Gráficos interactivos y mapas con capas |
| **Machine Learning** | scikit-learn + mlxtend | Clasificación, clustering, reglas de asociación |
| **Infraestructura** | Docker Compose | Entorno reproducible en cualquier sistema operativo |
| **Configuración** | Pydantic Settings | Validación de tipos + variables de entorno |
| **Logging** | structlog | Logs estructurados con contexto enriquecido |

---

## Pipeline ETL

El pipeline se ejecuta con `docker compose run --rm pipeline` y consta de tres fases:

### Fase 1: Extracción

**Datos del NYPD** (`src/extract/nypd_complaints.py`):
- Descarga registros de la [API Socrata de NYC Open Data](https://data.cityofnewyork.us/).
- Dos datasets: histórico (2020 en adelante) y year-to-date (año en curso).
- Paginación automática (50.000 registros por request) con reintentos exponenciales.
- Deduplicación por `complaint_id` para evitar registros repetidos entre datasets.
- Particionado por año para procesamiento eficiente.

**Datos de infraestructura** (`src/extract/osm_infrastructure.py`):
- Consulta la API Overpass de OpenStreetMap para obtener:
  - **Comisarías de policía** dentro del bounding box de NYC.
  - **Estaciones de transporte** (metro, tren, paradas de bus).
- Tres mirrors de Overpass con failover automático si uno falla.

### Fase 2: Transformación

**Crímenes** (`src/transform/complaints.py`):
- Renombrado de columnas crípticas del NYPD a nombres descriptivos.
- Casting de tipos (fechas, coordenadas, categorías).
- Derivación de features temporales: `year`, `month`, `day_of_week`, `hour`.
- Limpieza de valores nulos e inconsistentes.

**Validación geoespacial** (`src/transform/geospatial.py`):
- Filtrado de coordenadas fuera del bounding box de NYC.
- Eliminación de registros con latitud/longitud nulas o en (0, 0).

### Fase 3: Carga

- Escritura a archivos Parquet con compresión **zstd**.
- Particionado por año: un archivo por año (2020-2025).
- Datos de referencia (comisarías, transporte) en archivos separados.

---

## Dashboard: Pestañas y Funcionalidades

### Filtros Globales

El sidebar izquierdo contiene tres filtros que afectan a **todas** las pestañas simultáneamente:

| Filtro | Opciones | Efecto |
|--------|----------|--------|
| **Año(s)** | 2020, 2021, 2022, 2023, 2024, 2025 | Filtra por año del crimen |
| **Borough(s)** | Manhattan, Brooklyn, Queens, Bronx, Staten Island | Filtra por distrito |
| **Nivel de ofensa** | Felony, Misdemeanor, Violation | Filtra por gravedad |

---

### Estadísticas Descriptivas

<details>
<summary><b>1. Resumen General</b></summary>

Página de inicio con KPIs principales del dataset filtrado:

- **Total de registros** en el dataset.
- **Cantidad de felonies** (delitos graves).
- **Cantidad de boroughs** representados.
- **Período temporal** cubierto.
- Guía de navegación con descripción de cada sección.

</details>

<details>
<summary><b>2. Temporal</b></summary>

Análisis de patrones temporales en la actividad criminal:

- **Evolución mensual por nivel de ofensa:** Gráfico de líneas que muestra la tendencia mes a mes de felonies, misdemeanors y violations. Permite identificar estacionalidad y tendencias de largo plazo.
- **Heatmap día de semana × hora:** Mapa de calor que revela en qué combinación día/hora ocurren más crímenes. Las celdas más oscuras indican mayor concentración.
- **Comparación año contra año:** Gráfico de barras con el total anual. Útil para evaluar el impacto de políticas públicas o eventos extraordinarios (ej. COVID-19).

</details>

<details>
<summary><b>3. Geoespacial</b></summary>

Visualizaciones en mapa interactivo:

- **Mapa de calor de densidad:** Heatmap sobre mapa base (CartoDB) que muestra dónde se concentran los crímenes. Los focos rojos indican las zonas de mayor densidad.
- **Overlay de comisarías:** Marcadores azules muestran la ubicación de cada comisaría de policía, permitiendo evaluar visualmente la cobertura.
- **Distribución por borough:** Gráfico de barras con el conteo de crímenes por distrito.

> Las capas del mapa se pueden activar/desactivar con el control de layers en la esquina superior derecha.

</details>

<details>
<summary><b>4. Demográfico</b></summary>

Perfil estadístico de víctimas y delitos:

- **Top tipos de delito:** Los N tipos de crimen más frecuentes (N ajustable con slider). Permite identificar rápidamente qué delitos predominan.
- **Perfil de víctimas:** Tres gráficos de torta con la distribución por:
  - Grupo etario (<18, 18-24, 25-44, 45-64, 65+)
  - Sexo (con mapeo de códigos NYPD a etiquetas descriptivas)
  - Raza
- **Tipo de premisa:** Los 15 tipos de lugar más comunes donde ocurren crímenes (calle, residencia, comercio, etc.).

> Los valores atípicos del NYPD (edad -1, sexo "D"=Business) son filtrados o mapeados correctamente.

</details>

---

### Análisis Avanzado

<details>
<summary><b>5. Comparativo</b></summary>

Cruce de datos criminales con infraestructura urbana:

- **Ratio crímenes por comisaría:** Cuántos crímenes hay por cada comisaría en cada borough. Un ratio alto sugiere que la zona necesita más cobertura policial.
- **Distancia a comisaría más cercana:** Histograma con la distribución de distancias (km). Incluye métricas: distancia media, mediana, y porcentaje de crímenes a más de 2 km.
- **Densidad alrededor de estaciones de transporte:** Para cada estación, cuántos crímenes ocurren dentro de un radio configurable (100m a 2km). Muestra las 20 estaciones con más actividad criminal.
- **Mapa combinado:** Todas las capas juntas — heatmap de crímenes + comisarías (azul) + transporte público (verde/naranja/violeta). Las capas se pueden activar/desactivar individualmente.
- **Nivel de ofensa por borough:** Comparación de la proporción de felonies vs. misdemeanors vs. violations en cada distrito.

</details>

<details>
<summary><b>6. Proximidad</b></summary>

Análisis de boxplots: crímenes cerca vs. lejos de comisarías.

**Controles:**
- Slider de umbral de distancia (0.1 km a 3 km) para definir qué se considera "cerca".

**Visualizaciones:**
- **Boxplot 1 — Distribución horaria:** Compara a qué horas ocurren los crímenes cerca vs. lejos de comisarías. Cada punto individual está visible (jitter + transparencia). Si la mediana difiere significativamente, sugiere que la presencia policial disuade crímenes en ciertos horarios.
- **Boxplot 2 — Distancia a transporte:** Los crímenes lejos de comisarías, ¿también están lejos del transporte? Revela zonas de baja cobertura dual.
- **Boxplot 3 — Distancia por tipo de crimen (top 10):** Qué tipos de delito tienden a ocurrir más lejos de las comisarías.
- **KPI combinado:** Porcentaje de crímenes cerca de ambas infraestructuras, solo de policía, solo de transporte, o lejos de ambas.
- **Tabla estadística:** Media, mediana, desviación estándar, Q1, Q3, IQR por grupo.
- **Tabla cruzada:** Bins de distancia a policía × distancia a transporte (4×4).
- **Tabla por tipo de crimen:** Distancia media y porcentaje cerca de cada infraestructura, desglosado por los 20 tipos de delito más frecuentes.

</details>

<details>
<summary><b>7. Clustering K-Means</b></summary>

Identificación automática de zonas de alta criminalidad:

- **Algoritmo:** K-Means sobre coordenadas (latitud, longitud) de los crímenes.
- **Slider de k:** Permite ajustar la cantidad de clusters (3 a 20).
- **Mapa interactivo:** Cada cluster se muestra con un color distinto. Los centros de cluster tienen marcadores grandes con tooltip informativo. Círculos de 1 km de radio muestran la zona de influencia de cada cluster.
- **Elbow Chart:** Gráfico de inercia vs. k (2 a 15) para encontrar el k óptimo. El punto de inflexión indica la cantidad ideal de clusters.
- **Tabla de centros:** Coordenadas exactas y cantidad de crímenes de cada cluster, ordenados por tamaño.

> **Procesamiento en segundo plano:** El cálculo de K-Means + Elbow Chart corre en un hilo separado con barra de progreso. Se puede navegar a otra pestaña mientras se computa.

</details>

<details>
<summary><b>8. Reglas de Asociación (FP-Growth)</b></summary>

Descubrimiento de patrones frecuentes entre tipo de delito y proximidad a infraestructura:

- **Algoritmo:** FP-Growth (via mlxtend), reemplazando la implementación original en PySpark.
- **Ítems por transacción:** Cada crimen genera 2-3 ítems:
  - `TIPO=<descripción del delito>`
  - `CERCA_POLICIA` o `LEJOS_POLICIA`
  - `CERCA_TRANSPORTE` o `LEJOS_TRANSPORTE` (si hay datos disponibles)

**Controles:**
- Soporte mínimo (0.005 a 0.10)
- Confianza mínima (0.5 a 1.0)
- Umbral CERCA/LEJOS (0.1 a 2.0 km)

**Resultados:**
- **Itemsets frecuentes:** Los 30 conjuntos de ítems que aparecen con mayor frecuencia.
- **Reglas de asociación:** Tabla con antecedente, consecuente, soporte, confianza y lift. Las reglas con lift > 1.5 se resaltan en amarillo.
- **KPIs:** Cantidad de reglas, reglas con lift > 1.5, confianza máxima.
- **Scatter plot:** Soporte vs. confianza (tamaño = lift) para las top 50 reglas.

**Ejemplo de interpretación:** Una regla `[TIPO=ROBBERY] -> [LEJOS_POLICIA]` con confianza 0.85 indica que el 85% de los robos ocurren lejos de comisarías.

> **Procesamiento en segundo plano:** El cálculo corre en un hilo separado con barra de progreso en 5 pasos.

</details>

<details>
<summary><b>9. Predicción ML</b></summary>

Clasificación del nivel de ofensa (FELONY / MISDEMEANOR / VIOLATION) con modelos de machine learning:

**Modelos comparados:**
- **Random Forest** (con `class_weight="balanced"`)
- **Gradient Boosting** (con subsampling)

**Features utilizadas (ingeniería de features):**

| Feature | Tipo | Justificación |
|---------|------|---------------|
| `hour_sin`, `hour_cos` | Cíclica | Captura que las 23h y las 0h son cercanas |
| `dow_sin`, `dow_cos` | Cíclica | El domingo es cercano al lunes |
| `month_sin`, `month_cos` | Cíclica | Diciembre es cercano a enero |
| `is_night` | Binaria | Crímenes nocturnos (22h-6h) suelen ser más graves |
| `is_weekend` | Binaria | Patrón delictivo distinto en fines de semana |
| `night_weekend` | Interacción | Efecto combinado noche × fin de semana |
| `dist_police_km` | Continua | Hipótesis central: distancia a comisaría |
| `log_dist_police` | Continua | Reduce asimetría de la distribución |
| `dist_transport_km` | Continua | Proxy de actividad urbana |
| `dist_ratio` | Continua | Cobertura relativa policía/transporte |
| `borough_*` | One-hot | Perfil delictivo propio de cada distrito |
| `premise_*` | One-hot | El lugar del crimen influye en su gravedad |

**Evaluación:**
- **Validación cruzada estratificada (5-fold):** Entrena 5 veces con distintas particiones, manteniendo la proporción de clases. Reporta media y desviación estándar.
- **Holdout test set:** Split configurable (15%-40%).
- **Métricas:** Accuracy, precision, recall, F1 por clase.
- **Visualizaciones:** Gráfico de barras de accuracy por fold, matriz de confusión, ranking de feature importance.

**Controles:**
- Cantidad de árboles (50-300)
- Profundidad máxima (3-20)
- Tamaño del test set (15%-40%)
- Selector de modelo principal (RF o GB)

> **Procesamiento en segundo plano:** Ambos modelos se entrenan en paralelo con barra de progreso en 4 pasos.

</details>

<details>
<summary><b>10. Anomalías (Isolation Forest)</b></summary>

Detección de días con actividad criminal anormalmente alta o baja:

- **Algoritmo:** Isolation Forest sobre features de conteo diario + variables temporales (día de semana, mes).
- **Granularidad:** Por día (toda la ciudad) o por día y borough.
- **Tasa de contaminación:** Configurable (1% a 15%), define qué proporción de datos se consideran anómalos.

**Visualizaciones:**
- **Timeline:** Serie temporal de crímenes diarios. Los días normales se muestran como línea azul, las anomalías como marcadores rojos (X). Línea punteada gris indica la media normal.
- **Tabla de top anomalías:** Las 20 anomalías más extremas con fecha, conteo, borough y score.
- **Distribución por borough:** Qué distritos concentran más anomalías.
- **Histograma de scores:** Distribución del anomaly score. Valores más negativos = más anómalo.

**Ejemplo de interpretación:** Un día con 2.500 crímenes cuando la media es 1.200 aparece como anomalía con score negativo alto. Puede indicar un evento especial, protesta, o cambio en políticas de reporte.

> **Procesamiento en segundo plano:** El entrenamiento corre en un hilo separado con barra de progreso en 3 pasos.

</details>

---

## Fuentes de Datos

| Fuente | Dataset | Registros | Actualización |
|--------|---------|-----------|---------------|
| [NYC Open Data](https://data.cityofnewyork.us/) | NYPD Complaint Data Historic | ~3.000.000+ | Trimestral |
| [NYC Open Data](https://data.cityofnewyork.us/) | NYPD Complaint Data Current (YTD) | Variable | Semanal |
| [OpenStreetMap](https://www.openstreetmap.org/) | Comisarías de policía (NYC) | ~77 | Comunitaria |
| [OpenStreetMap](https://www.openstreetmap.org/) | Estaciones de transporte (NYC) | ~1.000+ | Comunitaria |

Todos los datos son **públicos y de acceso libre**. No se requieren API keys ni autenticación.

---

## Configuración Avanzada

La configuración se maneja mediante **variables de entorno** con el prefijo `NYC_PIPELINE_`. Se pueden definir en un archivo `.env` en la raíz del proyecto o pasarlas directamente al contenedor.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `NYC_PIPELINE_START_YEAR` | `2020` | Primer año a descargar |
| `NYC_PIPELINE_END_YEAR` | `2025` | Último año a descargar |
| `NYC_PIPELINE_PAGE_SIZE` | `50000` | Registros por request a Socrata |
| `NYC_PIPELINE_MAX_RETRIES` | `5` | Reintentos ante fallos HTTP |
| `NYC_PIPELINE_RETRY_WAIT_SECONDS` | `2.0` | Base del backoff exponencial |
| `NYC_PIPELINE_REQUEST_TIMEOUT_SECONDS` | `120` | Timeout por request |
| `NYC_PIPELINE_OVERPASS_TIMEOUT` | `120` | Timeout para consultas OSM |

**Ejemplo:** Descargar solo 2023-2025 con mayor timeout:

```bash
NYC_PIPELINE_START_YEAR=2023 NYC_PIPELINE_REQUEST_TIMEOUT_SECONDS=300 \
  docker compose run --rm pipeline
```

---

## Solución de Problemas

<details>
<summary><b>El dashboard no muestra datos / "Datos procesados no encontrados"</b></summary>

El pipeline ETL no fue ejecutado o falló. Ejecutar:

```bash
docker compose run --rm pipeline
```

Verificar que los archivos Parquet existen:

```bash
docker compose exec dashboard ls data/processed/complaints/
```

</details>

<details>
<summary><b>El contenedor se reinicia (exit code 137 — OOM)</b></summary>

El sistema no tiene suficiente RAM asignada a Docker.

- **Docker Desktop:** Settings > Resources > Memory > Aumentar a 6-8 GB.
- **Colima:** `colima stop && colima start --memory 8`
- **Linux:** Verificar con `free -h` que hay al menos 4 GB disponibles.

</details>

<details>
<summary><b>Error de conexión al descargar datos</b></summary>

El pipeline usa APIs públicas que pueden tener rate limiting o estar temporalmente caídas.

- Reintentar: `docker compose run --rm pipeline`
- Si falla la descarga de OSM, el pipeline usa 3 mirrors con failover automático.
- Si el problema persiste, verificar la conexión a internet y que los sitios `data.cityofnewyork.us` y `overpass-api.de` estén accesibles.

</details>

<details>
<summary><b>Puerto 8501 ocupado</b></summary>

Otro proceso está usando el puerto. Opciones:

```bash
# Ver qué usa el puerto
lsof -i :8501

# O cambiar el puerto en docker-compose.yml
ports:
  - "8502:8501"   # Acceder en http://localhost:8502
```

</details>

<details>
<summary><b>"docker compose" no funciona</b></summary>

En versiones antiguas de Docker, el comando es `docker-compose` (con guión):

```bash
docker-compose run --rm pipeline
docker-compose up dashboard
```

</details>

---

<p align="center">
  <sub>
    Trabajo de tesis — Ingeniería en Sistemas<br>
    Fuente de datos: NYC Open Data (NYPD Complaint Data) + OpenStreetMap<br>
    Desarrollado con Python 3.12, Streamlit, Polars, scikit-learn y Docker
  </sub>
</p>
