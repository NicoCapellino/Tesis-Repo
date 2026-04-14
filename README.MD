# Tesis - Análisis de Crimen en NYC

Dashboard interactivo y pipeline ETL para análisis de datos de crimen en Nueva York, usando datos abiertos de NYPD y OpenStreetMap.

## Arquitectura

```
src/                        # Pipeline ETL
├── extract/
│   ├── nypd_complaints.py  # Descarga desde NYC Open Data (Socrata API)
│   └── osm_infrastructure.py # Descarga comisarías y transporte desde OSM
├── transform/
│   ├── complaints.py       # Normalización y limpieza
│   └── geospatial.py       # Validación de coordenadas
├── load/
│   └── parquet_writer.py   # Escritura en Parquet comprimido
└── pipeline.py             # Orquestador ETL (CLI)

app/                        # Dashboard Streamlit
├── main.py                 # Entrada, navegación y filtros globales
├── components/             # Filtros, mapas, utilidades
└── pages/                  # Una página por análisis

config/
└── settings.py             # Configuración central (Pydantic Settings)

tests/                      # Tests unitarios
```

## Requisitos

- Python 3.11+
- Docker y Docker Compose (opcional)

## Quick Start

### Con Python local

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# 2. Correr el pipeline (descarga y procesa los datos)
python -m src.pipeline

# 3. Levantar el dashboard
streamlit run app/main.py
```

El dashboard queda disponible en **http://localhost:8501**.

### Con Docker

```bash
# Pipeline completo (descarga + procesa)
docker-compose run --rm pipeline

# Solo re-transformar sin re-descargar
docker-compose run --rm pipeline python -m src.pipeline --skip-extract

# Dashboard
docker-compose up dashboard
```

## Pipeline ETL

El pipeline ejecuta tres fases:

1. **Extract** — Descarga datos de NYPD (Socrata API) y OSM (Overpass API)
2. **Transform** — Normaliza columnas, limpia nulls, valida coordenadas
3. **Load** — Guarda en Parquet comprimido (zstd) particionado por año

```bash
# Opciones de CLI
python -m src.pipeline
python -m src.pipeline --skip-extract          # Saltar descarga, re-transformar
python -m src.pipeline --skip-infrastructure   # Saltar descarga de OSM

# Configuración via variables de entorno
NYC_PIPELINE_START_YEAR=2023 NYC_PIPELINE_END_YEAR=2024 python -m src.pipeline
```

### Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `NYC_PIPELINE_START_YEAR` | `2020` | Primer año a descargar |
| `NYC_PIPELINE_END_YEAR` | `2025` | Último año a descargar |
| `NYC_PIPELINE_PAGE_SIZE` | `50000` | Filas por request (máx Socrata) |
| `NYC_PIPELINE_MAX_RETRIES` | `5` | Reintentos por request fallido |

## Dashboard

Navegación en dos secciones:

**Estadísticas Descriptivas**
- Resumen General
- Temporal
- Geoespacial
- Demográfico

**Análisis Avanzado**
- Comparativo
- Proximidad a comisarías y transporte
- Clustering K-Means
- Reglas de Asociación
- Predicción ML
- Anomalías

Los filtros globales (año, borough, nivel de ofensa) en el sidebar aplican a todas las páginas.

## Tests

```bash
pytest
# o con Docker:
docker-compose run --rm test
```
