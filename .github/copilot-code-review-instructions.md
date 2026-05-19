# Copilot Code Review Instructions

## Review Philosophy

- **Only flag issues with high confidence.** Avoid speculative or stylistic nits.
- **Be concise and actionable.** Each comment must include a concrete fix or code suggestion.
- **Do NOT duplicate CI checks.** Our CI already runs `ruff` (lint + format), `mypy --strict`, and `pytest`. Do not comment on import ordering, unused imports, line length, or formatting — ruff handles those.
- **Focus on:** logical correctness, data integrity bugs, security issues, performance regressions, architectural violations, and missing edge-case handling.

---

## Project Context

**NYC Crime Pipeline** — A Python 3.11+ ETL pipeline + Streamlit dashboard for analyzing ~3M NYPD crime records. Data is fetched from the Socrata SODA API, transformed with Polars, and visualized through a 10-page Streamlit dashboard with ML capabilities (K-Means, FP-Growth, Random Forest, Gradient Boosting, Isolation Forest).

### Architecture

```
config/settings.py     → Pydantic-settings (all config, URLs, params)
src/extract/           → HTTP extraction (httpx + tenacity retry)
src/transform/         → Data cleaning + normalization (Polars)
src/load/              → Parquet I/O layer
src/utils/logging.py   → structlog-based structured logging
src/pipeline.py        → ETL orchestrator (Extract → Transform → Load)
app/main.py            → Streamlit entry point (st.navigation, global filters)
app/pages/             → 10 analysis pages (each reads st.session_state["filtered"])
app/components/        → Reusable: BackgroundTask, distance helpers, filter helpers
```

### Tech Stack

| Purpose | Library | NOT allowed |
|---------|---------|-------------|
| DataFrames | **Polars** | ❌ pandas (except inside sklearn interop in `app/pages/prediction.py`) |
| HTTP | **httpx** | ❌ requests, urllib |
| Retry | **tenacity** (exponential backoff) | ❌ manual retry loops |
| Dashboard | **Streamlit** (multipage via `st.navigation`) | — |
| Visualization | **Plotly**, **Folium** (streamlit-folium), **pydeck** | ❌ matplotlib in dashboard pages |
| ML | **scikit-learn**, **mlxtend** | — |
| Config | **pydantic** + **pydantic-settings** | ❌ raw os.environ, dotenv |
| Logging | **structlog** (via `src.utils.logging.get_logger`) | ❌ print(), ❌ logging.getLogger() |
| Data format | **Parquet** with zstd compression | ❌ CSV for processed data |

---

## Critical Rules (Flag Violations)

### 1. Polars Only — No pandas

All data manipulation must use `polars.DataFrame`. Flag any `import pandas` or `pd.DataFrame` in `src/` or `config/`.

**Exception:** `app/pages/prediction.py` converts to pandas for sklearn compatibility — this is intentional and acceptable.

### 2. Structured Logging Only

```python
# ✅ Correct
from src.utils.logging import get_logger
log = get_logger(__name__)
log.info("event_name", key=value)

# ❌ Flag these
print("debug info")
logging.info("something")
import logging  # at module level in src/
```

### 3. Configuration Centralization

All magic numbers, API URLs, and tunable parameters must live in `config/settings.py`. Flag any hardcoded URLs or API endpoints outside this file.

**Exception:** `SAMPLE_N` constants in dashboard pages (e.g., `SAMPLE_N = 50_000`) are acceptable as page-level rendering limits.

### 4. HTTP Calls Must Have Retry + Timeout

Every external HTTP call must:
- Use `httpx.Client` or `httpx.AsyncClient` with an explicit `timeout=`
- Be wrapped with `@retry` from tenacity (or equivalent)
- Never hardcode API tokens — use environment variables

### 5. Session State Discipline (Streamlit)

- Pages must read filtered data via `get_filtered_data()` from `app/components/filters.py`, NOT directly from `st.session_state["complaints"]`.
- Never store unbounded data in `st.session_state` — always sample or limit.
- `st.set_page_config()` must only appear in `app/main.py`, never in page modules.

### 6. BackgroundTask Pattern for Heavy Computation

Any ML training, clustering, or association rule mining must use the `BackgroundTask` pattern from `app/components/background.py`:

```python
task = get_task("task_name")
if needs_recompute(task, params_hash):
    task.start(_compute_function, arg1, arg2)
if not show_progress_or_result(task):
    st.stop()
result = task.result
```

Background worker functions must **never** call Streamlit APIs (`st.*`).

---

## Data Integrity Rules (Flag Violations)

- **Cast with `strict=False`:** All `.cast()` calls on external/untrusted data must use `strict=False` to avoid crashing on dirty data.
- **Concat with `how="diagonal_relaxed"`:** When concatenating DataFrames with potentially different schemas (e.g., multi-year Parquets).
- **Null sentinel replacement:** Raw Socrata data uses `"(null)"`, `"UNKNOWN"`, `""` as null placeholders. These must be converted to actual `null` before analysis.
- **Coordinate validation:** Any lat/lon data must be validated against the city bounding box (defined in `CITY_CONFIGS`) before use in geospatial analysis.
- **Deduplication:** Records from `historic` and `current_ytd` datasets overlap. Always deduplicate on `cmplnt_num` / `complaint_id`.

---

## Performance Rules (Flag Violations)

- **Never load all Parquet columns.** Use `columns=` parameter in `pl.read_parquet()` to select only needed columns.
- **Sample before visualization.** Maps and scatter plots must sample data (typically 3K-50K points) to avoid browser crashes.
- **Use `@st.cache_data(ttl=3600)` on data-loading functions.** Never use the deprecated `@st.cache`.
- **Handle `MemoryError`.** Pages processing the full dataset should catch `MemoryError` gracefully.
- **Prefer `df.is_empty()` over `len(df) == 0`.**
- **Write Parquet with `compression="zstd"`.** Flag uncompressed or gzip Parquet writes.

---

## Security Rules (Flag Violations)

- **No secrets in code.** API tokens, passwords, connection strings must come from environment variables (via `pydantic-settings`).
- **No `eval()` or `exec()`.** Never on user-provided input.
- **Sanitize Streamlit widget inputs** before using them in SoQL `$where` clauses or file paths.

---

## Conventions (Suggest, Don't Block)

These are preferred patterns. Suggest improvements but don't block PRs:

- Use `from __future__ import annotations` in every module.
- Use keyword-only arguments (`*`) for functions with 3+ parameters.
- Docstrings on all public classes and functions (Google or NumPy style).
- Dashboard text (labels, titles, error messages) should be in **Spanish**.
- Use `pl.col()` expressions over indexing (`df["col"]`) in Polars chains.
- Comment sections with `# ── Section Title ──────` banner style (matches existing codebase).

---

## Docker Rules (Flag in Dockerfile/docker-compose changes)

- Multi-stage build must be preserved (builder → runtime).
- Target image size: ~350MB. Flag new heavy dependencies without justification.
- Data directory is volume-mounted, never `COPY`ed into the image.
- `PYTHONPATH=/app` is set — imports assume project root.
