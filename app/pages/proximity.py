"""
Proximity Analysis Page — Boxplots: crímenes cerca vs. lejos de comisarías.

El usuario ajusta el umbral de distancia con un deslizador y los gráficos
se actualizan en tiempo real mostrando las diferencias de distribución
entre crímenes cercanos y lejanos a una comisaría de policía.

Visualizaciones:
1. Boxplot unificado: distribución horaria (CERCA vs LEJOS)
2. Boxplot unificado: distancia a transporte (CERCA vs LEJOS de policía)
3. Boxplot: distancia a comisaría por tipo de crimen (top 10)
4. Tabla de estadísticas descriptivas de distancias
5. Tabla por tipo de crimen: dist media, % cerca
6. Tabla cruzada: bins de proximidad policía × transporte
"""

from __future__ import annotations

import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st

from app.components.distances import add_distance_column, compute_nearest_distances
from app.components.filters import (
    get_filtered_data,
    get_healthcare,
    get_offices,
    get_police_stations,
    get_schools,
    get_transport_stations,
    get_usgs_fire,
    get_usgs_police,
)

st.header("Proximidad: Crímenes Cerca vs. Lejos de Infraestructura")

df = get_filtered_data()
police_df = get_police_stations()
transport_df = get_transport_stations()
healthcare_df = get_healthcare()
schools_df = get_schools()
offices_df = get_offices()
usgs_police_df = get_usgs_police()
usgs_fire_df = get_usgs_fire()

# Build available infrastructure options (USGS sources listed first)
_INFRA_OPTIONS: dict[str, pl.DataFrame | None] = {
    "USGS Comisarías (federal)": usgs_police_df,
    "USGS Estaciones de bomberos": usgs_fire_df,
    "Transporte público": transport_df,
    "Salud (hospitales + centros)": healthcare_df,
    "Escuelas federales": schools_df,
    "Oficinas federales": offices_df,
    "Comisarías de policía (OSM)": police_df,
}
_available = {k: v for k, v in _INFRA_OPTIONS.items() if v is not None and not v.is_empty()}

if not _available:
    st.warning(
        "No hay datos de infraestructura disponibles. "
        "Ejecutá el pipeline primero: `docker-compose run --rm pipeline`"
    )
    st.stop()

# ── Controles ────────────────────────────────────────────────────────────────
st.markdown(
    "Seleccioná el tipo de infraestructura y ajustá el umbral de distancia "
    "para definir qué se considera *cerca*. Los gráficos se actualizan automáticamente."
)

selected_infra = st.selectbox(
    "Infraestructura de referencia",
    options=list(_available.keys()),
    index=0,
    help="El análisis CERCA/LEJOS se calcula respecto a esta infraestructura.",
)

# Resolve to the right lat/lon column names (police/transport use lat/lon, FRPP also uses lat/lon)
_ref_df = _available[selected_infra]
_ref_label = selected_infra

# Normalize: ensure lat/lon columns exist (police_df and transport_df already have lat/lon)
if "lat" not in _ref_df.columns or "lon" not in _ref_df.columns:
    st.error(f"El dataset de '{selected_infra}' no tiene columnas lat/lon.")
    st.stop()

# Override police_df for downstream logic so the rest of the page works generically
police_df = _ref_df

threshold_km = st.slider(
    "Umbral de distancia (km)",
    min_value=0.1, max_value=3.0, value=0.5, step=0.1,
    help="Crímenes a menos de esta distancia se clasifican como CERCA; los demás como LEJOS.",
)

SAMPLE_N = 20_000

# ── Calcular distancias a infraestructura seleccionada ───────────────────────
@st.cache_data(ttl=3600, show_spinner="Calculando distancias...")
def _get_police_distances(
    year_filter: tuple[int, ...],
    borough_filter: tuple[str, ...],
    level_filter: tuple[str, ...],
    p_lats: tuple[float, ...],
    p_lons: tuple[float, ...],
) -> pl.DataFrame:
    """Compute distance-to-nearest-police for a consistent sample."""
    base = st.session_state["filtered"]
    return add_distance_column(
        base, pl.DataFrame({"lat": list(p_lats), "lon": list(p_lons)}),
        col_name="dist_police_m",
        sample_n=SAMPLE_N,
    )


