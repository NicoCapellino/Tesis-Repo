"""Download pipeline for NYC crime and infrastructure data.

Handles paginated downloads from the Socrata Open Data API (crimes) and
bulk downloads from the Overpass / OpenStreetMap API (police & transport
stations).  Every HTTP request uses exponential back-off retries.
"""

import io
import os
import csv
import time
import requests

from .config import (
    NY_API_URL, OVERPASS_URL, NY_BBOX, YEARS,
    DATA_BASE, NY_CRIMES_RAW,
    SOCRATA_PAGE_LIMIT, SOCRATA_APP_TOKEN,
    SOCRATA_REQUEST_DELAY, HTTP_MAX_RETRIES, HTTP_RETRY_BASE_DELAY,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _request_with_retry(method, url, *, max_retries=None, base_delay=None,
                        **kwargs):
    """Execute an HTTP request with exponential back-off.

    Parameters
    ----------
    method : str
        HTTP method ("GET", "POST", …).
    url : str
        Target URL.
    max_retries : int, optional
        Number of retries (default from config).
    base_delay : float, optional
        Base delay in seconds; doubles each retry (default from config).
    **kwargs
        Forwarded to ``requests.request()``.

    Returns
    -------
    requests.Response
    """
    max_retries = max_retries if max_retries is not None else HTTP_MAX_RETRIES
    base_delay = base_delay if base_delay is not None else HTTP_RETRY_BASE_DELAY

    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = base_delay * (2 ** (attempt - 1))
                print(f"  [retry {attempt}/{max_retries}] {exc} — waiting {wait:.0f}s …")
                time.sleep(wait)
            else:
                raise last_exc


# ---------------------------------------------------------------------------
# Crime data  –  Socrata API with proper pagination
# ---------------------------------------------------------------------------

def download_ny_crimes(years=None, save_path=None, page_limit=None):
    """Download New York crime data from the Socrata Open Data API.

    Paginates through all records for each year using ``$limit`` /
    ``$offset``, writing a single CSV per year.  Each file contains
    the full header row followed by all data rows for that year.

    Parameters
    ----------
    years : list[int], optional
        Calendar years to download (default: config.YEARS).
    save_path : str, optional
        Directory for output CSVs (default: config.NY_CRIMES_RAW).
    page_limit : int, optional
        Rows per page (default: config.SOCRATA_PAGE_LIMIT, max 50 000).
    """
    years = years or YEARS
    save_path = save_path or NY_CRIMES_RAW
    page_limit = page_limit or SOCRATA_PAGE_LIMIT
    os.makedirs(save_path, exist_ok=True)

    # Optional Socrata app-token header (raises rate limits)
    headers = {}
    if SOCRATA_APP_TOKEN:
        headers["X-App-Token"] = SOCRATA_APP_TOKEN

    summary: dict[int, int] = {}

    for year in years:
        start = f"{year}-01-01T00:00:00.000"
        end = f"{year}-12-31T23:59:59.999"

        where_clause = f"cmplnt_fr_dt between '{start}' and '{end}'"
        file_path = os.path.join(save_path, f"new_york_crimes_{year}.csv")

        print(f"\n{'─' * 50}")
        print(f"Downloading NY crimes for {year} …")
        print(f"{'─' * 50}")

        total_rows = 0
        offset = 0
        header_written = False

        with open(file_path, "w", newline="", encoding="utf-8") as out_f:
            while True:
                params = {
                    "$where": where_clause,
                    "$limit": page_limit,
                    "$offset": offset,
                    "$order": "cmplnt_num",      # deterministic ordering
                }

                response = _request_with_retry(
                    "GET", NY_API_URL,
                    headers=headers,
                    params=params,
                    timeout=120,
                )

                # Parse the CSV text returned by Socrata
                text = response.text
                reader = csv.reader(io.StringIO(text))
                rows = list(reader)

                if not rows:
                    break

                csv_header = rows[0]
                data_rows = rows[1:]          # strip the header Socrata sends

                if not data_rows:
                    break

                writer = csv.writer(out_f)

                if not header_written:
                    writer.writerow(csv_header)
                    header_written = True

                writer.writerows(data_rows)
                page_count = len(data_rows)
                total_rows += page_count
                offset += page_count

                print(f"  page {offset // page_limit + 1}: "
                      f"+{page_count:,} rows  (cumulative {total_rows:,})")

                # If we got fewer rows than the limit we've reached the end
                if page_count < page_limit:
                    break

                # Respect rate limits
                time.sleep(SOCRATA_REQUEST_DELAY)

        summary[year] = total_rows
        print(f"  ✓ {year}: {total_rows:,} rows saved to {file_path}")

    # Final report
    grand_total = sum(summary.values())
    print(f"\n{'═' * 50}")
    print(f"Crime download complete — {len(years)} years, {grand_total:,} total rows")
    for yr, cnt in sorted(summary.items()):
        print(f"  {yr}: {cnt:,}")
    print(f"{'═' * 50}")

    return summary


# ---------------------------------------------------------------------------
# Police stations  –  Overpass API
# ---------------------------------------------------------------------------

def download_police_stations(save_path=None, bbox=None):
    """Download police stations from OpenStreetMap via the Overpass API.

    Queries nodes, ways and relations tagged ``amenity=police`` inside the
    given bounding box and writes them to a CSV.
    """
    bbox = bbox or NY_BBOX
    save_path = save_path or f"{DATA_BASE}/new_york"
    min_lat, min_lon, max_lat, max_lon = bbox

    query = f"""
    [out:json][timeout:120];
    (
      node["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """

    print("Downloading police stations from Overpass API …")
    response = _request_with_retry(
        "GET", OVERPASS_URL, params={"data": query}, timeout=120,
    )
    data = response.json()

    if "elements" not in data or len(data["elements"]) == 0:
        raise RuntimeError("No police-station elements returned from Overpass API")

    output_dir = os.path.join(save_path, "police_stations")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "new_york_police_stations.csv")

    written = 0
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "name", "lat", "lon"])
        for el in data["elements"]:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            name = el.get("tags", {}).get("name", "")
            writer.writerow([el.get("id"), el.get("type"), name, lat, lon])
            written += 1

    print(f"  ✓ {written} police stations saved to {file_path}")
    return written


