# Arquitectura del Sistema

## Visión general

El sistema está compuesto por dos componentes independientes que comparten la capa de configuración y los datos procesados:

```
┌─────────────────────────────────────────────────────────┐
│                    NYC Crime Analysis                    │
├──────────────────────────┬──────────────────────────────┤
│     Pipeline ETL (src/)  │    Dashboard (app/)          │
│                          │                              │
│  Extract → Transform →   │   Streamlit multi-página     │
│  Load (Parquet)          │   con análisis interactivos  │
└──────────┬───────────────┴──────────────────────────────┘
           │              ▲
           ▼              │
     data/processed/   data/processed/
     data/reference/   data/reference/
           │
    ┌──────┴───────┐
    │  config/     │  (compartido)
    │  settings.py │
    └──────────────┘
```

---

## Estructura de directorios

```
.
├── src/                          # Pipeline ETL
│   ├── extract/
│   │   ├── nypd_complaints.py    # Extractor Socrata (NYC Open Data)
│   │   └── osm_infrastructure.py # Extractor Overpass (OpenStreetMap)
│   ├── transform/
│   │   ├── complaints.py         # Normalización y limpieza
│   │   └── geospatial.py         # Validación de coordenadas
│   ├── load/
│   │   └── parquet_writer.py     # Escritura en Parquet comprimido
│   ├── utils/
│   │   └── logging.py            # Logging estructurado (structlog)
│   └── pipeline.py               # Orquestador ETL + CLI
│
├── app/                          # Dashboard Streamlit
│   ├── main.py                   # Entrada: navegación + filtros globales
│   ├── components/
│   │   ├── background.py         # Tareas en segundo plano (threading)
│   │   ├── distances.py          # Cálculo Haversine vectorizado
│   │   └── filters.py            # Helpers para filtros y session_state
│   └── pages/
│       ├── overview.py           # Resumen general
│       ├── temporal.py           # Análisis temporal
│       ├── geospatial.py         # Análisis geoespacial
│       ├── demographic.py        # Análisis demográfico
│       ├── comparative.py        # Comparativo por borough/tipo
│       ├── proximity.py          # Proximidad a comisarías y transporte
│       ├── clustering.py         # K-Means geoespacial
│       ├── associations.py       # Reglas de asociación FP-Growth
│       ├── prediction.py         # Clasificación ML (Random Forest / GBT)
│       └── anomalies.py          # Detección de anomalías (Isolation Forest)
│
├── config/
│   └── settings.py               # Configuración central (Pydantic Settings)
│
├── data/                         # Generado por el pipeline (no en git)
│   ├── raw/complaints/           # Parquet crudo por año
│   ├── processed/complaints/     # Parquet normalizado por año
│   └── reference/new_york/       # Comisarías y estaciones de transporte
│
├── tests/
│   ├── test_extract.py
│   └── test_transform.py
│
├── notebooks/                    # Exploración y análisis previos
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

## Pipeline ETL

### Flujo de datos

```
NYC Open Data (Socrata API)          OpenStreetMap (Overpass API)
         │                                      │
         ▼                                      ▼
  NYPDComplaintsExtractor            OSMInfrastructureExtractor
  - Paginación (50k rows/req)        - Police stations
  - Retry con backoff exponencial    - Transport stations
  - Filtro por año (date range)              │
         │                                   │
         ▼                                   ▼
  data/raw/complaints/              data/reference/new_york/
  complaints_2024.parquet           police_stations.parquet
                                    transport_stations.parquet
         │
         ▼
  ComplaintsTransformer
  - Renombrado y tipado de columnas
  - Features temporales (year, month, hour, day_of_week)
  - Limpieza de nulls
         │
         ▼
  GeospatialValidator
  - Filtra coordenadas fuera del bounding box de NYC
         │
         ▼
  data/processed/complaints/
  complaints_2024.parquet  (compresión zstd)
```

### Configuración (PipelineSettings)

Todos los parámetros son sobreescribibles via variables de entorno con prefijo `NYC_PIPELINE_`:

| Parámetro | Default | Descripción |
|---|---|---|
| `start_year` | 2020 | Primer año a extraer |
| `end_year` | 2025 | Último año a extraer |
| `page_size` | 50 000 | Filas por request Socrata |
| `max_retries` | 5 | Reintentos por fallo HTTP |
| `retry_wait_seconds` | 2.0 | Espera base entre reintentos |
| `request_timeout_seconds` | 120.0 | Timeout HTTP |
| `overpass_timeout` | 120 | Timeout Overpass API |

---

## Dashboard

### Arquitectura de estado

```
app/main.py
    │
    ├── load_complaints()        → st.session_state["complaints"]
    ├── load_police_stations()   → st.session_state["police_stations"]
    ├── load_transport_stations()→ st.session_state["transport_stations"]
    │
    ├── Filtros globales (sidebar)
    │   └── df.filter(year, borough, offense_level)
    │       → st.session_state["filtered"]
    │
    └── st.navigation() → página seleccionada
```

Cada página lee `st.session_state["filtered"]` y trabaja sobre el subconjunto ya filtrado. Los filtros globales aplican a todas las páginas simultáneamente.

### Tareas en segundo plano

Los análisis pesados (K-Means, FP-Growth, Random Forest) se ejecutan en un `threading.Thread` separado para no bloquear la UI. El módulo `app/components/background.py` provee:

- `BackgroundTask`: wrapper que ejecuta una función en background y expone progreso y resultado
- `get_task(name)`: recupera o crea una tarea por nombre desde session_state
- `needs_recompute(task, params_hash)`: detecta si los parámetros cambiaron
- `show_progress_or_result(task)`: muestra barra de progreso o resultado según estado

---

## Extensibilidad

### Agregar una nueva ciudad

En `config/settings.py`, agregar una entrada al dict `CITY_CONFIGS`:

```python
CITY_CONFIGS["chicago"] = CityConfig(
    name="chicago",
    display_name="Chicago",
    bbox=(41.63, -87.94, 42.02, -87.52),
    datasets={"historic": SocrataDataset(resource_id="...")},
    default_center=(41.8781, -87.6298),
)
```

### Agregar un nuevo dataset

Agregar una entrada al dict `NYPD_DATASETS` en `config/settings.py`:

```python
NYPD_DATASETS["arrests"] = SocrataDataset(
    resource_id="uip8-fykc",
    description="NYPD Arrest Data",
)
```

---

## Decisiones de diseño

| Decisión | Alternativa considerada | Motivo |
|---|---|---|
| Polars en lugar de Pandas | Pandas | 5-10x más rápido en ~3M filas, uso de memoria ~50% menor |
| Parquet + zstd | CSV | Lectura columnar 10x más rápida, compresión ~80% |
| Pydantic Settings | .env manual | Validación de tipos, documentación integrada, override via env vars |
| scikit-learn en lugar de PySpark MLlib | PySpark | El volumen (~600k filas/año) no justifica overhead de Spark; sklearn corre en segundos |
| Threading para background tasks | asyncio / multiprocessing | Streamlit no es thread-safe para multiprocessing; asyncio no aplica a CPU-bound |
| mlxtend FP-Growth | PySpark FPGrowth | Sin dependencia de JVM; compatible con el stack Polars/scikit-learn del proyecto |