sample_df = _get_police_distances(
    year_filter=tuple(sorted(df["year"].drop_nulls().unique().to_list())),
    borough_filter=tuple(sorted(df["borough"].drop_nulls().unique().to_list())),
    level_filter=tuple(sorted(df["offense_level"].drop_nulls().unique().to_list())),
    p_lats=tuple(police_df["lat"].to_list()),
    p_lons=tuple(police_df["lon"].to_list()),
)

# Classify CERCA / LEJOS based on the slider threshold
threshold_m = threshold_km * 1000
cerca_label = f"CERCA (< {threshold_km} km) — {_ref_label}"
lejos_label = f"LEJOS (≥ {threshold_km} km) — {_ref_label}"

sample_df = sample_df.with_columns(
    pl.when(pl.col("dist_police_m") < threshold_m)
    .then(pl.lit(cerca_label))
    .otherwise(pl.lit(lejos_label))
    .alias("grupo_policia")
)

cerca_count = int((sample_df["dist_police_m"] < threshold_m).sum())
lejos_count = len(sample_df) - cerca_count

# ── KPIs ─────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total en muestra", f"{len(sample_df):,}")
with col2:
    st.metric(f"CERCA (< {threshold_km} km)", f"{cerca_count:,}")
with col3:
    st.metric(f"LEJOS (≥ {threshold_km} km)", f"{lejos_count:,}")
with col4:
    pct = cerca_count / len(sample_df) * 100 if len(sample_df) > 0 else 0
    st.metric("% CERCA", f"{pct:.1f}%")

st.markdown("---")

# ── Boxplot 1: Distribución horaria (UNIFICADO) ─────────────────────────────
st.subheader(f"Distribución horaria: CERCA vs. LEJOS de {_ref_label}")
st.caption(
    f"¿Los crímenes cometidos cerca de {_ref_label} ocurren a horas distintas "
    "que los cometidos lejos? Un desplazamiento en la distribución podría indicar "
    "un efecto disuasorio o de concentración en ciertos horarios. "
    "Cada punto representa un crimen individual."
)

hour_df = sample_df.filter(
    pl.col("hour").is_not_null()
    & pl.col("hour").is_between(0, 23)
)

if not hour_df.is_empty():
    fig_hour = px.box(
        hour_df.to_pandas(),
        x="grupo_policia",
        y="hour",
        color="grupo_policia",
        points="all",
        color_discrete_map={
            cerca_label: "#2196F3",
            lejos_label: "#F44336",
        },
        labels={"hour": "Hora del día (0-23)", "grupo_policia": "Proximidad a Comisaría"},
        title=f"Distribución horaria: CERCA vs. LEJOS de {_ref_label}",
        category_orders={"grupo_policia": [cerca_label, lejos_label]},
    )
    fig_hour.update_traces(
        boxmean=True,
        jitter=0.3,
        marker=dict(opacity=0.2, size=2),
    )
    fig_hour.update_layout(
        showlegend=False,
        yaxis=dict(dtick=1, range=[-0.5, 23.5], title="Hora del día (0-23)"),
        height=500,
    )
    st.plotly_chart(fig_hour, width="stretch")

    # Statistical summary for hour distribution
    _hour_stats = (
        hour_df.group_by("grupo_policia")
        .agg(
            pl.col("hour").count().alias("n"),
            pl.col("hour").mean().round(2).alias("media"),
            pl.col("hour").median().alias("mediana"),
            pl.col("hour").std().round(2).alias("std"),
            pl.col("hour").quantile(0.25).alias("Q1"),
            pl.col("hour").quantile(0.75).alias("Q3"),
        )
        .with_columns(
            (pl.col("Q3") - pl.col("Q1")).round(2).alias("IQR"),
        )
        .sort("grupo_policia")
    )
    st.caption("Resumen estadístico:")
    st.dataframe(_hour_stats.to_pandas(), width="stretch", hide_index=True)
