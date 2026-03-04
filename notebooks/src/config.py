# Paths (relative to /home/jovyan/work inside Docker container)
DATA_BASE = "data"
NY_CRIMES_RAW = f"{DATA_BASE}/new_york/crimes"
NY_CRIMES_NORMALIZED = f"{DATA_BASE}/new_york/crimes_normalized/parquet"
NY_POLICE_STATIONS = f"{DATA_BASE}/new_york/police_stations/new_york_police_stations.csv"
NY_TRANSPORT_STATIONS = f"{DATA_BASE}/new_york/transport_stations/new_york_transport_stations.csv"

# API URLs
NY_API_URL = "https://data.cityofnewyork.us/resource/5uac-w243.csv"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# New York bounding box (min_lat, min_lon, max_lat, max_lon)
NY_BBOX = (40.49, -74.26, 40.92, -73.70)

# Years to download
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

# Analysis parameters
KMEANS_K = 10
KMEANS_SEED = 42
FP_MIN_SUPPORT = 0.01
FP_MIN_CONFIDENCE = 0.8
PROXIMITY_THRESHOLD_KM = 0.5
ANOMALY_STDDEV_THRESHOLD = 2.0
