# New York Crime Data - Normalized

This folder contains the normalization workflow for New York crime data (2020-2025).

## Files

- **[normalize_new_york_crimes.ipynb](normalize_new_york_crimes.ipynb)** - Main notebook that normalizes the data

## What This Does

Transforms raw NY crime data from cryptic column names to clean, descriptive names:

| Before | After |
|--------|-------|
| `cmplnt_num` | `complaint_id` |
| `boro_nm` | `borough` |
| `ofns_desc` | `offense_description` |
| `law_cat_cd` | `offense_level` |
| `prem_typ_desc` | `premise_type` |
| ... | ... |

## Quick Start

1. **Run the notebook** to normalize data:
   ```bash
   jupyter notebook normalize_new_york_crimes.ipynb
   ```

2. **Track with DVC** (from project root):
   ```bash
   cd ../../  # Go to project root
   dvc add notebooks/data/new_york/crimes_normalized/parquet
   dvc push
   ```

3. **Commit to git**:
   ```bash
   git add notebooks/data/new_york/crimes_normalized/*.dvc
   git commit -m "Add normalized NY crime data"
   git push
   ```

## Output Location

Normalized data is saved to:
```
../data/new_york/crimes_normalized/
├── parquet/    # Partitioned by year (use this for PySpark/Sedona)
└── csv/        # Single CSV (use for quick inspection)
```

## Usage with PySpark + Apache Sedona

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import expr

# Load normalized data
df = spark.read.parquet("../data/new_york/crimes_normalized/parquet")

# Add geometry for Sedona
df_geo = df.withColumn("geometry", expr("ST_Point(longitude, latitude)"))

# Ready for geospatial analysis!
```

## Data Stats

- **Records**: ~3,600 crimes
- **Years**: 2020-2025
- **Boroughs**: Brooklyn, Manhattan, Queens, Bronx, Staten Island
- **Valid Coordinates**: 99.7%

For the full DVC workflow, see: [/notebooks/Docs/GUIA_DVC.md](../Docs/GUIA_DVC.md)
