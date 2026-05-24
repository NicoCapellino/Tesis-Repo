"""
Anomaly Detection Page — Isolation Forest para detectar anomalías temporales.

Detecta días con actividad criminal anómalamente alta o baja usando
Isolation Forest sobre features de conteo diario por borough.

Visualizaciones:
1. Timeline con anomalías destacadas
2. Tabla de top anomalías con contexto
3. Distribución de anomalías por borough
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st
from sklearn.ensemble import IsolationForest

from app.components.background import (
    BackgroundTask,
    get_task,
    needs_recompute,
    show_progress_or_result,
)
from app.components.display import dataframe, plotly_chart
from app.components.filters import get_filtered_data

st.header("Detección de Anomalías — Isolation Forest")
st.markdown(
    "Isolation Forest identifica días con actividad criminal **inusualmente alta o baja** "
    "respecto al patrón normal. Las anomalías pueden indicar eventos especiales, "
    "feriados, protestas, o cambios en políticas policiales."
)

df = get_filtered_data()

# ── Controles ────────────────────────────────────────────────────────────────
with st.expander("Parámetros del modelo", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        contamination = st.slider(
            "Tasa de contaminación",
            min_value=0.01,
            max_value=0.15,
            value=0.05,
            step=0.01,
            format="%.2f",
            help="Proporción esperada de anomalías en los datos (0.05 = 5%).",
        )
    with col2:
        granularity = st.radio(
            "Granularidad",
            options=["Por día (ciudad)", "Por día y borough"],
            index=0,
        )


# ── Preparar datos ───────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Preparando datos temporales...")
def _prepare_daily_counts(
    year_filter: tuple[int, ...],
    borough_filter: tuple[str, ...],
    level_filter: tuple[str, ...],
    by_borough: bool,
) -> pl.DataFrame | None:
    """Aggregate crime counts by date (optionally by borough)."""
    base = st.session_state["filtered"]

    required = ["year", "month", "day_of_week"]
    if not all(c in base.columns for c in required):
        return None

    # We need a date column. Build it from year + month + a day.
    # Check if we have crime_start_date or similar
    date_cols = [c for c in base.columns if "date" in c.lower()]

    if date_cols:
        date_col = date_cols[0]
        base = base.filter(pl.col(date_col).is_not_null())

        group_cols = [date_col]
        if by_borough:
            base = base.filter(pl.col("borough").is_not_null())
            group_cols.append("borough")

        daily = (
            base.group_by(group_cols)
            .agg(
                pl.len().alias("crime_count"),
                pl.col("year").first().alias("year"),
                pl.col("month").first().alias("month"),
                pl.col("day_of_week").first().alias("day_of_week"),
            )
            .sort(date_col)
        )
        daily = daily.rename({date_col: "date"})
    else:
        # Build synthetic date from year/month/day_of_week
        # Group by year+month as proxy
        group_cols = ["year", "month"]
        if by_borough:
            base = base.filter(pl.col("borough").is_not_null())
            group_cols.append("borough")

        daily = (
            base.group_by(group_cols)
            .agg(
                pl.len().alias("crime_count"),
                pl.col("day_of_week").mode().first().alias("day_of_week"),
            )
            .sort(group_cols)
        )
        # Create a synthetic date column
        daily = daily.with_columns(pl.date(pl.col("year"), pl.col("month"), 1).alias("date"))

    return daily


by_borough = granularity == "Por día y borough"
daily_df = _prepare_daily_counts(
    year_filter=tuple(sorted(df["year"].drop_nulls().unique().to_list())),
    borough_filter=tuple(sorted(df["borough"].drop_nulls().unique().to_list())),
    level_filter=tuple(sorted(df["offense_level"].drop_nulls().unique().to_list())),
    by_borough=by_borough,
)

if daily_df is None or daily_df.is_empty():
    st.warning("No hay suficientes datos temporales para el análisis de anomalías.")
    st.stop()

st.caption(f"Períodos analizados: {len(daily_df):,}")


# ── Entrenar Isolation Forest (background thread) ───────────────────────────
def _detect_anomalies_bg(
    task: BackgroundTask,
    daily_data_pdf: pd.DataFrame,
    contam: float,
) -> pd.DataFrame:
    """Run Isolation Forest in background. No Streamlit API."""
    task.update(0.10, "Paso 1/3: Preparando features...")
    pdf = daily_data_pdf.copy()

    feature_cols = ["crime_count"]
    if "day_of_week" in pdf.columns:
        feature_cols.append("day_of_week")
    if "month" in pdf.columns:
        feature_cols.append("month")

    features_matrix = pdf[feature_cols].fillna(0).values

    task.update(0.30, "Paso 2/3: Entrenando Isolation Forest...")
    iso = IsolationForest(
        contamination=contam,
        random_state=42,
        n_jobs=-1,
    )
    pdf["anomaly"] = iso.fit_predict(features_matrix)

    task.update(0.70, "Paso 3/3: Calculando scores de anomalía...")
    pdf["anomaly_score"] = iso.decision_function(features_matrix)
    pdf["is_anomaly"] = pdf["anomaly"] == -1

    return pdf


task = get_task("anomalies")
params_hash = str(hash((contamination, granularity, len(daily_df))))

if needs_recompute(task, params_hash):
    task.start(_detect_anomalies_bg, daily_df.to_pandas(), contamination)

if not show_progress_or_result(task):
    st.stop()

result_df = task.result

# ── KPIs ─────────────────────────────────────────────────────────────────────
n_anomalies = int(result_df["is_anomaly"].sum())
n_total = len(result_df)
pct_anomalies = n_anomalies / n_total * 100 if n_total > 0 else 0

anomaly_rows = result_df[result_df["is_anomaly"]]
mean_normal = result_df[~result_df["is_anomaly"]]["crime_count"].mean()
mean_anomaly = anomaly_rows["crime_count"].mean() if len(anomaly_rows) > 0 else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Períodos totales", f"{n_total:,}")
with c2:
    st.metric("Anomalías detectadas", f"{n_anomalies:,}")
with c3:
    st.metric("% anomalías", f"{pct_anomalies:.1f}%")
with c4:
    st.metric("Media crímenes (anomalías)", f"{mean_anomaly:,.0f}")

st.markdown("---")

# ── Timeline con anomalías ───────────────────────────────────────────────────
st.subheader("Timeline: crímenes por día con anomalías destacadas")

if "date" in result_df.columns:
    result_df["date"] = pd.to_datetime(result_df["date"])

    fig_timeline = go.Figure()

    # Normal points
    normal = result_df[~result_df["is_anomaly"]]
    fig_timeline.add_trace(
        go.Scatter(
            x=normal["date"],
            y=normal["crime_count"],
            mode="lines",
            name="Normal",
            line=dict(color="#2196F3", width=1),
            opacity=0.7,
        )
    )

    # Anomaly points
    anomalies = result_df[result_df["is_anomaly"]]
    fig_timeline.add_trace(
        go.Scatter(
            x=anomalies["date"],
            y=anomalies["crime_count"],
            mode="markers",
            name="Anomalía",
            marker=dict(color="red", size=8, symbol="x"),
            text=anomalies.get("borough", ""),
            hovertemplate="Fecha: %{x}<br>Crímenes: %{y}<br>%{text}<extra></extra>",
        )
    )

    # Mean reference line
    fig_timeline.add_hline(
        y=mean_normal,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"Media normal: {mean_normal:,.0f}",
    )

    fig_timeline.update_layout(
        title="Actividad criminal diaria con anomalías",
        xaxis_title="Fecha",
        yaxis_title="Cantidad de crímenes",
        hovermode="x unified",
    )
    plotly_chart(fig_timeline)

# ── Tabla de top anomalías ───────────────────────────────────────────────────
st.markdown("---")
st.subheader("Top anomalías detectadas")
st.caption(
    "Las anomalías con **score más negativo** son las más extremas. "
    "Un conteo de crímenes muy alto puede indicar un evento excepcional; "
    "uno muy bajo puede indicar un feriado o cierre."
)

top_anomalies = anomaly_rows.sort_values("anomaly_score").head(20)

display_cols = ["date", "crime_count", "anomaly_score"]
if "borough" in top_anomalies.columns:
    display_cols.insert(1, "borough")
if "day_of_week" in top_anomalies.columns:
    display_cols.append("day_of_week")

if not top_anomalies.empty:
    display_df = top_anomalies[display_cols].copy()
    display_df["anomaly_score"] = display_df["anomaly_score"].round(4)
    if "date" in display_df.columns:
        display_df["date"] = display_df["date"].astype(str)
    dataframe(display_df, hide_index=True)
else:
    st.info("No se detectaron anomalías con los parámetros actuales.")

# ── Distribución de anomalías por borough ────────────────────────────────────
if "borough" in result_df.columns and n_anomalies > 0:
    st.markdown("---")
    st.subheader("Distribución de anomalías por borough")

    borough_anomalies = (
        anomaly_rows.groupby("borough")
        .agg(
            total_anomalias=("is_anomaly", "sum"),
            media_crimenes=("crime_count", "mean"),
            score_min=("anomaly_score", "min"),
        )
        .sort_values("total_anomalias", ascending=False)
        .reset_index()
    )
    borough_anomalies["media_crimenes"] = borough_anomalies["media_crimenes"].round(0)
    borough_anomalies["score_min"] = borough_anomalies["score_min"].round(4)

    fig_borough = px.bar(
        borough_anomalies,
        x="borough",
        y="total_anomalias",
        color="media_crimenes",
        labels={
            "total_anomalias": "Anomalías detectadas",
            "borough": "Borough",
            "media_crimenes": "Media crímenes",
        },
        title="Anomalías por borough",
        text="total_anomalias",
        color_continuous_scale="YlOrRd",
    )
    fig_borough.update_traces(textposition="outside")
    plotly_chart(fig_borough)

# ── Histograma de scores ────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Distribución de anomaly scores")
st.caption(
    "Valores más negativos indican mayor grado de anomalía. "
    "El umbral de decisión separa las anomalías (izquierda) de los casos normales (derecha)."
)

fig_hist = px.histogram(
    result_df,
    x="anomaly_score",
    color="is_anomaly",
    nbins=50,
    color_discrete_map={True: "red", False: "#2196F3"},
    labels={"anomaly_score": "Anomaly Score", "is_anomaly": "Es anomalía"},
    title="Distribución de scores del Isolation Forest",
    barmode="overlay",
)
fig_hist.update_layout(bargap=0.05)
plotly_chart(fig_hist)
