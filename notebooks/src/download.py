import os
import csv
import requests

from .config import (
    NY_API_URL, OVERPASS_URL, NY_BBOX, YEARS,
    DATA_BASE, NY_CRIMES_RAW,
)


def download_ny_crimes(years=None, save_path=None):
    """Download New York crime data from NYC Open Data API by year."""
    years = years or YEARS
    save_path = save_path or NY_CRIMES_RAW
    os.makedirs(save_path, exist_ok=True)

    base_url = NY_API_URL + "?$offset=1000"

    for year in years:
        start = f"{year}-01-01T00:00:00.000"
        end = f"{year}-12-31T23:59:59.999"
        url = f"{base_url}&$where=cmplnt_fr_dt between '{start}' and '{end}'"

        print(f"Downloading NY crimes {year}...")
        response = requests.get(url)
        response.raise_for_status()

        file_path = os.path.join(save_path, f"new_york_crimes_{year}.csv")
        with open(file_path, "wb") as f:
            f.write(response.content)
        print(f"  -> {file_path}")

    print(f"Done: {len(years)} files downloaded")


def download_police_stations(save_path=None, bbox=None):
    """Download police stations from OpenStreetMap via Overpass API."""
    bbox = bbox or NY_BBOX
    save_path = save_path or f"{DATA_BASE}/new_york"
    min_lat, min_lon, max_lat, max_lon = bbox

    query = f"""
    [out:json][timeout:90];
    (
      node["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
      relation["amenity"="police"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out center;
    """

    print(f"Downloading police stations from Overpass API...")
    response = requests.get(OVERPASS_URL, params={"data": query}, timeout=100)
    response.raise_for_status()
    data = response.json()

    if "elements" not in data:
        raise RuntimeError("No elements returned from Overpass API")

    output_dir = os.path.join(save_path, "police_stations")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "new_york_police_stations.csv")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "name", "lat", "lon"])
        for el in data["elements"]:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            name = el.get("tags", {}).get("name", "")
            writer.writerow([el.get("id"), el.get("type"), name, lat, lon])

    print(f"  -> {len(data['elements'])} stations saved to {file_path}")


def download_transport_stations(save_path=None, bbox=None):
    """Download transport stations (bus, train, subway) from Overpass API."""
    bbox = bbox or NY_BBOX
    save_path = save_path or f"{DATA_BASE}/new_york"
    min_lat, min_lon, max_lat, max_lon = bbox

    query = f"""
    [out:json][timeout:90];
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

    print(f"Downloading transport stations from Overpass API...")
    response = requests.get(OVERPASS_URL, params={"data": query}, timeout=100)
    response.raise_for_status()
    data = response.json()

    if "elements" not in data:
        raise RuntimeError("No elements returned from Overpass API")

    output_dir = os.path.join(save_path, "transport_stations")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, "new_york_transport_stations.csv")

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "type", "transport_type", "name", "lat", "lon"])
        for el in data["elements"]:
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
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

    print(f"  -> {len(data['elements'])} stations saved to {file_path}")


def run_all_downloads():
    """Download all data needed for the pipeline."""
    print("=" * 60)
    print("STEP 1: Downloading crime data")
    print("=" * 60)
    download_ny_crimes()

    print()
    print("=" * 60)
    print("STEP 2: Downloading police stations")
    print("=" * 60)
    download_police_stations()

    print()
    print("=" * 60)
    print("STEP 3: Downloading transport stations")
    print("=" * 60)
    download_transport_stations()

    print()
    print("All downloads complete.")
