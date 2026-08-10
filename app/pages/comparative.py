"""
Comparative Analysis Page V2.

This page relates NYPD crimes to authoritative USGS V2 police, fire, and
healthcare facilities.
"""

from __future__ import annotations

import folium
import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from app.components.display import dataframe, plotly_chart
from app.components.distances import haversine_np
from app.components.filters import get_filtered_data, get_usgs_police_v2, get_usgs_v2_layers
from config.settings import CITY_CONFIGS, DEFAULT_CITY


@st.cache_data(ttl=3600, show_spinner=False)
def _distance_matrix(
    c_lats: tuple[float, ...],
    c_lons: tuple[float, ...],
    i_lats: tuple[float, ...],
    i_lons: tuple[float, ...],
    *,
    chunk_size: int = 2_000,
) -> np.ndarray:
    """Full (n_crimes x n_facilities) distance matrix in meters.

    Built in row chunks into a preallocated float32 array. A single full
    float64 broadcast would allocate several (n x m) temporaries at once —
    with large layers (e.g. ~17.5k bus stops) that peaks at tens of GB and
    OOMs. Chunking + float32 bounds memory while keeping the full matrix the
    exposure counts below rely on.
    """
    crimes_lat = np.asarray(c_lats, dtype=np.float64)
    crimes_lon = np.asarray(c_lons, dtype=np.float64)
    infra_lat = np.asarray(i_lats, dtype=np.float64)
    infra_lon = np.asarray(i_lons, dtype=np.float64)

    n = crimes_lat.shape[0]
    m = infra_lat.shape[0]
    out = np.empty((n, m), dtype=np.float32)
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        out[start:end] = haversine_np(
            crimes_lat[start:end, None],
            crimes_lon[start:end, None],
            infra_lat[None, :],
            infra_lon[None, :],
        ).astype(np.float32)
    return out


def _facility_type(row: dict, fallback: str) -> str:
    value = row.get("facility_type")
    return str(value) if value else fallback


def _safe_name(row: dict, idx: int, fallback: str) -> str:
    value = row.get("name")
    return str(value) if value else f"{fallback} {idx + 1}"


st.header("Analisis Comparativo V2 - Crimenes vs. USGS")
st.caption("V2 usa exclusivamente capas USGS: policia, bomberos y salud.")

df = get_filtered_data()
usgs_layers = get_usgs_v2_layers()
usgs_police = get_usgs_police_v2()
center = CITY_CONFIGS[DEFAULT_CITY].default_center

if not usgs_layers:
    st.warning(
        "No hay capas USGS V2 cargadas. Ejecuta el pipeline de referencia USGS "
        "antes de usar este analisis."
    )
    st.stop()

geo_df = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())
if geo_df.is_empty():
    st.warning("No hay crimenes con coordenadas validas para el analisis geoespacial.")
    st.stop()


# ---------------------------------------------------------------------------
# 1. USGS V2 inventory
# ---------------------------------------------------------------------------
st.subheader("Inventario USGS V2")

inventory_rows: list[dict] = []
for label, layer_df in usgs_layers.items():
    inventory_rows.append(
        {
            "capa_v2": label,
            "instalaciones": len(layer_df),
            "boroughs": layer_df["borough"].n_unique() if "borough" in layer_df.columns else None,
            "tipos": (
                layer_df["facility_type"].n_unique()
                if "facility_type" in layer_df.columns
                else None
            ),
        }
    )

inventory_df = pl.DataFrame(inventory_rows)
cols = st.columns(len(inventory_rows))
for col, row in zip(cols, inventory_rows, strict=False):
    with col:
        st.metric(row["capa_v2"], f"{row['instalaciones']:,}")

dataframe(inventory_df.to_pandas(), hide_index=True)

# Solo capas con borough: MTA - Omnibus no lo trae, y sus filas null vuelven
# el eje X numerico (Plotly infiere el tipo del primer trace) dejando el
# grafico vacio, ademas de aplastar la escala con sus ~13.5k paradas.
facility_frames: list[pl.DataFrame] = []
for label, layer_df in usgs_layers.items():
    if "borough" not in layer_df.columns:
        continue
    frame = layer_df.with_columns(pl.lit(label).alias("capa_v2"))
    keep_cols = [c for c in ["capa_v2", "borough", "facility_type"] if c in frame.columns]
    facility_frames.append(frame.select(keep_cols))

if facility_frames:
    by_borough = (
        pl.concat(facility_frames, how="diagonal_relaxed")
        .filter(pl.col("borough").is_not_null())
        .group_by("capa_v2", "borough")
        .len()
        .rename({"len": "instalaciones"})
        .sort("capa_v2", "borough")
    )
    if by_borough.is_empty():
        st.info("Las capas cargadas no tienen borough asignado.")
    else:
        fig_inventory = px.bar(
            by_borough.to_pandas(),
            x="borough",
            y="instalaciones",
            color="capa_v2",
            barmode="group",
            title="USGS V2: instalaciones por borough",
            labels={"borough": "Borough", "instalaciones": "Instalaciones", "capa_v2": "Capa"},
        )
        plotly_chart(fig_inventory)


