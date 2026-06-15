# Librerías Python

## Procesamiento de datos

| Librería | Versión mínima | Uso |
|---|---|---|
| **polars** | 1.0.0 | DataFrame principal para ETL y dashboard. Reemplaza Pandas por su performance en ~3M filas (~5-10x más rápido, ~50% menos memoria). |
| **pyarrow** | 15.0.0 | Backend de serialización para lectura/escritura de archivos Parquet. |
| **numpy** | 1.26.0 | Operaciones vectorizadas en análisis de distancias (Haversine), ingeniería de features (codificación cíclica) y matrices de ML. |

## HTTP y APIs

| Librería | Versión mínima | Uso |
|---|---|---|
| **httpx** | 0.27.0 | Cliente HTTP asíncrono/síncrono para Socrata API y USGS WFS. Soporte nativo para timeouts y redirects. |
| **tenacity** | 8.2.0 | Retry con backoff exponencial para requests fallidos. Decorador `@retry` en `_fetch_page`. |

## Visualización y Dashboard

| Librería | Versión mínima | Uso |
|---|---|---|
| **streamlit** | 1.36.0 | Framework del dashboard multi-página. Maneja estado global, navegación, sidebar y caching. |
| **plotly** | 5.20.0 | Gráficos interactivos: barras, líneas, scatter, mapas de calor (confusion matrix), histogramas, elbow chart. |
| **folium** | 0.16.0 | Mapas interactivos. Usado en clustering (MarkerCluster), geoespacial y capas USGS V2. |
| **streamlit-folium** | 0.20.0 | Integración de mapas Folium dentro de Streamlit via `st_folium`. |
| **pydeck** | 0.9.0 | Mapas de alta performance con WebGL para visualización geoespacial de grandes volúmenes. |

## Machine Learning

| Librería | Versión mínima | Uso |
|---|---|---|
| **scikit-learn** | 1.4.0 | Suite completa de ML. Ver detalle por módulo abajo. |
| **mlxtend** | 0.23.0 | Implementación de FP-Growth y generación de reglas de asociación. Usado en `pages/associations.py`. |

### Módulos de scikit-learn utilizados

| Módulo | Clase/Función | Página |
|---|---|---|
| `sklearn.cluster` | `KMeans` | clustering.py |
| `sklearn.ensemble` | `RandomForestClassifier` | prediction.py |
| `sklearn.ensemble` | `GradientBoostingClassifier` | prediction.py |
| `sklearn.ensemble` | `IsolationForest` | anomalies.py |
| `sklearn.model_selection` | `StratifiedKFold`, `cross_val_score`, `train_test_split` | prediction.py |
| `sklearn.metrics` | `accuracy_score`, `classification_report`, `confusion_matrix` | prediction.py |
| `sklearn.preprocessing` | `LabelEncoder`, `StandardScaler` | prediction.py |

## Logging

| Librería | Versión mínima | Uso |
|---|---|---|
| **structlog** | 24.1.0 | Logging estructurado en formato JSON-like. Cada evento de log incluye campos clave-valor (ej: `year=2024`, `records=574096`). |

## Configuración

| Librería | Versión mínima | Uso |
|---|---|---|
| **pydantic** | 2.7.0 | Validación de tipos y serialización para `CityConfig`, `SocrataDataset`. |
| **pydantic-settings** | 2.2.0 | `BaseSettings` para `PipelineSettings`: carga automática desde variables de entorno con prefijo `NYC_PIPELINE_`. |

## Desarrollo y testing

| Librería | Versión mínima | Uso |
|---|---|---|
| **pytest** | 8.0.0 | Framework de testing. |
| **pytest-asyncio** | 0.23.0 | Soporte para tests asíncronos. |
| **ruff** | 0.4.0 | Linter y formatter (reemplaza flake8 + black + isort). |
| **mypy** | 1.10.0 | Type checking estático. |
