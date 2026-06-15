# Arquitectura del Sistema V2

El sistema tiene dos componentes principales que comparten configuracion y datos:

```text
NYPD / Socrata             USGS National Map Structures
      |                              |
      v                              v
src/extract/nypd_complaints.py   src/extract/usgs_structures.py
      |                              |
      v                              v
data/raw/complaints/          data/reference/new_york/
      |                       - healthcare.parquet
      |                       - usgs_police.parquet
      |                       - usgs_fire.parquet
      v
src/transform/complaints.py
      |
      v
src/transform/geospatial.py
      |
      v
data/processed/complaints/
      |
      v
app/main.py -> Streamlit dashboard V2
```

## Pipeline

`src/pipeline.py` coordina:

- Descarga NYPD Complaint Data desde Socrata.
- Descarga infraestructura USGS V2:
  - Salud: `healthcare.parquet`
  - Policia: `usgs_police.parquet`
  - Bomberos: `usgs_fire.parquet`
- Normaliza columnas, tipos y nulos.
- Deriva features temporales: `year`, `month`, `day_of_week`, `hour`.
- Filtra coordenadas fuera del bounding box de NYC.
- Escribe parquet comprimido por anio.

## Dashboard

`app/main.py` carga:

- `st.session_state["complaints"]`
- `st.session_state["usgs_healthcare_v2"]`
- `st.session_state["usgs_police_v2"]`
- `st.session_state["usgs_fire_v2"]`

Los filtros globales se aplican antes de ejecutar cada pagina y dejan el subset en
`st.session_state["filtered"]`.

## Analisis V2

- `geospatial.py`: heatmap de crimenes y capas USGS V2.
- `comparative.py`: inventario USGS, crimenes por comisaria, exposicion por instalacion y capa USGS mas cercana.
- `proximity.py`: cerca/lejos contra cualquier capa USGS, matriz multi-capa y tablas cruzadas.
- `associations.py`: FP-Growth con items de proximidad a policia, bomberos y salud USGS.
- `prediction.py`: clasificacion con features temporales, geograficas y distancias USGS V2.

## Configuracion

Los parametros de `PipelineSettings` se sobreescriben con variables `NYC_PIPELINE_`:

| Parametro | Default | Descripcion |
|---|---:|---|
| `start_year` | 2020 | Primer anio a extraer |
| `end_year` | 2025 | Ultimo anio a extraer |
| `page_size` | 50000 | Filas por request Socrata |
| `max_retries` | 5 | Reintentos HTTP |
| `retry_wait_seconds` | 2.0 | Espera base entre reintentos |
| `request_timeout_seconds` | 120.0 | Timeout HTTP |