# ---------------------------------------------------------------------------
# 2. Crime-to-USGS-police ratio by borough
# ---------------------------------------------------------------------------
if usgs_police is not None and not usgs_police.is_empty() and "borough" in usgs_police.columns:
    st.subheader("V2: crimenes por comisaria USGS, por borough")

    crimes_by_borough = (
        geo_df.filter(pl.col("borough").is_not_null())
        .group_by("borough")
        .len()
        .rename({"len": "crimenes"})
    )
    stations_by_borough = (
        usgs_police.filter(pl.col("borough").is_not_null())
        .group_by("borough")
        .len()
        .rename({"len": "comisarias_usgs_v2"})
    )
    ratio_df = (
        crimes_by_borough.join(stations_by_borough, on="borough", how="left")
        .with_columns(
            [
                pl.col("comisarias_usgs_v2").fill_null(0),
                pl.when(pl.col("comisarias_usgs_v2") > 0)
                .then((pl.col("crimenes") / pl.col("comisarias_usgs_v2")).round(0))
                .otherwise(None)
                .cast(pl.Int64)
                .alias("crimenes_por_comisaria_usgs_v2"),
            ]
        )
        .sort("crimenes_por_comisaria_usgs_v2", descending=True, nulls_last=True)
    )

    fig_ratio = px.bar(
        ratio_df.to_pandas(),
        x="borough",
        y="crimenes_por_comisaria_usgs_v2",
        color="borough",
        text="crimenes_por_comisaria_usgs_v2",
        title="V2: crimenes por comisaria USGS",
        labels={
            "borough": "Borough",
            "crimenes_por_comisaria_usgs_v2": "Crimenes por comisaria USGS",
        },
    )
    fig_ratio.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig_ratio.update_layout(showlegend=False)
    plotly_chart(fig_ratio)
    dataframe(ratio_df.to_pandas(), hide_index=True)


# ---------------------------------------------------------------------------
# 3. Facility exposure mining
# ---------------------------------------------------------------------------
st.subheader("V2: exposicion de crimenes alrededor de instalaciones USGS")

radius_m = st.slider(
    "Radio de analisis V2 (metros)",
    min_value=100,
    max_value=2500,
    value=500,
    step=100,
)

SAMPLE = 15_000
sample = geo_df.sample(n=min(SAMPLE, len(geo_df)), seed=42)
sample_lats = tuple(sample["latitude"].to_list())
sample_lons = tuple(sample["longitude"].to_list())
offense_values = np.array(sample["offense_description"].fill_null("SIN_TIPO").to_list())

exposure_rows: list[dict] = []
matrices: dict[str, np.ndarray] = {}
for label, layer_df in usgs_layers.items():
    matrix = _distance_matrix(
        sample_lats,
        sample_lons,
        tuple(layer_df["lat"].to_list()),
        tuple(layer_df["lon"].to_list()),
    )
    matrices[label] = matrix
    counts = (matrix <= radius_m).sum(axis=0)

    for idx, row in enumerate(layer_df.to_dicts()):
        exposure_rows.append(
            {
                "capa_v2": label,
                "facility_index": idx,
                "name": _safe_name(row, idx, label),
                "facility_type": _facility_type(row, label),
                "borough": row.get("borough"),
                "crimenes_en_radio": int(counts[idx]),
            }
        )

exposure_df = pl.DataFrame(exposure_rows)
summary_df = (
    exposure_df.group_by("capa_v2")
    .agg(
        [
            pl.len().alias("instalaciones"),
            pl.col("crimenes_en_radio").mean().round(1).alias("media_crimenes_radio"),
            pl.col("crimenes_en_radio").median().alias("mediana_crimenes_radio"),
            pl.col("crimenes_en_radio").max().alias("max_crimenes_radio"),
        ]
    )
    .sort("media_crimenes_radio", descending=True)
)
dataframe(summary_df.to_pandas(), hide_index=True)

top_exposure = exposure_df.sort("crimenes_en_radio", descending=True).head(20)

dominant_rows: list[dict] = []
for row in top_exposure.to_dicts():
    matrix = matrices[row["capa_v2"]]
    mask = matrix[:, row["facility_index"]] <= radius_m
    near_offenses = offense_values[mask]
    if len(near_offenses) == 0:
        dominant = "N/A"
    else:
        values, counts = np.unique(near_offenses, return_counts=True)
        dominant = str(values[int(np.argmax(counts))])
    dominant_rows.append({**row, "tipo_crimen_dominante": dominant})

top_exposure_display = pl.DataFrame(dominant_rows)
fig_top = px.bar(
    top_exposure_display.to_pandas(),
    y="name",
    x="crimenes_en_radio",
    color="capa_v2",
    orientation="h",
    hover_data=["facility_type", "borough", "tipo_crimen_dominante"],
    title=f"V2: top 20 instalaciones USGS con mas crimenes en {radius_m}m",
    labels={"name": "Instalacion", "crimenes_en_radio": "Crimenes en radio"},
)
fig_top.update_layout(yaxis=dict(autorange="reversed"))
plotly_chart(fig_top)
dataframe(top_exposure_display.drop("facility_index").to_pandas(), hide_index=True)


