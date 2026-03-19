# Tesis - Analisis de Crimen con PySpark y Apache Sedona

## Requisitos

- Docker y Docker Compose
- DVC (`pip install "dvc[gdrive]"`) - para descargar los datasets

## Quick Start

```bash

# 1. Descargar los datos con DVC
dvc pull

# 2. Levantar el entorno
docker compose up -d

# 3. Obtener el token de Jupyter
docker logs sedona-jupyter
```

Buscar en los logs la URL con el token, ej:
```
http://127.0.0.1:8888/lab?token=8a10ad27500f67ed51c81297fc37b8f4809197cbe9e5f4fa
```


## Estructura del Proyecto

```
notebooks/
├── crime.ipynb                    # Data mining sobre datos normalizados de NY
├── data_download.ipynb            # Descarga de datos
├── data_exploration.ipynb         # Exploracion inicial de datos
├── DE2.ipynb                      # Notebook auxiliar
├── crimes_normalized/
│   └── normalize_new_york_crimes.ipynb  # Normalizacion de datos crudos de NY
├── data/
│   └── new_york/
│       ├── crimes/                # CSVs crudos (2020-2025)
│       ├── crimes_normalized/     # Parquet normalizado (generado por normalize)
│       └── police_stations/       # Estaciones de policia
└── Docs/
    └── GUIA_DVC.md                # Guia completa de DVC
```

## Notebooks

### 1. `crimes_normalized/normalize_new_york_crimes.ipynb`
Normaliza los CSVs crudos de NY: renombra columnas, castea tipos, limpia nulls y guarda como parquet particionado por anio.

**Ejecutar primero** si los parquet no existen todavia.

### 2. `crime.ipynb`
Data mining sobre los datos normalizados:
- **FP-Growth**: Reglas de asociacion entre atributos del crimen
- **K-Means**: Clustering espacial de ubicaciones
- **Folium**: Mapa interactivo con clusters

### 3. `data_download.ipynb`
Descarga de datasets desde APIs publicas.

## DVC - Gestion de Datos

Los archivos `.csv` y `.parquet` estan en `.gitignore`. Se gestionan con DVC y se almacenan en Google Drive.

```bash
# Descargar datos
dvc pull

# Subir datos nuevos
dvc add notebooks/data/new_york/crimes_normalized/parquet
dvc push

# Commitear los punteros
git add notebooks/data/new_york/crimes_normalized/parquet.dvc
git commit -m "Actualizar datos normalizados"
git push
```

Ver [GUIA_DVC.md](notebooks/Docs/GUIA_DVC.md) para mas detalles.
