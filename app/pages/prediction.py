"""
Prediction Page V2.

Classifies offense level using temporal, spatial, and USGS V2 infrastructure
features.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.components.background import (
    BackgroundTask,
    get_task,
    needs_recompute,
    show_progress_or_result,
)
from app.components.display import dataframe, plotly_chart
from app.components.distances import add_distance_column
from app.components.filters import get_filtered_data, get_usgs_v2_layers
from app.components.utils import slugify as _slug

st.header("Prediccion V2: Nivel de Ofensa con features USGS")
st.markdown(
    "Este modelo clasifica crimenes en **FELONY**, **MISDEMEANOR** o **VIOLATION** "
    "usando variables temporales, borough, premisa y distancias a infraestructura "
    "**USGS V2**: policia, bomberos y salud."
)

df = get_filtered_data()
usgs_layers = get_usgs_v2_layers()

if not usgs_layers:
    st.warning("No hay capas USGS V2 disponibles. Ejecuta el pipeline de referencia USGS.")
    st.stop()


with st.expander("Parametros del modelo V2", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_estimators = st.slider("Arboles", min_value=50, max_value=300, value=150, step=50)
    with col2:
        max_depth = st.slider("Profundidad maxima", min_value=3, max_value=20, value=12, step=1)
    with col3:
        test_size = st.slider(
            "% datos de test",
            min_value=0.15,
            max_value=0.40,
            value=0.25,
            step=0.05,
            format="%.2f",
        )
    with col4:
        model_choice = st.selectbox(
            "Modelo principal",
            ["Random Forest", "Gradient Boosting"],
            index=0,
        )

SAMPLE_N = 30_000


@st.cache_data(ttl=3600, show_spinner="Preparando features USGS V2...")
def _prepare_features(
    base: pl.DataFrame,
    year_filter: tuple[int, ...],
    borough_filter: tuple[str, ...],
    level_filter: tuple[str, ...],
    layers_payload: tuple[tuple[str, tuple[float, ...], tuple[float, ...]], ...],
) -> pd.DataFrame | None:

    required_cols = [
        "hour",
        "day_of_week",
        "month",
        "borough",
        "offense_level",
        "latitude",
        "longitude",
    ]
    if not all(col in base.columns for col in required_cols):
        return None

    optional_cols = [col for col in ["premise_type"] if col in base.columns]
    base = base.select(required_cols + optional_cols)
    base = base.drop_nulls(subset=required_cols)
    base = base.filter(pl.col("offense_level").is_in(["FELONY", "MISDEMEANOR", "VIOLATION"]))
    base = base.filter(
        pl.col("hour").is_between(0, 23)
        & pl.col("day_of_week").is_between(1, 7)
        & pl.col("month").is_between(1, 12)
    )

    if len(base) > SAMPLE_N:
        base = base.sample(n=SAMPLE_N, seed=42)
    if len(base) < 200:
        return None

    for label, lats, lons in layers_payload:
        slug = _slug(label)
        dist_m_col = f"dist_{slug}_m"
        dist_km_col = f"dist_{slug}_km"
        stations = pl.DataFrame({"lat": list(lats), "lon": list(lons)})
        base = add_distance_column(base, stations, col_name=dist_m_col)
        base = base.with_columns((pl.col(dist_m_col) / 1000).alias(dist_km_col))

    return base.to_pandas()


layers_payload = tuple(
    (label, tuple(layer_df["lat"].to_list()), tuple(layer_df["lon"].to_list()))
    for label, layer_df in usgs_layers.items()
)

features_pdf = _prepare_features(
    df,
    year_filter=tuple(sorted(df["year"].drop_nulls().unique().to_list())),
    borough_filter=tuple(sorted(df["borough"].drop_nulls().unique().to_list())),
    level_filter=tuple(sorted(df["offense_level"].drop_nulls().unique().to_list())),
    layers_payload=layers_payload,
)

if features_pdf is None or len(features_pdf) < 200:
    st.warning("No hay suficientes datos para entrenar el modelo con los filtros actuales.")
    st.stop()

st.caption(f"Registros utilizados: {len(features_pdf):,} (muestra de hasta {SAMPLE_N:,})")


def _cyclical_encode(values: np.ndarray, period: float) -> tuple[np.ndarray, np.ndarray]:
    angle = 2 * np.pi * values / period
    return np.sin(angle), np.cos(angle)


def _build_feature_matrix(
    data: pd.DataFrame,
) -> tuple[pd.DataFrame, np.ndarray, list[str], LabelEncoder]:
    df_work = data.copy()

    hour_sin, hour_cos = _cyclical_encode(df_work["hour"].values, 24.0)
    dow_sin, dow_cos = _cyclical_encode(df_work["day_of_week"].values, 7.0)
    month_sin, month_cos = _cyclical_encode(df_work["month"].values, 12.0)

    df_work["hour_sin"] = hour_sin
    df_work["hour_cos"] = hour_cos
    df_work["dow_sin"] = dow_sin
    df_work["dow_cos"] = dow_cos
    df_work["month_sin"] = month_sin
    df_work["month_cos"] = month_cos
    df_work["is_night"] = ((df_work["hour"] >= 22) | (df_work["hour"] <= 6)).astype(float)
    df_work["is_weekend"] = df_work["day_of_week"].isin([6, 7]).astype(float)
    df_work["night_weekend"] = df_work["is_night"] * df_work["is_weekend"]

    dist_km_cols = [
        col for col in df_work.columns if col.startswith("dist_usgs_v2") and col.endswith("_km")
    ]
    for col in dist_km_cols:
        df_work[f"log_{col}"] = np.log1p(df_work[col])

    police_cols = [col for col in dist_km_cols if "policia" in col]
    if police_cols:
        police_col = police_cols[0]
        for col in dist_km_cols:
            if col != police_col:
                ratio_col = f"ratio_{police_col}_to_{col}"
                df_work[ratio_col] = df_work[police_col] / (df_work[col] + 0.01)

    borough_dummies = pd.get_dummies(df_work["borough"], prefix="borough")

    if "premise_type" in df_work.columns:
        top_premises = df_work["premise_type"].value_counts().head(10).index.tolist()
        df_work["premise_clean"] = df_work["premise_type"].where(
            df_work["premise_type"].isin(top_premises),
            "OTHER",
        )
        premise_dummies = pd.get_dummies(df_work["premise_clean"], prefix="premise")
    else:
        premise_dummies = pd.DataFrame()

    numeric_features = [
        "hour_sin",
        "hour_cos",
        "dow_sin",
        "dow_cos",
        "month_sin",
        "month_cos",
        "is_night",
        "is_weekend",
        "night_weekend",
    ]
    numeric_features.extend(dist_km_cols)
    numeric_features.extend([f"log_{col}" for col in dist_km_cols])
    numeric_features.extend(
        [col for col in df_work.columns if col.startswith("ratio_dist_usgs_v2")]
    )

    x_parts = [df_work[numeric_features], borough_dummies]
    if not premise_dummies.empty:
        x_parts.append(premise_dummies)
    x_matrix = pd.concat(x_parts, axis=1).astype(float)

    le = LabelEncoder()
    y = le.fit_transform(df_work["offense_level"])

    return x_matrix, y, x_matrix.columns.tolist(), le


def _train_single_model(
    x_scaled: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    class_names: list[str],
    n_est: int,
    m_depth: int,
    t_size: float,
    use_gb: bool,
) -> dict:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    if use_gb:
        model = GradientBoostingClassifier(
            n_estimators=n_est,
            max_depth=min(m_depth, 8),
            learning_rate=0.1,
            random_state=42,
            subsample=0.8,
        )
    else:
        model = RandomForestClassifier(
            n_estimators=n_est,
            max_depth=m_depth,
            random_state=42,
            n_jobs=-1,
            class_weight="balanced",
        )

    cv_scores = cross_val_score(model, x_scaled, y, cv=skf, scoring="accuracy", n_jobs=-1)

    x_train, x_test, y_train, y_test = train_test_split(
        x_scaled,
        y,
        test_size=t_size,
        random_state=42,
        stratify=y,
    )
    model.fit(x_train, y_train)
    y_pred = model.predict(x_test)

    return {
        "cm": confusion_matrix(y_test, y_pred),
        "importances": model.feature_importances_,
        "feature_names": feature_names,
        "class_names": class_names,
        "accuracy": accuracy_score(y_test, y_pred),
        "report": classification_report(y_test, y_pred, target_names=class_names),
        "cv_scores": cv_scores,
        "cv_mean": float(cv_scores.mean()),
        "cv_std": float(cv_scores.std()),
        "model_name": "Gradient Boosting" if use_gb else "Random Forest",
    }


def _train_models_bg(
    task: BackgroundTask,
    features_data: pd.DataFrame,
    n_est: int,
    m_depth: int,
    t_size: float,
    primary_is_gb: bool,
) -> tuple[dict, dict]:
    task.update(0.05, "Paso 1/4: Construyendo features USGS V2...")
    x_matrix, y, feature_names, le = _build_feature_matrix(features_data)
    class_names = le.classes_.tolist()

    task.update(0.15, "Paso 2/4: Escalando features...")
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x_matrix)

    task.update(0.25, "Paso 3/4: Entrenando modelo principal...")
    primary = _train_single_model(
        x_scaled,
        y,
        feature_names,
        class_names,
        n_est,
        m_depth,
        t_size,
        use_gb=primary_is_gb,
    )

    task.update(0.65, "Paso 4/4: Entrenando modelo secundario...")
    secondary = _train_single_model(
        x_scaled,
        y,
        feature_names,
        class_names,
        n_est,
        m_depth,
        t_size,
        use_gb=(not primary_is_gb),
    )

    return primary, secondary


task = get_task("prediction_v2")
params_hash = str(
    hash(
        (
            n_estimators,
            max_depth,
            test_size,
            model_choice,
            len(features_pdf),
            tuple((label, len(layer_df)) for label, layer_df in usgs_layers.items()),
            tuple(sorted(df["year"].drop_nulls().unique().to_list())),
        )
    )
)

if needs_recompute(task, params_hash):
    task.start(
        _train_models_bg,
        features_pdf,
        n_estimators,
        max_depth,
        test_size,
        model_choice == "Gradient Boosting",
    )

if not show_progress_or_result(task):
    st.stop()

primary, secondary = task.result

st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(f"Accuracy ({primary['model_name']})", f"{primary['accuracy']:.3f}")
with c2:
    st.metric("CV Score (5-fold)", f"{primary['cv_mean']:.3f} +/- {primary['cv_std']:.3f}")
with c3:
    st.metric(f"Accuracy ({secondary['model_name']})", f"{secondary['accuracy']:.3f}")
with c4:
    st.metric("Features V2", f"{len(primary['feature_names'])}")

st.markdown("---")
st.subheader("V2: validacion cruzada estratificada")

cv_data = pd.DataFrame(
    {
        "Fold": [f"Fold {i + 1}" for i in range(5)] + [f"Fold {i + 1}" for i in range(5)],
        "Accuracy": list(primary["cv_scores"]) + list(secondary["cv_scores"]),
        "Modelo": [primary["model_name"]] * 5 + [secondary["model_name"]] * 5,
    }
)

fig_cv = px.bar(
    cv_data,
    x="Fold",
    y="Accuracy",
    color="Modelo",
    barmode="group",
    title="V2: accuracy por fold",
    text="Accuracy",
)
fig_cv.update_traces(texttemplate="%{text:.3f}", textposition="outside")
fig_cv.update_layout(yaxis=dict(range=[0, 1]))
plotly_chart(fig_cv)

cv_summary = pd.DataFrame(
    {
        "Modelo": [primary["model_name"], secondary["model_name"]],
        "CV Media": [primary["cv_mean"], secondary["cv_mean"]],
        "CV Std": [primary["cv_std"], secondary["cv_std"]],
        "Holdout Accuracy": [primary["accuracy"], secondary["accuracy"]],
    }
).round(4)
dataframe(cv_summary, hide_index=True)

st.markdown("---")
st.subheader(f"V2: matriz de confusion - {primary['model_name']}")

fig_cm = px.imshow(
    primary["cm"],
    labels=dict(x="Predicho", y="Real", color="Cantidad"),
    x=primary["class_names"],
    y=primary["class_names"],
    color_continuous_scale="Blues",
    text_auto=True,
    title=f"V2: matriz de confusion - {primary['model_name']}",
)
fig_cm.update_layout(width=600, height=500)
plotly_chart(fig_cm)

st.subheader("V2: reporte de clasificacion")
st.code(primary["report"], language="text")

st.markdown("---")
st.subheader("V2: importancia de features")
st.caption(
    "Las distancias `dist_usgs_v2_*_km`, sus logs y ratios muestran cuanto aporta "
    "la cercania a instalaciones USGS al modelo."
)

feat_imp_df = (
    pd.DataFrame(
        {
            "feature": primary["feature_names"],
            "importance": primary["importances"],
        }
    )
    .sort_values("importance", ascending=True)
    .tail(15)
)

fig_imp = px.bar(
    feat_imp_df,
    x="importance",
    y="feature",
    orientation="h",
    labels={"importance": "Importancia", "feature": "Feature"},
    title=f"V2: top 15 features - {primary['model_name']}",
    color="importance",
    color_continuous_scale="YlOrRd",
)
fig_imp.update_layout(showlegend=False, coloraxis_showscale=False)
plotly_chart(fig_imp)

st.markdown("---")
st.subheader("V2: features USGS aplicadas")
distance_feature_rows = []
for label in usgs_layers:
    slug = _slug(label)
    distance_feature_rows.append(
        {
            "feature": f"dist_{slug}_km",
            "descripcion": f"Distancia al punto mas cercano de {label}",
        }
    )
    distance_feature_rows.append(
        {
            "feature": f"log_dist_{slug}_km",
            "descripcion": f"Log de distancia a {label}",
        }
    )
dataframe(pd.DataFrame(distance_feature_rows), hide_index=True)

feat_ranks = (
    pd.DataFrame(
        {
            "feature": primary["feature_names"],
            "importance": primary["importances"],
        }
    )
    .sort_values("importance", ascending=False)
    .reset_index(drop=True)
)
feat_ranks["rank"] = feat_ranks.index + 1

insights = []
for feature in [f for f in feat_ranks["feature"] if f.startswith("dist_usgs_v2")][:5]:
    row = feat_ranks[feat_ranks["feature"] == feature].iloc[0]
    insights.append(
        f"- **{feature}** ocupa el puesto **#{int(row['rank'])}** "
        f"(importancia: {float(row['importance']):.4f})."
    )

if insights:
    st.markdown("\n".join(insights))

best_cv = max(primary["cv_mean"], secondary["cv_mean"])
best_model = (
    primary["model_name"] if primary["cv_mean"] >= secondary["cv_mean"] else secondary["model_name"]
)

st.markdown(
    f"**Resumen V2:** el mejor modelo es **{best_model}** con accuracy CV = "
    f"**{best_cv:.3f}** usando infraestructura USGS V2 exclusivamente."
)