# ---------------------------------------------------------------------------
# 4. Nearest USGS layer per crime
# ---------------------------------------------------------------------------
st.subheader("V2: capa USGS mas cercana a cada crimen")

nearest_rows: list[dict] = []
for label, matrix in matrices.items():
    nearest_rows.append(
        {
            "capa_v2": label,
            "dist_m": matrix.min(axis=1),
        }
    )

nearest_distances = np.vstack([row["dist_m"] for row in nearest_rows])
nearest_idx = nearest_distances.argmin(axis=0)
nearest_labels = [nearest_rows[i]["capa_v2"] for i in nearest_idx]
nearest_min_km = nearest_distances.min(axis=0) / 1000

nearest_df = pl.DataFrame(
    {
        "capa_v2_mas_cercana": nearest_labels,
        "distancia_min_km": nearest_min_km,
        "offense_level": sample["offense_level"].to_list(),
        "offense_description": sample["offense_description"].to_list(),
    }
)

nearest_counts = (
    nearest_df.group_by("capa_v2_mas_cercana")
    .len()
    .rename({"len": "crimenes"})
    .sort("crimenes", descending=True)
)
fig_nearest = px.bar(
    nearest_counts.to_pandas(),
    x="capa_v2_mas_cercana",
    y="crimenes",
    color="capa_v2_mas_cercana",
    text="crimenes",
    title="V2: infraestructura USGS mas cercana al crimen",
    labels={"capa_v2_mas_cercana": "Capa USGS V2", "crimenes": "Crimenes"},
)
fig_nearest.update_traces(texttemplate="%{text:,}", textposition="outside")
fig_nearest.update_layout(showlegend=False)
plotly_chart(fig_nearest)

severity_nearest = (
    nearest_df.filter(pl.col("offense_level").is_not_null())
    .group_by("capa_v2_mas_cercana", "offense_level")
    .len()
    .rename({"len": "crimenes"})
)
fig_severity = px.bar(
    severity_nearest.to_pandas(),
    x="capa_v2_mas_cercana",
    y="crimenes",
    color="offense_level",
    barmode="group",
    title="V2: nivel de ofensa segun capa USGS mas cercana",
    labels={
        "capa_v2_mas_cercana": "Capa USGS V2",
        "crimenes": "Crimenes",
        "offense_level": "Nivel",
    },
)
plotly_chart(fig_severity)


# ---------------------------------------------------------------------------
# 5. Interactive map
# ---------------------------------------------------------------------------
st.subheader("Mapa V2: crimenes + infraestructura USGS")

MAP_SAMPLE = 15_000
map_df = geo_df.sample(n=min(MAP_SAMPLE, len(geo_df)), seed=42)
heat_data = map_df.select("latitude", "longitude").to_numpy().tolist()

m = folium.Map(location=list(center), zoom_start=11, tiles="CartoDB positron")
heat_group = folium.FeatureGroup(name="Densidad de crimenes", show=True)
HeatMap(heat_data, radius=8, blur=10, max_zoom=13).add_to(heat_group)
heat_group.add_to(m)

layer_styles = {
    "USGS V2 - Policia": ("blue", 6),
    "USGS V2 - Bomberos": ("orange", 5),
    "USGS V2 - Salud": ("red", 5),
    "MTA - Omnibus": ("green", 3),
}
# Cap markers per layer so large layers (e.g. ~17.5k bus stops) don't bloat the
# map and freeze the browser; the exposure/nearest analyses above use the full layer.
MAX_MARKERS_PER_LAYER = 1_500
for label, layer_df in usgs_layers.items():
    color, marker_radius = layer_styles.get(label, ("gray", 4))
    group = folium.FeatureGroup(name=label, show=label == "USGS V2 - Policia")
    render_df = layer_df.drop_nulls(subset=["lat", "lon"])
    if len(render_df) > MAX_MARKERS_PER_LAYER:
        render_df = render_df.sample(n=MAX_MARKERS_PER_LAYER, seed=42)
    for row in render_df.to_dicts():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=marker_radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=(
                f"<b>{row.get('name', 'N/A')}</b><br>"
                f"{label}<br>"
                f"{row.get('facility_type', '')}<br>"
                f"{row.get('address', '')} {row.get('zipcode', '')}"
            ),
        ).add_to(group)
    group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=None, height=650, key="comparative_map_v2")


# ---------------------------------------------------------------------------
# 6. Crime by offense level per borough
# ---------------------------------------------------------------------------
st.subheader("Distribucion de nivel de ofensa por borough")

borough_level = (
    df.filter(pl.col("borough").is_not_null() & pl.col("offense_level").is_not_null())
    .group_by("borough", "offense_level")
    .len()
    .sort("borough", "offense_level")
)

fig_stacked = px.bar(
    borough_level.to_pandas(),
    x="borough",
    y="len",
    color="offense_level",
    barmode="group",
    labels={"len": "Cantidad", "borough": "Borough", "offense_level": "Nivel"},
    title="Crimenes por borough y nivel de ofensa",
)
plotly_chart(fig_stacked)
