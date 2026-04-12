"""
Prediction Page — Clasificación de nivel de ofensa con ML.

Entrena Random Forest y Gradient Boosting para clasificar crímenes en
FELONY / MISDEMEANOR / VIOLATION usando features temporales, geoespaciales
y de infraestructura.

Técnicas aplicadas:
- Codificación cíclica (sin/cos) para hora, día de semana, mes
- StandardScaler para features numéricas
- StratifiedKFold cross-validation (5 folds)
- Comparación RF vs Gradient Boosting
- Feature importance y métricas por clase
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import polars as pl
import streamlit as st
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

from app.components.background import (
    BackgroundTask,
    get_task,
    needs_recompute,
    show_progress_or_result,
)
from app.components.distances import add_distance_column
from app.components.filters import (
    get_filtered_data,
    get_police_stations,
    get_transport_stations,
)

st.header("Predicción: Nivel de Ofensa — Modelos de Clasificación")
st.markdown(
    "Este análisis clasifica crímenes en **FELONY**, **MISDEMEANOR** o **VIOLATION** "
    "usando variables temporales y geoespaciales. Se comparan **Random Forest** y "
    "**Gradient Boosting** con validación cruzada estratificada (5 folds) para evaluar "
    "si la **proximidad a infraestructura** tiene poder predictivo sobre la gravedad del delito."
)

df = get_filtered_data()
police_df = get_police_stations()
transport_df = get_transport_stations()

if police_df is None or police_df.is_empty():
    st.warning("Datos de comisarías no disponibles. Ejecutá el pipeline primero.")
    st.stop()

# ── Controles ────────────────────────────────────────────────────────────────
with st.expander("Parámetros del modelo", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_estimators = st.slider(
            "Árboles (n_estimators)", min_value=50, max_value=300,
            value=150, step=50,
        )
    with col2:
        max_depth = st.slider(
            "Profundidad máxima", min_value=3, max_value=20,
            value=12, step=1,
        )
    with col3:
        test_size = st.slider(
            "% datos de test", min_value=0.15, max_value=0.40,
            value=0.25, step=0.05, format="%.2f",
        )
    with col4:
        model_choice = st.selectbox(
            "Modelo principal",
            ["Random Forest", "Gradient Boosting"],
            index=0,
        )

SAMPLE_N = 30_000


# ── Preparar features (main thread, cached) ─────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Preparando features...")
def _prepare_features(
    year_filter: tuple[int, ...],
    borough_filter: tuple[str, ...],
    level_filter: tuple[str, ...],
    p_lats: tuple[float, ...],
    p_lons: tuple[float, ...],
    t_lats: tuple[float, ...] | None,
    t_lons: tuple[float, ...] | None,
) -> pd.DataFrame | None:
    """Build feature matrix (main thread, cached)."""
    base = st.session_state["filtered"]

    required_cols = ["hour", "day_of_week", "month", "borough", "offense_level",
                     "latitude", "longitude"]
    if not all(c in base.columns for c in required_cols):
        return None

    optional_cols = [c for c in ["premise_type"] if c in base.columns]
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

    police_stations = pl.DataFrame({"lat": list(p_lats), "lon": list(p_lons)})
    base = add_distance_column(base, police_stations, col_name="dist_police_m")
    base = base.with_columns((pl.col("dist_police_m") / 1000).alias("dist_police_km"))

    if t_lats is not None and len(t_lats) > 0:
        transport_stations = pl.DataFrame({"lat": list(t_lats), "lon": list(t_lons)})
        base = add_distance_column(base, transport_stations, col_name="dist_transport_m")
        base = base.with_columns((pl.col("dist_transport_m") / 1000).alias("dist_transport_km"))

    return base.to_pandas()


t_lats = tuple(transport_df["lat"].to_list()) if transport_df is not None else None
t_lons = tuple(transport_df["lon"].to_list()) if transport_df is not None else None

features_pdf = _prepare_features(
    year_filter=tuple(sorted(df["year"].drop_nulls().unique().to_list())),
    borough_filter=tuple(sorted(df["borough"].drop_nulls().unique().to_list())),
    level_filter=tuple(sorted(df["offense_level"].drop_nulls().unique().to_list())),
    p_lats=tuple(police_df["lat"].to_list()),
    p_lons=tuple(police_df["lon"].to_list()),
    t_lats=t_lats,
    t_lons=t_lons,
)

if features_pdf is None or len(features_pdf) < 200:
    st.warning("No hay suficientes datos para entrenar el modelo con los filtros actuales.")
    st.stop()

st.caption(f"Registros utilizados: {len(features_pdf):,} (muestra de hasta {SAMPLE_N:,})")


# ── Funciones de cómputo para background thread ─────────────────────────────
# IMPORTANTE: Estas funciones NO usan APIs de Streamlit.

def _cyclical_encode(values: np.ndarray, period: float) -> tuple[np.ndarray, np.ndarray]:
    angle = 2 * np.pi * values / period
    return np.sin(angle), np.cos(angle)


def _build_feature_matrix(data: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, list[str], LabelEncoder]:
    df_work = data.copy()

    # Cyclical encoding
    hour_sin, hour_cos = _cyclical_encode(df_work["hour"].values, 24.0)
    dow_sin, dow_cos = _cyclical_encode(df_work["day_of_week"].values, 7.0)
    month_sin, month_cos = _cyclical_encode(df_work["month"].values, 12.0)

    df_work["hour_sin"] = hour_sin
    df_work["hour_cos"] = hour_cos
    df_work["dow_sin"] = dow_sin
    df_work["dow_cos"] = dow_cos
    df_work["month_sin"] = month_sin
    df_work["month_cos"] = month_cos

    # Interaction features
    df_work["is_night"] = ((df_work["hour"] >= 22) | (df_work["hour"] <= 6)).astype(float)
    df_work["is_weekend"] = df_work["day_of_week"].isin([6, 7]).astype(float)
    df_work["night_weekend"] = df_work["is_night"] * df_work["is_weekend"]
    df_work["log_dist_police"] = np.log1p(df_work["dist_police_km"])
    if "dist_transport_km" in df_work.columns:
        df_work["log_dist_transport"] = np.log1p(df_work["dist_transport_km"])
        df_work["dist_ratio"] = df_work["dist_police_km"] / (df_work["dist_transport_km"] + 0.01)

    # Borough one-hot
    borough_dummies = pd.get_dummies(df_work["borough"], prefix="borough")

    # Premise type one-hot (top 10)
    if "premise_type" in df_work.columns:
        top_premises = df_work["premise_type"].value_counts().head(10).index.tolist()
        df_work["premise_clean"] = df_work["premise_type"].where(
            df_work["premise_type"].isin(top_premises), "OTHER"
        )
        premise_dummies = pd.get_dummies(df_work["premise_clean"], prefix="premise")
    else:
        premise_dummies = pd.DataFrame()

    numeric_features = [
        "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
        "is_night", "is_weekend", "night_weekend",
        "dist_police_km", "log_dist_police",
    ]
    if "dist_transport_km" in df_work.columns:
        numeric_features.extend(["dist_transport_km", "log_dist_transport", "dist_ratio"])

    X_parts = [df_work[numeric_features], borough_dummies]
    if not premise_dummies.empty:
        X_parts.append(premise_dummies)
    X = pd.concat(X_parts, axis=1).astype(float)

    le = LabelEncoder()
    y = le.fit_transform(df_work["offense_level"])

    return X, y, X.columns.tolist(), le


def _train_single_model(
    X_scaled: np.ndarray, y: np.ndarray, feature_names: list[str],
    class_names: list[str], n_est: int, m_depth: int,
    t_size: float, use_gb: bool,
) -> dict:
    """Train one model with CV and holdout evaluation. No Streamlit API."""
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    if use_gb:
        model = GradientBoostingClassifier(
            n_estimators=n_est, max_depth=min(m_depth, 8),
            learning_rate=0.1, random_state=42, subsample=0.8,
        )
    else:
        model = RandomForestClassifier(
            n_estimators=n_est, max_depth=m_depth,
            random_state=42, n_jobs=-1, class_weight="balanced",
        )

    cv_scores = cross_val_score(model, X_scaled, y, cv=skf, scoring="accuracy", n_jobs=-1)

    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=t_size, random_state=42, stratify=y,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    return {
        "cm": confusion_matrix(y_test, y_pred),
        "importances": model.feature_importances_,
        "feature_names": feature_names,
        "class_names": class_names,
        "y_pred": y_pred,
        "y_test": y_test,
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
    """Train both models in background thread."""
    task.update(0.05, "Paso 1/4: Construyendo features...")
    X, y, feature_names, le = _build_feature_matrix(features_data)
    class_names = le.classes_.tolist()

    task.update(0.15, "Paso 2/4: Escalando features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    task.update(0.25, "Paso 3/4: Entrenando modelo principal + validación cruzada...")
    primary = _train_single_model(
        X_scaled, y, feature_names, class_names,
        n_est, m_depth, t_size, use_gb=primary_is_gb,
    )

    task.update(0.65, "Paso 4/4: Entrenando modelo secundario + validación cruzada...")
    secondary = _train_single_model(
        X_scaled, y, feature_names, class_names,
        n_est, m_depth, t_size, use_gb=(not primary_is_gb),
    )

    return primary, secondary


# ── Ejecutar en segundo plano ─────────────────────────────────────────────────
task = get_task("prediction")
params_hash = str(hash((
    n_estimators, max_depth, test_size, model_choice,
    len(features_pdf),
    tuple(sorted(df["year"].drop_nulls().unique().to_list())),
)))

if needs_recompute(task, params_hash):
    task.start(
        _train_models_bg,
        features_pdf, n_estimators, max_depth, test_size,
        model_choice == "Gradient Boosting",
    )

if not show_progress_or_result(task):
    st.stop()

primary, secondary = task.result

# ── KPIs ─────────────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(f"Accuracy ({primary['model_name']})", f"{primary['accuracy']:.3f}")
with c2:
    st.metric("CV Score (5-fold)", f"{primary['cv_mean']:.3f} ± {primary['cv_std']:.3f}")
with c3:
    st.metric(f"Accuracy ({secondary['model_name']})", f"{secondary['accuracy']:.3f}")
with c4:
    st.metric("Features", f"{len(primary['feature_names'])}")

# ── Cross-Validation Results ────────────────────────────────────────────────
st.markdown("---")
st.subheader("Validación Cruzada Estratificada (5-Fold)")
st.caption(
    "Cada fold entrena con 80% de los datos y evalúa con el 20% restante, "
    "manteniendo la proporción de clases. Esto da una estimación más robusta "
    "del rendimiento real del modelo que un solo split train/test."
)

cv_data = pd.DataFrame({
    "Fold": [f"Fold {i+1}" for i in range(5)] + [f"Fold {i+1}" for i in range(5)],
    "Accuracy": list(primary["cv_scores"]) + list(secondary["cv_scores"]),
    "Modelo": [primary["model_name"]] * 5 + [secondary["model_name"]] * 5,
})

fig_cv = px.bar(
    cv_data, x="Fold", y="Accuracy", color="Modelo", barmode="group",
    title="Accuracy por fold — Comparación de modelos",
    text="Accuracy",
)
fig_cv.update_traces(texttemplate="%{text:.3f}", textposition="outside")
fig_cv.update_layout(yaxis=dict(range=[0, 1]))
st.plotly_chart(fig_cv, width="stretch")

cv_summary = pd.DataFrame({
    "Modelo": [primary["model_name"], secondary["model_name"]],
    "CV Media": [primary["cv_mean"], secondary["cv_mean"]],
    "CV Std": [primary["cv_std"], secondary["cv_std"]],
    "Holdout Accuracy": [primary["accuracy"], secondary["accuracy"]],
}).round(4)
st.dataframe(cv_summary, width="stretch", hide_index=True)

# ── Confusion Matrix ─────────────────────────────────────────────────────────
st.markdown("---")
st.subheader(f"Matriz de Confusión — {primary['model_name']}")

fig_cm = px.imshow(
    primary["cm"],
    labels=dict(x="Predicho", y="Real", color="Cantidad"),
    x=primary["class_names"], y=primary["class_names"],
    color_continuous_scale="Blues", text_auto=True,
    title=f"Matriz de Confusión — {primary['model_name']}",
)
fig_cm.update_layout(width=600, height=500)
st.plotly_chart(fig_cm, width="stretch")

# ── Classification Report ────────────────────────────────────────────────────
st.subheader("Reporte de Clasificación")
st.code(primary["report"], language="text")

# ── Feature Importance ───────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Importancia de Features")
st.caption(
    "Las features con mayor importancia tienen más influencia en la predicción "
    "del nivel de ofensa. Features cíclicas (`hour_sin/cos`, `dow_sin/cos`) capturan "
    "patrones temporales periódicos. Si `dist_police_km` o `dist_transport_km` aparecen "
    "entre las más importantes, confirma que la proximidad a infraestructura "
    "es un factor relevante en la severidad del crimen."
)

feature_names = primary["feature_names"]
feat_imp_df = pd.DataFrame({
    "feature": feature_names,
    "importance": primary["importances"],
}).sort_values("importance", ascending=True).tail(15)

fig_imp = px.bar(
    feat_imp_df, x="importance", y="feature", orientation="h",
    labels={"importance": "Importancia", "feature": "Feature"},
    title=f"Top 15 features más importantes — {primary['model_name']}",
    color="importance", color_continuous_scale="YlOrRd",
)
fig_imp.update_layout(showlegend=False, coloraxis_showscale=False)
st.plotly_chart(fig_imp, width="stretch")

# ── Feature engineering explanation ──────────────────────────────────────────
st.markdown("---")
st.subheader("Ingeniería de Features Aplicada")

with st.expander("Ver detalle de features", expanded=False):
    st.markdown("""
