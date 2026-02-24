# Paths — resolved relative to THIS file's parent directory (notebooks/)
# so they work regardless of the working directory (Jupyter, docker exec, etc.)
import os as _os

_SRC_DIR = _os.path.dirname(_os.path.abspath(__file__))       # notebooks/src/
_NOTEBOOKS_DIR = _os.path.dirname(_SRC_DIR)                    # notebooks/
DATA_BASE = _os.path.join(_NOTEBOOKS_DIR, "data")

NY_CRIMES_RAW = _os.path.join(DATA_BASE, "new_york", "crimes")
NY_CRIMES_NORMALIZED = _os.path.join(DATA_BASE, "new_york", "crimes_normalized", "parquet")
NY_POLICE_STATIONS = _os.path.join(DATA_BASE, "new_york", "police_stations", "new_york_police_stations.csv")
NY_TRANSPORT_STATIONS = _os.path.join(DATA_BASE, "new_york", "transport_stations", "new_york_transport_stations.csv")

# API URLs
NY_API_URL = "https://data.cityofnewyork.us/resource/5uac-w243.csv"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Socrata API pagination settings
# Max rows per request (Socrata allows up to 50 000)
SOCRATA_PAGE_LIMIT = 50_000
# Optional Socrata app token for higher rate limits (None = anonymous)
SOCRATA_APP_TOKEN = None
# Seconds to wait between paginated requests (rate-limit courtesy)
SOCRATA_REQUEST_DELAY = 1.0
# Max retries per HTTP request before failing
HTTP_MAX_RETRIES = 3
# Base delay (seconds) for exponential back-off on retries
HTTP_RETRY_BASE_DELAY = 5.0

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
