# NYC Crime Analysis Dashboard V2

Dashboard interactivo y pipeline ETL para analizar crimenes de Nueva York
cruzados con infraestructura de referencia.

Capas de infraestructura (NYC):

- `healthcare.parquet` (USGS National Map)
- `usgs_police.parquet` (USGS National Map)
- `usgs_fire.parquet` (USGS National Map)
- `mta_bus_stops.parquet` (MTA Bus Stops, NY State Open Data)

## Requisitos

- Docker 20.10+
- Docker Compose V2 (`docker compose`)
- 4 GB de RAM libres como minimo, 8 GB recomendado
- Internet para descargar datos NYPD y USGS

## Setup Rapido

Desde la raiz del repo:

```powershell
docker compose build
docker compose run --rm pipeline
docker compose up dashboard
```

Luego abrir:

```text
http://localhost:8501
```

Si ya existen datos crudos NYPD y solo se quiere transformar:

```powershell
docker compose run --rm pipeline python -m src.pipeline --skip-extract
```

Si se quiere actualizar solo referencia USGS V2 usando los datos NYPD crudos ya
presentes:

```powershell
docker compose run --rm pipeline python -m src.pipeline --skip-complaints
```

## Estructura

```text
app/                         Dashboard Streamlit
  main.py                    Navegacion, carga de datos y filtros globales
  components/                Helpers compartidos
  pages/                     Paginas de analisis

src/                         Pipeline ETL
  extract/
    nypd_complaints.py       NYPD Complaint Data via Socrata
    usgs_structures.py       USGS V2 healthcare, police, fire
    mta_bus_stops.py         MTA bus stops via Socrata (data.ny.gov)
  transform/
    complaints.py            Limpieza, tipado y features temporales
    geospatial.py            Validacion de coordenadas NYC
  pipeline.py                Orquestador CLI

data/
  raw/complaints/            NYPD crudo por anio
  processed/complaints/      NYPD procesado por anio
  reference/new_york/        Capas USGS V2
```

## Pipeline V2

El pipeline produce:

```text
data/processed/complaints/complaints_2020.parquet
...
data/processed/complaints/complaints_2025.parquet

data/reference/new_york/healthcare.parquet
data/reference/new_york/usgs_police.parquet
data/reference/new_york/usgs_fire.parquet
data/reference/new_york/mta_bus_stops.parquet
```

## Dashboard V2

Paginas principales:

- **Resumen General**: KPIs del dataset filtrado.
- **Temporal**: tendencias mensuales, dia/hora, comparativa anual.
- **Geoespacial V2**: heatmap de crimenes y capas USGS V2.
- **Demografico**: victimas, sospechosos y premisas.
- **Comparativo V2**: inventario USGS, crimenes por comisaria, exposicion por instalacion y capa mas cercana.
- **Proximidad V2**: cerca/lejos contra policia, bomberos o salud USGS, con matriz multi-capa.
- **Clustering K-Means**: zonas de alta criminalidad.
- **Reglas V2**: FP-Growth con proximidad a capas USGS.
- **Prediccion ML V2**: modelos con features de distancia USGS.
- **Anomalias**: Isolation Forest para dias inusuales.

## Comandos

```powershell
docker compose build
docker compose run --rm pipeline
docker compose run --rm pipeline python -m src.pipeline --skip-extract
docker compose run --rm pipeline python -m src.pipeline --skip-complaints
docker compose up dashboard
docker compose run --rm test
docker compose down
```

## Configuracion

Variables con prefijo `NYC_PIPELINE_`:

| Variable | Default | Descripcion |
|---|---:|---|
| `NYC_PIPELINE_PAGE_SIZE` | 50000 | Filas por request Socrata |
| `NYC_PIPELINE_START_YEAR` | 2020 | Primer anio |
| `NYC_PIPELINE_END_YEAR` | 2025 | Ultimo anio |
| `NYC_PIPELINE_MAX_RETRIES` | 5 | Reintentos HTTP |
| `NYC_PIPELINE_REQUEST_TIMEOUT_SECONDS` | 120 | Timeout HTTP |

## Fuentes

- NYC Open Data - NYPD Complaint Data Historic
- NYC Open Data - NYPD Complaint Data Current Year To Date
- USGS National Map Structures WFS
- MTA Bus Stops - NY State Open Data (Socrata `2ucp-7wg5`)
