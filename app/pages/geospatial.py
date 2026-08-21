"""
Geospatial Analysis Page V2.

Visualizations:
- Interactive heatmap of crime density.
- USGS V2 police, fire, and healthcare facility overlays.
- Borough-level crime density.
"""

from __future__ import annotations

import folium
import plotly.express as px
import polars as pl
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from app.components.display import plotly_chart
from app.components.filters import get_filtered_data, get_usgs_v2_layers
from config.settings import CITY_CONFIGS, DEFAULT_CITY

st.header("Analisis Geoespacial V2 - USGS")

df = get_filtered_data()
usgs_layers = get_usgs_v2_layers()
center = CITY_CONFIGS[DEFAULT_CITY].default_center

st.subheader("Mapa de calor de densidad de crimenes")

MAX_HEATMAP_POINTS = 50_000
geo_df = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())

if len(geo_df) > MAX_HEATMAP_POINTS:
    st.caption(
        f"Mostrando muestra de {MAX_HEATMAP_POINTS:,} de {len(geo_df):,} registros "
        "para rendimiento."
    )
    geo_df = geo_df.sample(n=MAX_HEATMAP_POINTS, seed=42)

heat_data = geo_df.select("latitude", "longitude").to_numpy().tolist()

m = folium.Map(location=list(center), zoom_start=11, tiles="CartoDB positron")
HeatMap(heat_data, radius=8, blur=10, max_zoom=13).add_to(m)

layer_styles = {
    "USGS V2 - Policia": ("blue", 5),
    "USGS V2 - Bomberos": ("orange", 5),
    "USGS V2 - Salud": ("red", 5),
    "MTA - Omnibus": ("green", 3),
}

# Cap markers per layer: large layers (e.g. ~17.5k bus stops) would otherwise
# serialize tens of thousands of markers into the map, bloating it and freezing
# the browser. We sample down for display; analyses still use the full layer.
MAX_MARKERS_PER_LAYER = 1_500

for label, layer_df in usgs_layers.items():
    color, radius = layer_styles.get(label, ("gray", 4))
    layer_group = folium.FeatureGroup(name=label, show=label == "USGS V2 - Policia")
    render_df = layer_df.drop_nulls(subset=["lat", "lon"])
    if len(render_df) > MAX_MARKERS_PER_LAYER:
        render_df = render_df.sample(n=MAX_MARKERS_PER_LAYER, seed=42)
    for row in render_df.to_dicts():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=(
                f"<b>{row.get('name', 'N/A')}</b><br>"
                f"{label}<br>"
                f"{row.get('facility_type', '')}<br>"
                f"{row.get('address', '')} {row.get('zipcode', '')}"
            ),
        ).add_to(layer_group)
    layer_group.add_to(m)

if usgs_layers:
    folium.LayerControl(collapsed=False).add_to(m)

st_folium(m, width=None, height=600, key="geospatial_map_v2")

st.subheader("Distribucion por borough")

borough_counts = (
    df.filter(pl.col("borough").is_not_null())
    .group_by("borough")
    .len()
    .sort("len", descending=True)
)

fig_borough = px.bar(
    borough_counts.to_pandas(),
    x="borough",
    y="len",
    color="borough",
    labels={"len": "Cantidad", "borough": "Borough"},
    title="Crimenes por borough",
    text="len",
)
fig_borough.update_traces(texttemplate="%{text:,}", textposition="outside")
fig_borough.update_layout(showlegend=False)
plotly_chart(fig_borough)
