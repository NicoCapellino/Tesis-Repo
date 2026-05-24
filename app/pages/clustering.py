"""
K-Means Clustering Page — Zonas de alta criminalidad.

Aplica K-Means sobre coordenadas (lat, lon) para identificar clusters
geoespaciales de crímenes. El usuario ajusta k con un deslizador y puede
explorar el "Elbow chart" para encontrar el k óptimo.

Replica y mejora el análisis del notebook original (PySpark K-Means k=10)
usando scikit-learn, que es más apropiado para el volumen del dataset.
"""

from __future__ import annotations

import folium
import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st
from folium.plugins import MarkerCluster
from sklearn.cluster import KMeans
from streamlit_folium import st_folium

from app.components.background import (
    BackgroundTask,
    get_task,
    needs_recompute,
    show_progress_or_result,
)
from app.components.display import dataframe, plotly_chart
from app.components.filters import get_filtered_data
from config.settings import CITY_CONFIGS, DEFAULT_CITY

st.header("Clustering K-Means — Zonas de Alta Criminalidad")
st.markdown(
    "K-Means agrupa los crímenes por cercanía geográfica, identificando "
    "automáticamente las zonas de mayor concentración delictiva. "
    "Cambiá **k** para ajustar la granularidad del análisis."
)

df = get_filtered_data()
center = CITY_CONFIGS[DEFAULT_CITY].default_center

# ── Controles ────────────────────────────────────────────────────────────────
col_k, col_sample = st.columns([1, 2])
with col_k:
    k = st.slider("Número de clusters (k)", min_value=3, max_value=20, value=10)
with col_sample:
    st.caption(
        "Cada cluster representa una zona de concentración de crímenes. "
        "El mapa muestra los centros de cada cluster y una muestra de puntos coloreados."
    )

SAMPLE_N = 50_000

# ── Preparar datos ───────────────────────────────────────────────────────────
geo_df = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())
if len(geo_df) > SAMPLE_N:
    geo_df = geo_df.sample(n=SAMPLE_N, seed=42)

coords = geo_df.select("longitude", "latitude").to_numpy()  # same order as notebook

if len(coords) < k:
    st.warning(f"No hay suficientes datos ({len(coords)} registros) para {k} clusters.")
    st.stop()


def _fit_kmeans_bg(
    task: BackgroundTask,
    data: np.ndarray,
    n_clusters: int,
    k_max: int,
) -> dict:
    """Fit K-Means + elbow data in background thread. No Streamlit API."""
    task.update(0.10, f"Paso 1/2: Entrenando K-Means con k={n_clusters}...")
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(data)
    centers = km.cluster_centers_
    inertia = float(km.inertia_)

    task.update(0.40, "Paso 2/2: Calculando Elbow Chart (k=2..15)...")
    elbow_rows = []
    for ki in range(2, k_max + 1):
        km_e = KMeans(n_clusters=ki, random_state=42, n_init=10)
        km_e.fit(data)
        elbow_rows.append({"k": ki, "inercia": float(km_e.inertia_)})
        task.update(0.40 + 0.55 * (ki - 1) / (k_max - 1),
                    f"Elbow Chart: k={ki}/{k_max}...")

    return {
        "labels": labels,
        "centers": centers,
        "inertia": inertia,
        "elbow": elbow_rows,
    }


task = get_task("clustering")
params_hash = str(hash((k, len(coords))))

if needs_recompute(task, params_hash):
    task.start(_fit_kmeans_bg, coords, k, 15)

if not show_progress_or_result(task):
    st.stop()

result = task.result
labels = result["labels"]
centers = result["centers"]
inertia = result["inertia"]
elbow = result["elbow"]

# Add cluster column (centers are [lon, lat] matching coord order)
geo_df = geo_df.with_columns(pl.Series("cluster", labels.tolist()))

# ── Métricas ─────────────────────────────────────────────────────────────────
cluster_counts = (
    geo_df.group_by("cluster")
    .len()
    .sort("len", descending=True)
    .rename({"len": "crimenes"})
)

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Clusters", k)
with c2:
    st.metric("Crímenes en muestra", f"{len(geo_df):,}")
