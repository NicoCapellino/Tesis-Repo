# Funciones de Data Mining y Análisis

## 1. K-Means Clustering — Zonas de alta criminalidad

**Página:** `app/pages/clustering.py`

### Objetivo
Identificar zonas geoespaciales de concentración delictiva agrupando crímenes por coordenadas (latitud, longitud).

### Algoritmo
**K-Means** (scikit-learn `KMeans`)

### Inputs
| Feature | Descripción |
|---|---|
| `longitude` | Longitud del crimen |
| `latitude` | Latitud del crimen |

### Parámetros ajustables
| Parámetro | Default | Rango | Descripción |
|---|---|---|---|
| `k` | 10 | 3–20 | Número de clusters |

### Proceso
1. Filtrar registros con coordenadas válidas
2. Samplear hasta 50 000 puntos (seed=42)
3. Construir matriz de coordenadas `[lon, lat]`
4. Ajustar `KMeans(n_clusters=k, n_init=10, random_state=42)`
5. Calcular Elbow Chart para k=2..15 (inercia por k)
6. Asignar etiqueta de cluster a cada punto

### Outputs
- Mapa Folium con puntos coloreados por cluster y círculos de radio 1km
- Elbow Chart (plotly) con línea vertical en k seleccionado
- Tabla de centros de cluster con conteo de crímenes
- Métricas: k, crímenes en muestra, cluster más grande

### Interpretación
El método del codo (Elbow Chart) sugiere el k óptimo como el punto de inflexión donde la inercia deja de decrecer significativamente. Los centros de cluster con mayor conteo indican las zonas de mayor densidad delictiva.

---

## 2. Reglas de Asociación — FP-Growth

**Página:** `app/pages/associations.py`

### Objetivo
Descubrir patrones frecuentes entre tipo de delito y proximidad a infraestructura policial y de transporte.

### Algoritmo
**FP-Growth** (mlxtend `fpgrowth` + `association_rules`)

### Items (transacciones)
Cada crimen se convierte en una transacción con hasta 3 items:

| Item | Valores posibles | Descripción |
|---|---|---|
| `TIPO=<offense>` | ej. `TIPO=ROBBERY` | Tipo de delito (top 15 más frecuentes) |
| Proximidad policía | `CERCA_POLICIA` / `LEJOS_POLICIA` | Distancia < umbral a comisaría más cercana |
| Proximidad transporte | `CERCA_TRANSPORTE` / `LEJOS_TRANSPORTE` | Distancia < umbral a estación más cercana |

### Parámetros ajustables
| Parámetro | Default | Rango | Descripción |
|---|---|---|---|
| Soporte mínimo | 0.01 | 0.005–0.10 | Fracción mínima de transacciones |
| Confianza mínima | 0.70 | 0.50–1.00 | P(consecuente \| antecedente) |
| Umbral CERCA/LEJOS | 0.5 km | 0.1–2.0 km | Distancia para clasificar proximidad |

### Proceso
1. Samplear hasta 10 000 crímenes con coordenadas válidas
2. Limitar a los 15 tipos de delito más frecuentes
3. Calcular distancias Haversine vectorizadas a todas las comisarías → tomar mínimo
4. Calcular distancias Haversine vectorizadas a todas las estaciones de transporte → tomar mínimo
5. Clasificar cada distancia en `CERCA` / `LEJOS` según umbral
6. Construir matriz one-hot booleana (transacciones × items)
7. Ejecutar `fpgrowth(min_support=...)` → itemsets frecuentes
8. Ejecutar `association_rules(metric="confidence", min_threshold=...)` → reglas

### Outputs
- Tabla de itemsets frecuentes (top 30 por soporte)
- Tabla de reglas con soporte, confianza y lift (filas con lift > 1.5 en amarillo)
- Scatter plot soporte vs. confianza (tamaño = lift)
- KPIs: reglas encontradas, reglas con lift > 1.5, confianza máxima