| Feature | Descripción | Justificación |
|---------|-------------|---------------|
| `hour_sin`, `hour_cos` | Codificación cíclica de la hora | Captura que las 23h y las 0h son cercanas |
| `dow_sin`, `dow_cos` | Codificación cíclica del día de semana | El domingo (7) es cercano al lunes (1) |
| `month_sin`, `month_cos` | Codificación cíclica del mes | Diciembre es cercano a enero |
| `is_night` | Binaria: ¿es de noche? (22h-6h) | Los crímenes nocturnos suelen ser más graves |
| `is_weekend` | Binaria: ¿es fin de semana? | Patrón delictivo distinto en fines de semana |
| `night_weekend` | Interacción noche × fin de semana | Captura el efecto combinado |
| `dist_police_km` | Distancia a comisaría más cercana | Hipótesis central de la tesis |
| `log_dist_police` | Log de distancia a policía | Reduce asimetría en la distribución |
| `dist_transport_km` | Distancia a transporte más cercano | Proxy de actividad urbana |
| `dist_ratio` | Ratio policía/transporte | Zonas con baja cobertura relativa |
| `borough_*` | One-hot del borough | Cada borough tiene perfil delictivo propio |
| `premise_*` | One-hot del tipo de premisa (top 10) | El lugar del crimen influye en su gravedad |
""")

# ── Interpretación ───────────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Interpretación")

feat_ranks = pd.DataFrame({
    "feature": feature_names,
    "importance": primary["importances"],
}).sort_values("importance", ascending=False).reset_index(drop=True)
feat_ranks["rank"] = feat_ranks.index + 1

insights = []
for feat_name, label in [("dist_police_km", "Distancia a comisaría"),
                          ("log_dist_police", "Log dist. a comisaría"),
                          ("dist_transport_km", "Distancia a transporte")]:
    row = feat_ranks[feat_ranks["feature"] == feat_name]
    if not row.empty:
        rank_val = int(row["rank"].values[0])
        imp_val = float(row["importance"].values[0])
        insights.append(
            f"- **{label}** (`{feat_name}`) ocupa el puesto **#{rank_val}** "
            f"de {len(feature_names)} features (importancia: {imp_val:.4f})."
        )

for feat_name, label in [("hour_sin", "Hora (sin)"), ("is_night", "Es de noche"),
                          ("is_weekend", "Es fin de semana")]:
    row = feat_ranks[feat_ranks["feature"] == feat_name]
    if not row.empty:
        rank_val = int(row["rank"].values[0])
        imp_val = float(row["importance"].values[0])
        insights.append(
            f"- **{label}** (`{feat_name}`) → puesto **#{rank_val}** (importancia: {imp_val:.4f})."
        )

if insights:
    st.markdown("\n".join(insights))
else:
    st.info("No se encontraron features de distancia en el modelo.")

best_cv = max(primary["cv_mean"], secondary["cv_mean"])
best_model = primary["model_name"] if primary["cv_mean"] >= secondary["cv_mean"] else secondary["model_name"]

st.markdown("---")
st.markdown(
    f"**Resumen:** El mejor modelo es **{best_model}** con accuracy CV = **{best_cv:.3f}**. "
    f"Se utilizaron {len(feature_names)} features incluyendo codificación cíclica temporal, "
    f"features de interacción y distancias a infraestructura."
)
