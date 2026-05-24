"""
Overview / Home page - KPI summary of the filtered dataset.
"""

from __future__ import annotations

import polars as pl
import streamlit as st

from app.components.filters import get_filtered_data

df = get_filtered_data()

st.title("NYC Crime Analysis Dashboard V2")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total de registros", f"{len(df):,}")

with col2:
    felonies = len(df.filter(pl.col("offense_level") == "FELONY"))
    st.metric("Felonies", f"{felonies:,}")

with col3:
    st.metric("Boroughs", df["borough"].n_unique())

with col4:
    years = df["year"].drop_nulls().unique().sort().to_list()
    period = f"{years[0]}-{years[-1]}" if years else "N/A"
    st.metric("Periodo", period)

st.markdown("---")
st.markdown(
    """
    Usa el menu lateral para navegar entre las secciones:

    **Estadisticas Descriptivas** - Analisis basado en distribuciones y conteos:
    - **Temporal**: Evolucion mensual, patrones por dia/hora, comparativa anual.
    - **Geoespacial V2**: Mapa de calor interactivo con capas USGS V2.
    - **Demografico**: Perfil de victimas y sospechosos, tipos de premisa.

    **Analisis Avanzado V2** - Cruce de datos e inteligencia artificial con infraestructura USGS:
    - **Comparativo**: Ratio crimenes/comisarias USGS, exposicion por instalaciones
      y capa USGS mas cercana.
    - **Proximidad**: Boxplots y tablas cruzadas de crimenes cerca vs. lejos de
      policia, bomberos y salud USGS.
    - **Clustering K-Means**: Zonas de alta criminalidad identificadas por ML.
    - **Reglas de Asociacion**: Patrones entre tipo de delito y proximidad a capas USGS V2.
    - **Prediccion ML**: Random Forest y Gradient Boosting con features de distancia USGS V2.
    - **Anomalias**: Isolation Forest para detectar dias con actividad criminal inusual.

    ---
    *Fuente: NYC Open Data - NYPD Complaint Data (2020-2025) + USGS National Map Structures V2*
    """
)