# ---------------------------------------------------------------------------
# Transport stations  –  Overpass API
# ---------------------------------------------------------------------------

def download_transport_stations(save_path=None, bbox=None):
    """Download transport stations (bus, rail, subway) via the Overpass API.

    Queries bus stations, train stations, subway entrances and generic
    public-transport stations inside the given bounding box.
    """
    bbox = bbox or NY_BBOX
    save_path = save_path or f"{DATA_BASE}/new_york"
    min_lat, min_lon, max_lat, max_lon = bbox

    query = f"""
    [out:json][timeout:120];
    (
      node["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["amenity"="bus_station"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["railway"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["railway"="subway_entrance"]({min_lat},{min_lon},{max_lat},{max_lon});
      node["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["public_transport"="station"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """

    print("Downloading transport stations from Overpass API …")
    response = _request_with_retry(
        "GET", OVERPASS_URL, params={"data": query}, timeout=120,
    )
    data = response.json()

    if "elements" not in data or len(data["elements"]) == 0:
        raise RuntimeError("No transport-station elements returned from Overpass API")

    output_dir = os.path.join(save_path, "transport_stations")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "new_york_transport_stations.csv")

    written = 0
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "transport_type", "name", "lat", "lon"])
        for el in data["elements"]:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is None or lon is None:
                continue
            tags = el.get("tags", {})
            name = tags.get("name", "")

            if tags.get("amenity") == "bus_station":
                transport_type = "bus_station"
            elif tags.get("railway") == "station":
                transport_type = "train_station"
            elif tags.get("railway") == "subway_entrance":
                transport_type = "subway_entrance"
            elif tags.get("public_transport") == "station":
                transport_type = "public_transport_station"
            else:
                transport_type = "unknown"

            writer.writerow([el.get("id"), el.get("type"), transport_type, name, lat, lon])
            written += 1

    print(f"  ✓ {written} transport stations saved to {file_path}")
    return written


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_downloads():
    """Download all data needed for the analysis pipeline.

    Returns a dict with download counts / summary for logging.
    """
    results = {}

    print("=" * 60)
    print("STEP 1 / 3: Downloading crime data")
    print("=" * 60)
    results["crimes"] = download_ny_crimes()

    print()
    print("=" * 60)
    print("STEP 2 / 3: Downloading police stations")
    print("=" * 60)
    results["police_stations"] = download_police_stations()

    print()
    print("=" * 60)
    print("STEP 3 / 3: Downloading transport stations")
    print("=" * 60)
    results["transport_stations"] = download_transport_stations()

    print()
    print("All downloads complete.")
    return results
