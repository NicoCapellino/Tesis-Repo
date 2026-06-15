"""
Proximity Analysis Page V2.

All infrastructure distances use USGS V2 layers only: police, fire, and
healthcare.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st

from app.components.display import dataframe, plotly_chart
from app.components.distances import add_distance_column, compute_nearest_distances
from app.components.filters import get_filtered_data, get_usgs_v2_layers
from app.components.utils import slugify as _slug

st.header("Proximidad V2: Crimenes cerca vs. lejos de infraestructura USGS")

df = get_filtered_data()
usgs_layers = get_usgs_v2_layers()

if not usgs_layers:
    st.warning("No hay datos USGS V2 disponibles. Ejecuta el pipeline de referencia USGS primero.")
    st.stop()


@st.cache_data(ttl=3600, show_spinner="Calculando distancias V2...")
def _get_reference_distances(
    filtered_df: pl.DataFrame,
    year_filter: tuple[int, ...],
    borough_filter: tuple[str, ...],
    level_filter: tuple[str, ...],
    ref_lats: tuple[float, ...],
    ref_lons: tuple[float, ...],
    sample_n: int,
) -> pl.DataFrame:
    return add_distance_column(
        filtered_df,
        pl.DataFrame({"lat": list(ref_lats), "lon": list(ref_lons)}),
        col_name="dist_ref_m",
        sample_n=sample_n,
    )


@st.cache_data(ttl=3600, show_spinner="Calculando matriz USGS V2...")
def _distances_for_layers(
    crime_lats: tuple[float, ...],
    crime_lons: tuple[float, ...],
    layers_payload: tuple[tuple[str, tuple[float, ...], tuple[float, ...]], ...],
) -> dict[str, np.ndarray]:
    output: dict[str, np.ndarray] = {}
    for label, lats, lons in layers_payload:
        output[label] = compute_nearest_distances(crime_lats, crime_lons, lats, lons)
    return output


with st.expander("Parametros V2", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_layer = st.selectbox(
            "Infraestructura USGS V2 de referencia",
            options=list(usgs_layers.keys()),
            index=0,
        )
    with col2:
        threshold_km = st.slider(
            "Umbral CERCA/LEJOS (km)",
            min_value=0.1,
            max_value=3.0,
            value=0.5,
            step=0.1,
        )
    with col3:
        sample_n = st.slider(
            "Muestra",
            min_value=5_000,
            max_value=50_000,
            value=20_000,
            step=5_000,
        )

selected_df = usgs_layers[selected_layer]
threshold_m = threshold_km * 1000

sample_df = _get_reference_distances(
    df,
    year_filter=tuple(sorted(df["year"].drop_nulls().unique().to_list())),
    borough_filter=tuple(sorted(df["borough"].drop_nulls().unique().to_list())),
    level_filter=tuple(sorted(df["offense_level"].drop_nulls().unique().to_list())),
    ref_lats=tuple(selected_df["lat"].to_list()),
    ref_lons=tuple(selected_df["lon"].to_list()),
    sample_n=sample_n,
)

if sample_df.is_empty():
    st.warning("No hay crimenes con coordenadas validas para calcular proximidad.")
    st.stop()

cerca_label = f"CERCA (< {threshold_km} km) - {selected_layer}"
lejos_label = f"LEJOS (>= {threshold_km} km) - {selected_layer}"
sample_df = sample_df.with_columns(
    [
        (pl.col("dist_ref_m") / 1000).alias("dist_ref_km"),
        pl.when(pl.col("dist_ref_m") < threshold_m)
        .then(pl.lit(cerca_label))
        .otherwise(pl.lit(lejos_label))
        .alias("grupo_v2"),
    ]
)

cerca_count = int((sample_df["dist_ref_m"] < threshold_m).sum())
lejos_count = len(sample_df) - cerca_count
pct_cerca = cerca_count / len(sample_df) * 100 if len(sample_df) else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total en muestra", f"{len(sample_df):,}")
with col2:
    st.metric(f"CERCA (< {threshold_km} km)", f"{cerca_count:,}")
with col3:
    st.metric(f"LEJOS (>= {threshold_km} km)", f"{lejos_count:,}")
with col4:
    st.metric("% CERCA V2", f"{pct_cerca:.1f}%")


# ---------------------------------------------------------------------------
# 1. Time distribution
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader(f"V2: distribucion horaria cerca/lejos de {selected_layer}")

hour_df = sample_df.filter(pl.col("hour").is_not_null() & pl.col("hour").is_between(0, 23))
if not hour_df.is_empty():
    fig_hour = px.box(
        hour_df.to_pandas(),
        x="grupo_v2",
        y="hour",
        color="grupo_v2",
        points="all",
        category_orders={"grupo_v2": [cerca_label, lejos_label]},
        labels={"hour": "Hora del dia (0-23)", "grupo_v2": "Grupo V2"},
        title=f"V2: hora del crimen segun proximidad a {selected_layer}",
    )
    fig_hour.update_traces(boxmean=True, jitter=0.3, marker=dict(opacity=0.2, size=2))
    fig_hour.update_layout(showlegend=False, yaxis=dict(dtick=1, range=[-0.5, 23.5]))
    plotly_chart(fig_hour)

    hour_stats = (
        hour_df.group_by("grupo_v2")
        .agg(
            [
                pl.len().alias("n"),
                pl.col("hour").mean().round(2).alias("media"),
                pl.col("hour").median().alias("mediana"),
                pl.col("hour").std().round(2).alias("std"),
                pl.col("hour").quantile(0.25).alias("q1"),
                pl.col("hour").quantile(0.75).alias("q3"),
            ]
        )
        .with_columns((pl.col("q3") - pl.col("q1")).round(2).alias("iqr"))
    )
    dataframe(hour_stats.to_pandas(), hide_index=True)
else:
    st.info("No hay datos de hora disponibles.")


# ---------------------------------------------------------------------------
# 2. Distance by offense type
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader(f"V2: distancia a {selected_layer} por tipo de crimen")

crime_dist_df = sample_df.filter(pl.col("offense_description").is_not_null())
top_offenses = (
    crime_dist_df.group_by("offense_description")
    .len()
    .sort("len", descending=True)
    .head(10)["offense_description"]
    .to_list()
)
crime_dist_top = crime_dist_df.filter(pl.col("offense_description").is_in(top_offenses))

if not crime_dist_top.is_empty():
    fig_crime_dist = px.box(
        crime_dist_top.to_pandas(),
        x="offense_description",
        y="dist_ref_km",
        color="offense_description",
        points="outliers",
        labels={"dist_ref_km": "Distancia (km)", "offense_description": "Tipo de crimen"},
        title=f"V2: distancia a {selected_layer} por tipo de crimen",
    )
    fig_crime_dist.update_traces(boxmean=True)
    fig_crime_dist.update_layout(showlegend=False, xaxis_tickangle=-45, height=600)
    plotly_chart(fig_crime_dist)


# ---------------------------------------------------------------------------
# 3. Multi-layer USGS V2 distances
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("V2: matriz multi-capa USGS")

layers_payload = tuple(
    (label, tuple(layer_df["lat"].to_list()), tuple(layer_df["lon"].to_list()))
    for label, layer_df in usgs_layers.items()
)
distance_map = _distances_for_layers(
    tuple(sample_df["latitude"].to_list()),
    tuple(sample_df["longitude"].to_list()),
    layers_payload,
)

multi_df = sample_df
distance_cols: dict[str, str] = {}
for label, distances in distance_map.items():
    col_name = f"dist_{_slug(label)}_m"
    distance_cols[label] = col_name
    multi_df = multi_df.with_columns(pl.Series(col_name, distances))

summary_rows: list[dict] = []
for label, col_name in distance_cols.items():
    distances_km = multi_df[col_name] / 1000
    pct_near = float((multi_df[col_name] < threshold_m).sum()) / len(multi_df) * 100
    summary_rows.append(
        {
            "capa_v2": label,
            "media_km": round(float(distances_km.mean()), 3),
            "mediana_km": round(float(distances_km.median()), 3),
            "p75_km": round(float(distances_km.quantile(0.75)), 3),
            f"%_cerca_{threshold_km}km": round(pct_near, 1),
        }
    )

summary_v2 = pd.DataFrame(summary_rows)
dataframe(summary_v2, hide_index=True)

fig_summary = px.bar(
    summary_v2,
    x="capa_v2",
    y=f"%_cerca_{threshold_km}km",
    color="capa_v2",
    text=f"%_cerca_{threshold_km}km",
    title=f"V2: porcentaje de crimenes cerca de cada capa USGS (< {threshold_km} km)",
    labels={"capa_v2": "Capa USGS V2", f"%_cerca_{threshold_km}km": "% cerca"},
)
fig_summary.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig_summary.update_layout(showlegend=False)
plotly_chart(fig_summary)


# ---------------------------------------------------------------------------
# 4. Crime-type mining across all USGS layers
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("V2: data mining por tipo de crimen y proximidad USGS")

agg_exprs: list[pl.Expr] = [pl.len().alias("total")]
pct_exprs: list[pl.Expr] = []
drop_cols: list[str] = []
for label, col_name in distance_cols.items():
    slug = _slug(label)
    near_col = f"cerca_{slug}"
    total_col = f"_total_{slug}"
    agg_exprs.extend(
        [
            (pl.col(col_name) / 1000).mean().round(3).alias(f"media_{slug}_km"),
            (pl.col(col_name) < threshold_m).sum().alias(near_col),
            pl.len().alias(total_col),
        ]
    )
    pct_exprs.append(
        (pl.col(near_col) / pl.col(total_col) * 100).round(1).alias(f"pct_cerca_{slug}")
    )
    drop_cols.extend([near_col, total_col])

crime_type_stats = (
    multi_df.filter(pl.col("offense_description").is_not_null())
    .group_by("offense_description")
    .agg(agg_exprs)
    .with_columns(pct_exprs)
    .drop(drop_cols)
    .sort("total", descending=True)
    .head(20)
)
dataframe(crime_type_stats.to_pandas(), hide_index=True)


# ---------------------------------------------------------------------------
# 5. Cross-tab between two USGS layers
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("V2: tabla cruzada de proximidad entre capas USGS")

other_options = [label for label in usgs_layers if label != selected_layer]

BIN_LABELS = ["Muy cerca (<250m)", "Cerca (250-500m)", "Media (500m-1km)", "Lejos (>1km)"]


def _bin_distance(col: str, alias: str) -> pl.Expr:
    return (
        pl.when(pl.col(col) < 250)
        .then(pl.lit(BIN_LABELS[0]))
        .when(pl.col(col) < 500)
        .then(pl.lit(BIN_LABELS[1]))
        .when(pl.col(col) < 1000)
        .then(pl.lit(BIN_LABELS[2]))
        .otherwise(pl.lit(BIN_LABELS[3]))
        .alias(alias)
    )


if other_options:
    compare_layer = st.selectbox("Comparar contra", options=other_options, index=0)
    selected_col = distance_cols[selected_layer]
    compare_col = distance_cols[compare_layer]
    cross_df = (
        multi_df.with_columns(
            [
                _bin_distance(selected_col, "bin_referencia"),
                _bin_distance(compare_col, "bin_comparada"),
            ]
        )
        .group_by("bin_referencia", "bin_comparada")
        .len()
        .rename({"len": "crimenes"})
        .sort("bin_referencia", "bin_comparada")
    )
    pivot = cross_df.pivot(on="bin_comparada", index="bin_referencia", values="crimenes")
    dataframe(pivot.to_pandas().set_index("bin_referencia"))
else:
    st.info("Se necesita mas de una capa USGS V2 para la tabla cruzada.")