### Métricas
| Métrica | Descripción |
|---|---|
| **Soporte** | Frecuencia del itemset: `P(A ∩ B)` |
| **Confianza** | Probabilidad condicional: `P(B \| A) = P(A ∩ B) / P(A)` |
| **Lift** | Independencia relativa: `P(B \| A) / P(B)`. Lift > 1 = asociación positiva |

### Interpretación
Una regla `[TIPO=ROBBERY] → [LEJOS_POLICIA]` con confianza=0.85 y lift=1.6 indica que los robos ocurren lejos de comisarías el 85% de las veces, con una frecuencia 60% mayor a la esperada por azar.

---

## 3. Predicción — Clasificación del Nivel de Ofensa

**Página:** `app/pages/prediction.py`

### Objetivo
Clasificar crímenes en **FELONY**, **MISDEMEANOR** o **VIOLATION** usando features temporales, geoespaciales y de infraestructura. Evaluar si la proximidad a infraestructura tiene poder predictivo.

### Algoritmos
- **Random Forest** (`sklearn.ensemble.RandomForestClassifier`)
- **Gradient Boosting** (`sklearn.ensemble.GradientBoostingClassifier`)

### Features

#### Temporales (codificación cíclica sin/cos)
| Feature | Período | Justificación |
|---|---|---|
| `hour_sin`, `hour_cos` | 24 h | Las 23h y las 0h son temporalmente cercanas |
| `dow_sin`, `dow_cos` | 7 días | El domingo (7) es cercano al lunes (1) |
| `month_sin`, `month_cos` | 12 meses | Diciembre es cercano a enero |

#### Binarias e interacciones
| Feature | Descripción |
|---|---|
| `is_night` | 1 si hora entre 22h y 6h |
| `is_weekend` | 1 si día de semana en {6, 7} |
| `night_weekend` | Interacción: `is_night × is_weekend` |

#### Geoespaciales e infraestructura
| Feature | Descripción |
|---|---|
| `dist_police_km` | Distancia a comisaría más cercana (km) |
| `log_dist_police` | `log1p(dist_police_km)` — reduce asimetría |
| `dist_transport_km` | Distancia a estación de transporte más cercana (km) |
| `log_dist_transport` | `log1p(dist_transport_km)` |
| `dist_ratio` | `dist_police_km / (dist_transport_km + 0.01)` |

#### Categóricas (one-hot)
| Feature | Descripción |
|---|---|
| `borough_*` | One-hot del borough (5 categorías) |
| `premise_*` | One-hot del tipo de premisa (top 10 + OTHER) |

### Parámetros ajustables
| Parámetro | Default | Rango |
|---|---|---|
| `n_estimators` | 150 | 50–300 |
| `max_depth` | 12 | 3–20 |
| `test_size` | 0.25 | 0.15–0.40 |
| Modelo principal | Random Forest | RF / Gradient Boosting |

### Proceso
1. Samplear hasta 30 000 registros con features requeridas
2. Calcular distancias a comisarías y transporte (`add_distance_column`)
3. Aplicar `StandardScaler` sobre todas las features
4. Validación cruzada estratificada: `StratifiedKFold(n_splits=5)` con `cross_val_score`
5. Split holdout: `train_test_split(test_size=..., stratify=y)`
6. Entrenar modelo principal y secundario (RF y GBT)
7. Evaluar con accuracy, confusion matrix y classification report

### Outputs
- Comparación de accuracy y CV score (5-fold) entre RF y GBT
- Gráfico de barras de accuracy por fold para ambos modelos
- Matriz de confusión (heatmap interactivo)
- Classification report por clase (precision, recall, F1)
- Importancia de features (top 15, gráfico horizontal)
- Tabla de feature engineering con justificación de cada feature
- Interpretación automática del ranking de `dist_police_km` y `dist_transport_km`

### Interpretación
Si `dist_police_km` aparece entre las features más importantes, confirma la hipótesis central de la tesis: la proximidad a infraestructura policial es un predictor relevante de la gravedad del delito.