else:
    st.info("No hay datos de hora disponibles.")

# ── Boxplot 2: Distancia a transporte (UNIFICADO) ───────────────────────────
if transport_df is not None and not transport_df.is_empty():
    st.markdown("---")
    st.subheader("Distancia al transporte: CERCA vs. LEJOS de comisaría")
    st.caption(
        "¿Los crímenes lejos de comisarías también tienden a estar lejos del transporte público? "
        "Esto revelaría si ciertas zonas de la ciudad tienen simultáneamente baja cobertura "
        "policial y de transporte."
    )

    _valid = sample_df.filter(
        pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null()
    )
    _t_dists = compute_nearest_distances(
        tuple(_valid["latitude"].to_list()),
        tuple(_valid["longitude"].to_list()),
        tuple(transport_df["lat"].to_list()),
        tuple(transport_df["lon"].to_list()),
    )
    sample_with_transport = _valid.with_columns(pl.Series("dist_transport_m", _t_dists))
    sample_with_transport = sample_with_transport.with_columns(
        (pl.col("dist_transport_m") / 1000).alias("dist_transport_km"),
        (pl.col("dist_police_m") / 1000).alias("dist_police_km"),
    ).filter(pl.col("dist_transport_km") < 10)

    # Reclassify with current threshold (transport distances don't change with threshold)
    sample_with_transport = sample_with_transport.with_columns(
        pl.when(pl.col("dist_police_m") < threshold_m)
        .then(pl.lit(cerca_label))
        .otherwise(pl.lit(lejos_label))
        .alias("grupo_policia")
    )

    fig_transport = px.box(
        sample_with_transport.to_pandas(),
        x="grupo_policia",
        y="dist_transport_km",
        color="grupo_policia",
        points="all",
        color_discrete_map={
            cerca_label: "#2196F3",
            lejos_label: "#F44336",
        },
        labels={"dist_transport_km": "Distancia a transporte (km)", "grupo_policia": "Proximidad a Comisaría"},
        title=f"Distancia a transporte público: CERCA vs. LEJOS de {_ref_label}",
        category_orders={"grupo_policia": [cerca_label, lejos_label]},
    )
    fig_transport.update_traces(
        boxmean=True,
        jitter=0.3,
        marker=dict(opacity=0.2, size=2),
    )
    fig_transport.update_layout(
        showlegend=False,
        yaxis=dict(dtick=0.25, title="Distancia a transporte (km)"),
        height=550,
    )
    st.plotly_chart(fig_transport, width="stretch")

    # Statistical summary for transport distances
    _transport_stats = (
        sample_with_transport.group_by("grupo_policia")
        .agg(
            pl.col("dist_transport_km").count().alias("n"),
            pl.col("dist_transport_km").mean().round(3).alias("media_km"),
            pl.col("dist_transport_km").median().round(3).alias("mediana_km"),
            pl.col("dist_transport_km").std().round(3).alias("std_km"),
            pl.col("dist_transport_km").quantile(0.25).round(3).alias("Q1"),
            pl.col("dist_transport_km").quantile(0.75).round(3).alias("Q3"),
        )
        .with_columns(
            (pl.col("Q3") - pl.col("Q1")).round(3).alias("IQR"),
        )
        .sort("grupo_policia")
    )
    st.caption("Resumen estadístico:")
    st.dataframe(_transport_stats.to_pandas(), width="stretch", hide_index=True)

    # ── KPI: Crímenes cerca de AMBAS infraestructuras ────────────────────────
    st.markdown("---")
    st.subheader("Crímenes cerca de ambas infraestructuras")

    cerca_ambas = int(
        sample_with_transport.filter(
            (pl.col("dist_police_m") < threshold_m)
            & (pl.col("dist_transport_m") < threshold_m)
        ).height
    )
    total_sample_t = len(sample_with_transport)
    pct_ambas = cerca_ambas / total_sample_t * 100 if total_sample_t > 0 else 0

    cerca_solo_policia = int(
        sample_with_transport.filter(
            (pl.col("dist_police_m") < threshold_m)
            & (pl.col("dist_transport_m") >= threshold_m)
        ).height
    )
    cerca_solo_transporte = int(
        sample_with_transport.filter(
            (pl.col("dist_police_m") >= threshold_m)
            & (pl.col("dist_transport_m") < threshold_m)
        ).height
    )
    lejos_ambas = int(
        sample_with_transport.filter(
            (pl.col("dist_police_m") >= threshold_m)
            & (pl.col("dist_transport_m") >= threshold_m)
        ).height
    )

    ca, cb, cc, cd = st.columns(4)
    with ca:
        st.metric("Cerca de ambas", f"{cerca_ambas:,}", help=f"{pct_ambas:.1f}% del total")
    with cb:
        st.metric("Solo cerca policía", f"{cerca_solo_policia:,}")
    with cc:
        st.metric("Solo cerca transporte", f"{cerca_solo_transporte:,}")
    with cd:
        st.metric("Lejos de ambas", f"{lejos_ambas:,}")

