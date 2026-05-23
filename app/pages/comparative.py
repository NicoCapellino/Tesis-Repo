"""
Comparative Analysis Page.

Cross-reference crime data with infrastructure data (police stations,
transport stations) to discover spatial patterns and correlations.

Visualizations:
1. Crime-to-station ratio by borough
2. Distance to nearest police station (sampled histogram)
3. Crime density around transport stations (radius analysis)
4. Interactive map: crime hotspots vs infrastructure overlay
"""

from __future__ import annotations

import folium
import numpy as np
import plotly.express as px
import polars as pl
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium

from app.components.distances import compute_nearest_distances, haversine_np


@st.cache_data(ttl=3600, show_spinner=False)
def _infra_dist_matrix(
    c_lats: tuple[float, ...], c_lons: tuple[float, ...],
    i_lats: tuple[float, ...], i_lons: tuple[float, ...],
) -> np.ndarray:
    c = np.array(c_lats)
    cl = np.array(c_lons)
    il = np.array(i_lats)
    iln = np.array(i_lons)
    return haversine_np(c[:, None], cl[:, None], il[None, :], iln[None, :])
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
from config.settings import CITY_CONFIGS, DEFAULT_CITY

st.header("Análisis Comparativo: Crímenes vs. Infraestructura")

df = get_filtered_data()
police_df = get_police_stations()
transport_df = get_transport_stations()
healthcare_df = get_healthcare()
schools_df = get_schools()
offices_df = get_offices()
usgs_police_df = get_usgs_police()
usgs_fire_df = get_usgs_fire()

center = CITY_CONFIGS[DEFAULT_CITY].default_center

# Prefer USGS police (authoritative) over OSM police for primary analyses
primary_police_df = (
    usgs_police_df
    if usgs_police_df is not None and not usgs_police_df.is_empty()
    else police_df
)
_police_source = "USGS" if primary_police_df is usgs_police_df else "OSM"

# Check if infrastructure data is available
has_police = primary_police_df is not None and not primary_police_df.is_empty()
has_transport = transport_df is not None and not transport_df.is_empty()

if not has_police and not has_transport:
    st.warning(
        "No hay datos de infraestructura disponibles. "
        "Ejecutá el pipeline con datos de comisarías y transporte: "
        "`docker-compose run --rm pipeline`"
    )
    st.stop()


# Distance helpers imported from app.components.distances


# ── Prepare geo-filtered crime data ─────────────────────────────────────
geo_df = df.filter(pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null())


# =========================================================================
# 1. Crime-to-Station Ratio by Borough
# =========================================================================
st.subheader("Relación crímenes por comisaría, por borough")

if has_police:
    # Assign each station to a borough using nearest-borough-center heuristic
    # NYC boroughs approximate centers
    BOROUGH_CENTERS = {
        "MANHATTAN": (40.7831, -73.9712),
        "BROOKLYN": (40.6782, -73.9442),
        "QUEENS": (40.7282, -73.7949),
        "BRONX": (40.8448, -73.8648),
        "STATEN ISLAND": (40.5795, -74.1502),
    }

    # Assign each police station to nearest borough (cached)
    @st.cache_data(ttl=3600)
    def _assign_station_boroughs(
        s_lats: tuple[float, ...], s_lons: tuple[float, ...],
    ) -> list[str]:
        boroughs: list[str] = []
        for lat, lon in zip(s_lats, s_lons):
            best_boro = min(
                BOROUGH_CENTERS,
                key=lambda b: haversine_np(
                    np.array([lat]), np.array([lon]),
                    np.array([BOROUGH_CENTERS[b][0]]), np.array([BOROUGH_CENTERS[b][1]]),
                )[0],
            )
            boroughs.append(best_boro)
        return boroughs

    station_boroughs = _assign_station_boroughs(
        tuple(primary_police_df["lat"].to_list()),
        tuple(primary_police_df["lon"].to_list()),
    )

    stations_by_borough = (
        pl.DataFrame({"borough": station_boroughs})
        .group_by("borough")
        .len()
        .rename({"len": "stations"})
    )

    crimes_by_borough = (
        geo_df.filter(pl.col("borough").is_not_null())
        .group_by("borough")
        .len()
        .rename({"len": "crimes"})
    )

    ratio_df = (
        crimes_by_borough.join(stations_by_borough, on="borough", how="left")
        .with_columns(
            (pl.col("crimes") / pl.col("stations")).round(0).cast(pl.Int64).alias("crimes_per_station")
        )
        .sort("crimes_per_station", descending=True)
    )

    col_chart, col_table = st.columns([2, 1])

    with col_chart:
        fig_ratio = px.bar(
            ratio_df.to_pandas(),
            x="borough",
            y="crimes_per_station",
            color="borough",
            text="crimes_per_station",
            labels={
                "crimes_per_station": "Crímenes por comisaría",
                "borough": "Borough",
            },
            title="Crímenes por comisaría de policía",
        )
        fig_ratio.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_ratio.update_layout(showlegend=False)
        st.plotly_chart(fig_ratio, width="stretch")

    with col_table:
        st.dataframe(
            ratio_df.select("borough", "crimes", "stations", "crimes_per_station").to_pandas(),
            width="stretch",
            hide_index=True,
        )
