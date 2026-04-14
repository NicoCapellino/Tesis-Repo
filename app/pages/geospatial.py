"""
Geospatial Analysis Page.

Visualizations:
- Interactive heatmap of crime density
- Crime locations with police station overlay
- Borough-level choropleth (density)
"""

from __future__ import annotations

import folium
import polars as pl
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from app.components.filters import get_filtered_data, get_police_stations
from config.settings import CITY_CONFIGS, DEFAULT_CITY

st.header("Análisis Geoespacial")

df = get_filtered_data()
police_df = get_police_stations()

center = CITY_CONFIGS[DEFAULT_CITY].default_center

# ---------------------------------------------------------------------------
# 1. Crime Heatmap
# ---------------------------------------------------------------------------
st.subheader("Mapa de calor de densidad de crímenes")

# Sample for performance if dataset is very large
MAX_HEATMAP_POINTS = 50_000
geo_df = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())

if len(geo_df) > MAX_HEATMAP_POINTS:
    st.caption(f"Mostrando muestra de {MAX_HEATMAP_POINTS:,} de {len(geo_df):,} registros para rendimiento.")
    geo_df = geo_df.sample(n=MAX_HEATMAP_POINTS, seed=42)

heat_data = geo_df.select("latitude", "longitude").to_numpy().tolist()

m = folium.Map(location=list(center), zoom_start=11, tiles="CartoDB positron")
HeatMap(heat_data, radius=8, blur=10, max_zoom=13).add_to(m)

# Overlay police stations if available
if police_df is not None and not police_df.is_empty():
    police_group = folium.FeatureGroup(name="Comisarías")
    for row in police_df.iter_rows(named=True):
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color="blue",
            fill=True,
            fill_opacity=0.8,
            popup=row.get("name", "Police Station"),
        ).add_to(police_group)
    police_group.add_to(m)
    folium.LayerControl().add_to(m)

st_folium(m, width=None, height=600, key="geospatial_map")


# ---------------------------------------------------------------------------
# 2. Crime density by borough
# ---------------------------------------------------------------------------
st.subheader("Distribución por borough")

borough_counts = (
    df.filter(pl.col("borough").is_not_null())
    .group_by("borough")
    .len()
    .sort("len", descending=True)
)

import plotly.express as px

fig_borough = px.bar(
    borough_counts.to_pandas(),
    x="borough",
    y="len",
    color="borough",
    labels={"len": "Cantidad", "borough": "Borough"},
    title="Crímenes por borough",
    text="len",
)
fig_borough.update_traces(texttemplate="%{text:,}", textposition="outside")
fig_borough.update_layout(showlegend=False)
st.plotly_chart(fig_borough, width="stretch")
