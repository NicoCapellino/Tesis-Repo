"""
Temporal Analysis Page.

Visualizations:
- Monthly crime evolution (line chart by offense level)
- Day-of-week × hour heatmap
- Year-over-year comparison
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import streamlit as st

from app.components.filters import get_filtered_data

st.header("Análisis Temporal")

df = get_filtered_data()

# ---------------------------------------------------------------------------
# 1. Monthly evolution by offense level
# ---------------------------------------------------------------------------
st.subheader("Evolución mensual por nivel de ofensa")

monthly = (
    df.group_by("year", "month", "offense_level")
    .len()
    .sort("year", "month")
    .with_columns(
        (pl.col("year").cast(pl.Utf8) + "-" + pl.col("month").cast(pl.Utf8).str.pad_start(2, "0"))
        .alias("year_month")
    )
)

fig_monthly = px.line(
    monthly.to_pandas(),
    x="year_month",
    y="len",
    color="offense_level",
    labels={"len": "Cantidad de crímenes", "year_month": "Mes", "offense_level": "Nivel"},
    title="Evolución mensual de crímenes por nivel de ofensa",
)
fig_monthly.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig_monthly, width="stretch")


# ---------------------------------------------------------------------------
# 2. Day-of-week × Hour heatmap
# ---------------------------------------------------------------------------
st.subheader("Concentración por día de semana y hora")

DAY_NAMES = {1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves", 5: "Viernes", 6: "Sábado", 7: "Domingo"}

heatmap_data = (
    df.filter(pl.col("day_of_week").is_not_null() & pl.col("hour").is_not_null())
    .group_by("day_of_week", "hour")
    .len()
    .sort("day_of_week", "hour")
)

if not heatmap_data.is_empty():
    pivot = heatmap_data.pivot(on="hour", index="day_of_week", values="len").sort("day_of_week")

    hour_cols = sorted([c for c in pivot.columns if c != "day_of_week"], key=int)
    z_values = pivot.select(hour_cols).to_numpy()
    y_labels = [DAY_NAMES.get(d, str(d)) for d in pivot["day_of_week"].to_list()]

    fig_heatmap = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=[f"{h}:00" for h in hour_cols],
            y=y_labels,
            colorscale="YlOrRd",
            hovertemplate="Día: %{y}<br>Hora: %{x}<br>Crímenes: %{z}<extra></extra>",
        )
    )
    fig_heatmap.update_layout(
        title="Mapa de calor: Crímenes por día de semana y hora",
        xaxis_title="Hora del día",
        yaxis_title="Día de la semana",
    )
    st.plotly_chart(fig_heatmap, width="stretch")
else:
    st.info("No hay datos temporales disponibles con los filtros actuales.")


# ---------------------------------------------------------------------------
# 3. Year-over-year comparison
# ---------------------------------------------------------------------------
st.subheader("Comparación año contra año")

yearly = df.group_by("year").len().sort("year")

fig_yearly = px.bar(
    yearly.to_pandas(),
    x="year",
    y="len",
    labels={"len": "Total de crímenes", "year": "Año"},
    title="Total de crímenes por año",
    text="len",
)
fig_yearly.update_traces(texttemplate="%{text:,}", textposition="outside")
st.plotly_chart(fig_yearly, width="stretch")