---

## 4. Detección de Anomalías — Isolation Forest

**Página:** `app/pages/anomalies.py`

### Objetivo
Identificar días con actividad criminal inusualmente alta o baja respecto al patrón histórico.

### Algoritmo
**Isolation Forest** (`sklearn.ensemble.IsolationForest`)

### Features
| Feature | Descripción |
|---|---|
| `crime_count` | Cantidad de crímenes en el período |
| `day_of_week` | Día de la semana (1–7) |
| `month` | Mes (1–12) |

### Parámetros ajustables
| Parámetro | Default | Rango | Descripción |
|---|---|---|---|
| `contamination` | 0.05 | 0.01–0.15 | Proporción esperada de anomalías |
| Granularidad | Por día (ciudad) | Ciudad / Por borough | Nivel de agregación |

### Proceso
1. Agregar conteo de crímenes por fecha (y opcionalmente por borough)
2. Construir feature matrix con `crime_count`, `day_of_week`, `month`
3. Ajustar `IsolationForest(contamination=..., n_jobs=-1, random_state=42)`
4. Asignar etiqueta: `-1` = anomalía, `1` = normal
5. Calcular `decision_function` → anomaly score (más negativo = más anómalo)

### Outputs
- Timeline interactivo con puntos normales (azul) y anomalías (rojo ×)
- Tabla top 20 anomalías ordenadas por score
- Distribución de anomalías por borough (si granularidad = borough)
- Histograma de anomaly scores con separación normal/anomalía
- KPIs: períodos totales, anomalías detectadas, % anomalías, media crímenes en anomalías

### Interpretación
Los días con score más negativo representan outliers más extremos. Valores de `crime_count` muy altos pueden indicar eventos masivos (protestas, días festivos), mientras que valores muy bajos pueden indicar feriados o cambios operativos.

---

## 5. Análisis de Proximidad

**Página:** `app/pages/proximity.py`

### Objetivo
Comparar distribuciones de crímenes entre zonas cercanas y lejanas a comisarías de policía, usando el umbral de distancia como variable de análisis.

### Método
Clasificación binaria `CERCA` / `LEJOS` basada en distancia Haversine al punto de infraestructura más cercano.

### Cálculo de distancias
La función `haversine_np` en `app/components/distances.py` implementa la fórmula de Haversine vectorizada con NumPy:

```
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlon/2)
d = 2R × arcsin(√a)     donde R = 6 371 000 m
```

Para cada crimen se calcula la distancia a todas las comisarías/estaciones y se toma el mínimo.

### Parámetros ajustables
| Parámetro | Default | Rango |
|---|---|---|
| Umbral de distancia | 0.5 km | 0.1–3.0 km |

### Visualizaciones
- Boxplot: distribución horaria de crímenes CERCA vs. LEJOS de comisarías
- Boxplot: distancia a transporte comparada entre grupos CERCA/LEJOS
- Boxplot: distancia a comisaría por tipo de crimen (top 10)
- Tabla de estadísticas descriptivas de distancias (media, mediana, p25, p75)
- Tabla por tipo de crimen: distancia media y % de crímenes CERCA
- Tabla cruzada: bins de proximidad policía × transporte

---

## Consideraciones generales

### Muestreo
Los algoritmos pesados trabajan sobre muestras para garantizar interactividad:

| Análisis | Muestra máxima |
|---|---|
| K-Means (coordenadas) | 50 000 |
| FP-Growth (transacciones) | 10 000 |
| Random Forest / GBT | 30 000 |
| Proximity boxplots | 20 000 |

Todos los samples usan `seed=42` para reproducibilidad.

### Ejecución en background
Los análisis de K-Means, FP-Growth e Isolation Forest se ejecutan en un thread separado para no bloquear la interfaz de Streamlit. El módulo `app/components/background.py` detecta cambios en los parámetros vía hash y solo re-ejecuta cuando es necesario.