else:
    st.info("Datos de comisarías no disponibles.")


# =========================================================================
# 2. Distance to Nearest Police Station (histogram)
# =========================================================================
if has_police:
    st.subheader("Distancia a la comisaría más cercana")

    SAMPLE_SIZE = 20_000
    sample_df = geo_df.sample(n=min(SAMPLE_SIZE, len(geo_df)), seed=42)

    crime_lats = sample_df["latitude"].to_numpy()
    crime_lons = sample_df["longitude"].to_numpy()
    station_lats = primary_police_df["lat"].to_numpy()
    station_lons = primary_police_df["lon"].to_numpy()

    distances_m = compute_nearest_distances(
        tuple(crime_lats.tolist()), tuple(crime_lons.tolist()),
        tuple(station_lats.tolist()), tuple(station_lons.tolist()),
    )
    distances_km = distances_m / 1000

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Distancia media", f"{np.mean(distances_km):.2f} km")
    with col2:
        st.metric("Distancia mediana", f"{np.median(distances_km):.2f} km")
    with col3:
        pct_over_2km = (distances_km > 2).sum() / len(distances_km) * 100
        st.metric("Crímenes a >2 km", f"{pct_over_2km:.1f}%")

    fig_hist = px.histogram(
        x=distances_km,
        nbins=60,
        labels={"x": "Distancia a comisaría más cercana (km)", "y": "Cantidad de crímenes"},
        title=f"Distribución de distancia a comisaría más cercana (muestra de {len(sample_df):,})",
    )
    fig_hist.update_layout(bargap=0.05)
    fig_hist.add_vline(
        x=np.median(distances_km),
        line_dash="dash",
        line_color="red",
        annotation_text=f"Mediana: {np.median(distances_km):.2f} km",
    )
    st.plotly_chart(fig_hist, width="stretch")