with c3:
    st.metric("Cluster más grande", f"{cluster_counts['crimenes'][0]:,}")

st.markdown("---")

# ── Mapa de clusters ─────────────────────────────────────────────────────────
st.subheader("Mapa de clusters geoespaciales")

# Color palette for clusters (up to 20)
COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]

m = folium.Map(location=list(center), zoom_start=11, tiles="CartoDB positron")

# Sample for map rendering
MAP_SAMPLE = 3_000
map_df = geo_df.sample(n=min(MAP_SAMPLE, len(geo_df)), seed=99)

# Crime points colored by cluster using MarkerCluster for performance
for cluster_id in range(k):
    cluster_points = map_df.filter(pl.col("cluster") == cluster_id)
    if cluster_points.is_empty():
        continue
    color = COLORS[cluster_id % len(COLORS)]
    cluster_group = MarkerCluster(name=f"Cluster {cluster_id}", show=True)
    lats = cluster_points["latitude"].to_list()
    lons = cluster_points["longitude"].to_list()
    for lat, lon in zip(lats, lons):
        folium.CircleMarker(
            location=[lat, lon],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.6,
        ).add_to(cluster_group)
    cluster_group.add_to(m)

# Cluster centers (lon, lat order from KMeans matches coord order)
centers_group = folium.FeatureGroup(name="Centros de cluster", show=True)
for i, center_coord in enumerate(centers):
    lon_c, lat_c = center_coord[0], center_coord[1]
    count = int(cluster_counts.filter(pl.col("cluster") == i)["crimenes"][0])
    folium.CircleMarker(
        location=[lat_c, lon_c],
        radius=14,
        color="black",
        fill=True,
        fill_color=COLORS[i % len(COLORS)],
        fill_opacity=0.9,
        popup=f"<b>Cluster {i}</b><br>{count:,} crímenes",
        tooltip=f"Cluster {i}: {count:,}",
    ).add_to(centers_group)
centers_group.add_to(m)

# Radius circles around cluster centers (zonas de alta criminalidad)
radius_group = folium.FeatureGroup(name="Radio 1km (zonas)", show=True)
for i, center_coord in enumerate(centers):
    lon_c, lat_c = center_coord[0], center_coord[1]
    folium.Circle(
        location=[lat_c, lon_c],
        radius=1000,
        color=COLORS[i % len(COLORS)],
        fill=True,
        fill_color=COLORS[i % len(COLORS)],
        fill_opacity=0.1,
        weight=2,
    ).add_to(radius_group)
radius_group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=None, height=600, key="cluster_map")

st.markdown("---")

# ── Elbow Chart ──────────────────────────────────────────────────────────────
st.subheader("Elbow Chart — ¿Cuál es el k óptimo?")
st.caption(
    "El método del codo muestra cómo disminuye la inercia (suma de distancias al centro "
    "del cluster) al aumentar k. El punto de inflexión sugiere el k óptimo."
)

fig_elbow = px.line(
    elbow,
    x="k",
    y="inercia",
    markers=True,
    labels={"k": "Número de clusters (k)", "inercia": "Inercia"},
    title="Elbow Chart — K-Means sobre crímenes de NYC",
)
fig_elbow.add_vline(
    x=k,
    line_dash="dash",
    line_color="red",
    annotation_text=f"k actual = {k}",
)
plotly_chart(fig_elbow)

st.markdown("---")

# ── Tabla de centros ──────────────────────────────────────────────────────────
st.subheader("Centros de cluster y conteo de crímenes")

centers_df = pl.DataFrame({
    "cluster": list(range(k)),
    "lat_centro": [float(c[1]) for c in centers],
    "lon_centro": [float(c[0]) for c in centers],
}).join(cluster_counts, on="cluster", how="left").sort("crimenes", descending=True)

dataframe(
    centers_df.with_columns(
        pl.col("lat_centro").round(5),
        pl.col("lon_centro").round(5),
    ).to_pandas(),
    hide_index=True,
)