# ── Boxplot 3: Distancia a comisaría por tipo de crimen ─────────────────────
st.markdown("---")
st.subheader(f"Distancia a {_ref_label} por tipo de crimen (top 10)")
st.caption(
    f"¿Qué tipos de crimen tienden a ocurrir más lejos de {_ref_label}? "
    "Tipos con mediana alta sugieren menor cobertura para ese delito."
)

crime_dist_df = sample_df.filter(pl.col("offense_description").is_not_null()).with_columns(
    (pl.col("dist_police_m") / 1000).alias("dist_police_km"),
)

# Top 10 most frequent offense types
top10_offenses = (
    crime_dist_df.group_by("offense_description")
    .len()
    .sort("len", descending=True)
    .head(10)["offense_description"]
    .to_list()
)

crime_dist_top10 = crime_dist_df.filter(pl.col("offense_description").is_in(top10_offenses))

if not crime_dist_top10.is_empty():
    fig_crime_dist = px.box(
        crime_dist_top10.to_pandas(),
        x="offense_description",
        y="dist_police_km",
        color="offense_description",
        points="outliers",
        labels={
            "dist_police_km": "Distancia a comisaría (km)",
            "offense_description": "Tipo de crimen",
        },
        title=f"Distribución de distancia a {_ref_label} por tipo de crimen",
    )
    fig_crime_dist.update_traces(boxmean=True)
    fig_crime_dist.update_layout(
        showlegend=False,
        xaxis_tickangle=-45,
        yaxis=dict(dtick=0.5, title="Distancia a comisaría (km)"),
        height=600,
        margin=dict(b=150),
    )
    st.plotly_chart(fig_crime_dist, width="stretch")

# ── Tabla describe() de distancias ───────────────────────────────────────────
st.markdown("---")
st.subheader("Estadísticas descriptivas de distancias")

dist_describe_df = sample_df.with_columns(
    (pl.col("dist_police_m") / 1000).alias("dist_police_km"),
)

police_desc = dist_describe_df["dist_police_km"].describe()
desc_data = {"Métrica": ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]}

stats_police = dist_describe_df["dist_police_km"]
desc_data[f"Dist. {_ref_label[:20]} (km)"] = [
    f"{len(stats_police):,}",
    f"{stats_police.mean():.3f}",
    f"{stats_police.std():.3f}",
    f"{stats_police.min():.3f}",
    f"{stats_police.quantile(0.25):.3f}",
    f"{stats_police.median():.3f}",
    f"{stats_police.quantile(0.75):.3f}",
    f"{stats_police.max():.3f}",
]

if transport_df is not None and not transport_df.is_empty() and "dist_transport_km" in sample_with_transport.columns:
    stats_transport = sample_with_transport["dist_transport_km"]
    desc_data["Dist. Transporte (km)"] = [
        f"{len(stats_transport):,}",
        f"{stats_transport.mean():.3f}",
        f"{stats_transport.std():.3f}",
        f"{stats_transport.min():.3f}",
        f"{stats_transport.quantile(0.25):.3f}",
        f"{stats_transport.median():.3f}",
        f"{stats_transport.quantile(0.75):.3f}",
        f"{stats_transport.max():.3f}",
    ]