# =========================================================================
# 3. Crime Density Around Transport Stations
# =========================================================================
if has_transport:
    st.subheader("Densidad de crímenes alrededor de estaciones de transporte")

    radius_m = st.slider(
        "Radio de análisis (metros)", min_value=100, max_value=2000, value=500, step=100
    )

    # Sample crimes for performance
    TRANSPORT_SAMPLE = 10_000
    transport_sample = geo_df.sample(n=min(TRANSPORT_SAMPLE, len(geo_df)), seed=42)
    c_lats = transport_sample["latitude"].to_numpy()
    c_lons = transport_sample["longitude"].to_numpy()
    t_lats = transport_df["lat"].to_numpy()
    t_lons = transport_df["lon"].to_numpy()

    # Cached matrix — only computed once per session, slider changes are instant
    dist_matrix = _infra_dist_matrix(
        tuple(c_lats.tolist()), tuple(c_lons.tolist()),
        tuple(t_lats.tolist()), tuple(t_lons.tolist()),
    )
    crimes_counts = (dist_matrix <= radius_m).sum(axis=0)

    crimes_per_station: list[dict] = []
    for i in range(len(t_lats)):
        crimes_per_station.append({
            "name": transport_df["name"][i] if transport_df["name"][i] else f"Station {i}",
            "transport_type": transport_df["transport_type"][i],
            "lat": float(t_lats[i]),
            "lon": float(t_lons[i]),
            "crimes_nearby": int(crimes_counts[i]),
        })

    station_crime_df = pl.DataFrame(crimes_per_station)

    # Stats by transport type
    type_stats = (
        station_crime_df.group_by("transport_type")
        .agg(
            pl.col("crimes_nearby").mean().round(1).alias("media_crimenes"),
            pl.col("crimes_nearby").median().alias("mediana_crimenes"),
            pl.col("crimes_nearby").max().alias("max_crimenes"),
            pl.len().alias("cantidad_estaciones"),
        )
        .sort("media_crimenes", descending=True)
    )

    st.dataframe(type_stats.to_pandas(), width="stretch", hide_index=True)

    # Top stations with most nearby crimes
    top_stations = station_crime_df.sort("crimes_nearby", descending=True).head(20)

    fig_top = px.bar(
        top_stations.to_pandas(),
        y="name",
        x="crimes_nearby",
        color="transport_type",
        orientation="h",
        labels={
            "crimes_nearby": f"Crímenes en radio de {radius_m}m",
            "name": "Estación",
            "transport_type": "Tipo",
        },
        title=f"Top 20 estaciones de transporte con más crímenes en {radius_m}m",
    )
    fig_top.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_top, width="stretch")


# =========================================================================
# 3b. Crime Density Around New Infrastructure Types
# =========================================================================

_NEW_INFRA = [
    ("Salud (hospitales + centros)", healthcare_df, "healthcare"),
    ("Escuelas federales", schools_df, "schools"),
    ("Oficinas federales", offices_df, "offices"),
    ("USGS Comisarías (federal)", usgs_police_df, "usgs_police"),
    ("USGS Estaciones de bomberos", usgs_fire_df, "usgs_fire"),
]

for _label, _infra_df, _key in _NEW_INFRA:
    if _infra_df is None or _infra_df.is_empty():
        continue

    st.subheader(f"Densidad de crímenes alrededor de: {_label}")

    _radius_m = st.slider(
        f"Radio de análisis — {_label} (metros)",
        min_value=100, max_value=2000, value=500, step=100,
        key=f"radius_{_key}",
    )

    _SAMPLE = 10_000
    _sample = geo_df.sample(n=min(_SAMPLE, len(geo_df)), seed=42)
    _c_lats = _sample["latitude"].to_numpy()
    _c_lons = _sample["longitude"].to_numpy()
    _i_lats = _infra_df["lat"].to_numpy()
    _i_lons = _infra_df["lon"].to_numpy()

    _dist_matrix = _infra_dist_matrix(
        tuple(_c_lats.tolist()), tuple(_c_lons.tolist()),
        tuple(_i_lats.tolist()), tuple(_i_lons.tolist()),
    )
    _counts = (_dist_matrix <= _radius_m).sum(axis=0)

    _rows = []
    for _i in range(len(_i_lats)):
        _rows.append({
            "name": _infra_df["name"][_i] or f"Facility {_i}",
            "facility_type": _infra_df["facility_type"][_i] if "facility_type" in _infra_df.columns else _label,
            "lat": float(_i_lats[_i]),
            "lon": float(_i_lons[_i]),
            "crimes_nearby": int(_counts[_i]),
        })

    _station_df = pl.DataFrame(_rows)
    _top = _station_df.sort("crimes_nearby", descending=True).head(20)

    _fig = px.bar(
        _top.to_pandas(),
        y="name",
        x="crimes_nearby",
        color="facility_type" if "facility_type" in _top.columns else None,
        orientation="h",
        labels={
            "crimes_nearby": f"Crímenes en radio de {_radius_m}m",
            "name": "Instalación",
            "facility_type": "Tipo",
        },
        title=f"Top 20 — {_label} con más crímenes en {_radius_m}m",
    )
    _fig.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(_fig, width="stretch", key=f"chart_{_key}")


# =========================================================================
# 4. Interactive Map: Crime Hotspots + Infrastructure
# =========================================================================
st.subheader("Mapa combinado: crímenes + infraestructura")

MAP_SAMPLE = 15_000
map_df = geo_df.sample(n=min(MAP_SAMPLE, len(geo_df)), seed=42)
heat_data = map_df.select("latitude", "longitude").to_numpy().tolist()

m = folium.Map(location=list(center), zoom_start=11, tiles="CartoDB positron")

# Crime heatmap layer
heat_group = folium.FeatureGroup(name="Densidad de crímenes", show=True)
HeatMap(heat_data, radius=8, blur=10, max_zoom=13).add_to(heat_group)
heat_group.add_to(m)

# Police stations layer (USGS when available, else OSM)
if has_police:
    police_group = folium.FeatureGroup(name=f"Comisarías ({_police_source})", show=True)
    for row in primary_police_df.iter_rows(named=True):
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color="blue",
            fill=True,
            fill_color="blue",
            fill_opacity=0.8,
            popup=f"<b>Comisaría:</b> {row.get('name', 'N/A')}",
        ).add_to(police_group)
    police_group.add_to(m)

# Transport stations layer (only named ones to avoid clutter)
if has_transport:
    transport_group = folium.FeatureGroup(name="Transporte público", show=False)
    named_transport = transport_df.filter(pl.col("name") != "").head(500)
    for row in named_transport.iter_rows(named=True):
        color = {
            "train_station": "green",
            "subway_entrance": "orange",
            "bus_station": "purple",
        }.get(row.get("transport_type", ""), "gray")

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            popup=f"<b>{row.get('name', 'N/A')}</b><br>Tipo: {row.get('transport_type', 'N/A')}",
        ).add_to(transport_group)
    transport_group.add_to(m)

# Healthcare layer
if healthcare_df is not None and not healthcare_df.is_empty():
    hc_group = folium.FeatureGroup(name="Salud (hospitales + centros)", show=False)
    for row in healthcare_df.iter_rows(named=True):
        color = "red" if row.get("facility_type") == "Hospital" else "lightred"
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=f"<b>{row.get('name', 'N/A')}</b><br>{row.get('facility_type', '')}<br>{row.get('agency', '')}",
        ).add_to(hc_group)
    hc_group.add_to(m)

# Schools layer
if schools_df is not None and not schools_df.is_empty():
    sch_group = folium.FeatureGroup(name="Escuelas (federales)", show=False)
    for row in schools_df.iter_rows(named=True):
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color="darkgreen",
            fill=True,
            fill_color="darkgreen",
            fill_opacity=0.8,
            popup=f"<b>{row.get('name', 'N/A')}</b><br>{row.get('agency', '')}",
        ).add_to(sch_group)
    sch_group.add_to(m)

# Offices layer
if offices_df is not None and not offices_df.is_empty():
    off_group = folium.FeatureGroup(name="Oficinas federales", show=False)
    for row in offices_df.iter_rows(named=True):
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            color="gray",
            fill=True,
            fill_color="gray",
            fill_opacity=0.7,
            popup=f"<b>{row.get('name', 'N/A')}</b><br>{row.get('agency', '')}",
        ).add_to(off_group)
    off_group.add_to(m)

# USGS Fire Stations layer
if usgs_fire_df is not None and not usgs_fire_df.is_empty():
    fire_group = folium.FeatureGroup(name="USGS Estaciones de bomberos", show=False)
    for row in usgs_fire_df.iter_rows(named=True):
        if row["lat"] is None or row["lon"] is None:
            continue
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color="orange",
            fill=True,
            fill_color="orange",
            fill_opacity=0.85,
            popup=(
                f"<b>{row.get('name', 'N/A')}</b><br>"
                f"USGS • Bomberos<br>"
                f"{row.get('address', '')}, {row.get('zipcode', '')}"
            ),
        ).add_to(fire_group)
    fire_group.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
st_folium(m, width=None, height=650, key="comparative_map")

# =========================================================================
# 5. Crime by Offense Level per Borough
# =========================================================================
st.subheader("Distribución de nivel de ofensa por borough")

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
    title="Crímenes por borough y nivel de ofensa",
)
st.plotly_chart(fig_stacked, width="stretch")