import pandas as pd
st.dataframe(pd.DataFrame(desc_data), width="stretch", hide_index=True)

# ── Tabla por tipo de crimen ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Estadísticas de proximidad por tipo de crimen")
st.caption(
    "Distancia media a policía y transporte, y porcentaje de crímenes cerca "
    "de cada infraestructura, desglosado por tipo de delito."
)

crime_stats_base = sample_df.filter(
    pl.col("offense_description").is_not_null()
).with_columns(
    (pl.col("dist_police_m") / 1000).alias("dist_police_km"),
)

crime_type_stats = (
    crime_stats_base.group_by("offense_description")
    .agg(
        pl.len().alias("total"),
        pl.col("dist_police_km").mean().round(3).alias("dist_media_policia_km"),
        (pl.col("dist_police_m") < threshold_m).sum().alias("cerca_policia"),
    )
    .with_columns(
        (pl.col("cerca_policia") / pl.col("total") * 100).round(1).alias("%_cerca_policia"),
    )
    .sort("total", descending=True)
    .head(20)
)

# Add transport stats if available
if (
    transport_df is not None
    and not transport_df.is_empty()
    and "dist_transport_km" in sample_with_transport.columns
):
    transport_type_stats = (
        sample_with_transport.filter(pl.col("offense_description").is_not_null())
        .group_by("offense_description")
        .agg(
            pl.col("dist_transport_km").mean().round(3).alias("dist_media_transporte_km"),
            (pl.col("dist_transport_m") < threshold_m).sum().alias("cerca_transporte"),
            pl.len().alias("_total_t"),
        )
        .with_columns(
            (pl.col("cerca_transporte") / pl.col("_total_t") * 100).round(1).alias("%_cerca_transporte"),
        )
        .drop("_total_t", "cerca_transporte")
    )
    crime_type_stats = crime_type_stats.join(
        transport_type_stats, on="offense_description", how="left"
    )

st.dataframe(
    crime_type_stats.drop("cerca_policia").to_pandas(),
    width="stretch",
    hide_index=True,
)

# ── Tabla cruzada de bins de proximidad ──────────────────────────────────────
st.markdown("---")
st.subheader("Tabla cruzada: bins de proximidad policía × transporte")
st.caption(
    "Distribución de crímenes según su distancia simultánea a comisarías y transporte público."
)

BIN_LABELS = ["Muy cerca (<250m)", "Cerca (250-500m)", "Media (500m-1km)", "Lejos (>1km)"]

def _bin_distance(col: str, alias: str) -> pl.Expr:
    return (
        pl.when(pl.col(col) < 250).then(pl.lit(BIN_LABELS[0]))
        .when(pl.col(col) < 500).then(pl.lit(BIN_LABELS[1]))
        .when(pl.col(col) < 1000).then(pl.lit(BIN_LABELS[2]))
        .otherwise(pl.lit(BIN_LABELS[3]))
        .alias(alias)
    )

if (
    transport_df is not None
    and not transport_df.is_empty()
    and "dist_transport_m" in sample_with_transport.columns
):
    cross_df = (
        sample_with_transport
        .with_columns([
            _bin_distance("dist_police_m", "bin_policia"),
            _bin_distance("dist_transport_m", "bin_transporte"),
        ])
        .group_by("bin_policia", "bin_transporte")
        .len()
        .sort("bin_policia", "bin_transporte")
        .rename({"len": "crimenes"})
    )

    pivot = cross_df.pivot(
        on="bin_transporte", index="bin_policia", values="crimenes"
    )
    st.dataframe(pivot.to_pandas().set_index("bin_policia"), width="stretch")
elif "dist_police_m" in sample_df.columns:
    police_bins = (
        sample_df
        .with_columns(_bin_distance("dist_police_m", "bin_policia"))
        .group_by("bin_policia")
        .len()
        .sort("bin_policia")
        .rename({"len": "crimenes"})
    )
    st.dataframe(police_bins.to_pandas(), width="stretch")
