"""
USGS Structures WFS — NYC POC

Fetches hospitals and law enforcement locations for New York City
from the USGS National Map via OGC WFS 2.0.

Service: https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
Standard: OGC WFS 2.0.0 — part of NSDI (National Spatial Data Infrastructure)

FType codes:
  800 = Hospitals / Medical Centers
  740 = Law Enforcement & Emergency Response

Run:
  python3 poc/usgs_structures_poc.py
"""

import xml.etree.ElementTree as ET

import httpx
import polars as pl

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WFS_URL = "https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer"
WFS_NS = "http://www.opengis.net/wfs/2.0"
FIELDS = ["NAME", "FType", "FCode", "ADDRESS", "CITY", "STATE", "ZIPCODE", "LOADDATE"]

# NYC borough ZIP code prefixes — more reliable than CITY name matching.
# BBOX spatial filter returns 0 (geometries not spatially indexed on this service).
NYC_ZIP_PREFIXES = {
    "100": "Manhattan",
    "101": "Manhattan",
    "102": "Manhattan",
    "103": "Staten Island",
    "104": "Bronx",
    "112": "Brooklyn",
    "113": "Queens",
    "114": "Queens",
    "116": "Queens",
}

# ---------------------------------------------------------------------------
# WFS fetch
# ---------------------------------------------------------------------------


def build_xml_filter(ftype: int, state: str = "NY") -> str:
    """OGC FES 2.0 XML filter body — POST required, GET params ignored by this service."""
    return f"""<?xml version="1.0"?>
<wfs:GetFeature xmlns:wfs="http://www.opengis.net/wfs/2.0"
                xmlns:fes="http://www.opengis.net/fes/2.0"
                service="WFS" version="2.0.0" count="5000">
  <wfs:Query typeNames="structures:USGS_TNM_Structures">
    <fes:Filter>
      <fes:And>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>FType</fes:ValueReference>
          <fes:Literal>{ftype}</fes:Literal>
        </fes:PropertyIsEqualTo>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>STATE</fes:ValueReference>
          <fes:Literal>{state}</fes:Literal>
        </fes:PropertyIsEqualTo>
      </fes:And>
    </fes:Filter>
  </wfs:Query>
</wfs:GetFeature>"""


def fetch_ny(ftype: int) -> pl.DataFrame:
    print(f"  Querying WFS for FType {ftype} in NY state...")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            WFS_URL,
            content=build_xml_filter(ftype),
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    print(f"  matched: {root.get('numberMatched')}, returned: {root.get('numberReturned')}")

    rows = []
    for member in root.iter(f"{{{WFS_NS}}}member"):
        for feat in member:
            row = {f: None for f in FIELDS}
            for child in feat:
                tag = child.tag.split("}")[-1]
                if tag in FIELDS:
                    row[tag] = child.text
            rows.append(row)

    return pl.DataFrame(rows, schema={f: pl.Utf8 for f in FIELDS})


def filter_nyc(df: pl.DataFrame) -> pl.DataFrame:
    """Filter to NYC using ZIP code prefixes and add borough column."""
    return (
        df.with_columns(pl.col("ZIPCODE").str.slice(0, 3).alias("zip_prefix"))
        .filter(pl.col("zip_prefix").is_in(list(NYC_ZIP_PREFIXES.keys())))
        .with_columns(pl.col("zip_prefix").replace(NYC_ZIP_PREFIXES).alias("borough"))
        .drop("zip_prefix")
    )


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def completeness(df: pl.DataFrame, label: str) -> None:
    total = len(df)
    rows = []
    for col in ["NAME", "ADDRESS", "CITY", "ZIPCODE", "LOADDATE"]:
        filled = df[col].drop_nulls().len()
        missing = total - filled
        pct = round(filled / total * 100, 1) if total else 0
        rows.append({"field": col, "filled": filled, "missing": missing, "complete_%": pct})
    print(f"\n--- Completeness: {label} (n={total}) ---")
    print(pl.DataFrame(rows))


def missing_address(df: pl.DataFrame, label: str) -> None:
    missing = df.filter(pl.col("ADDRESS").is_null())
    print(f"\n--- {label}: missing ADDRESS ({len(missing)} records) ---")
    if len(missing) > 0:
        print(missing.select(["NAME", "borough", "CITY", "ZIPCODE"]))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # --- Fetch ---
    section("1. Fetching from USGS WFS")
    hospitals_ny = fetch_ny(800)
    law_enforce_ny = fetch_ny(740)

    hospitals_nyc = filter_nyc(hospitals_ny)
    law_enforce_nyc = filter_nyc(law_enforce_ny)

    # --- Counts ---
    section("2. NYC Record Counts")
    print(f"  Hospitals:        {len(hospitals_nyc):>4}  (of {len(hospitals_ny)} NY state total)")
    print(
        f"  Law Enforcement:  {len(law_enforce_nyc):>4}  (of {len(law_enforce_ny)} NY state total)"
    )

    # --- Borough distribution ---
    section("3. Distribution by Borough")
    for label, df in [("Hospitals", hospitals_nyc), ("Law Enforcement", law_enforce_nyc)]:
        print(f"\n--- {label} ---")
        print(df.group_by("borough").agg(pl.len().alias("count")).sort("count", descending=True))

    # --- Completeness ---
    section("4. Completeness Check")
    completeness(hospitals_nyc, "Hospitals NYC")
    completeness(law_enforce_nyc, "Law Enforcement NYC")

    # --- Missing addresses ---
    section("5. Records Missing ADDRESS")
    missing_address(hospitals_nyc, "Hospitals")
    missing_address(law_enforce_nyc, "Law Enforcement")

    # --- Full preview ---
    section("6. Full NYC Record List")
    print("\n=== Hospitals ===")
    print(
        hospitals_nyc.select(["NAME", "borough", "ADDRESS", "ZIPCODE", "LOADDATE"]).sort("borough")
    )
    print("\n=== Law Enforcement ===")
    print(
        law_enforce_nyc.select(["NAME", "borough", "ADDRESS", "ZIPCODE", "LOADDATE"]).sort(
            "borough"
        )
    )

    # --- Export ---
    section("7. Export")
    hospitals_nyc.write_parquet("poc/hospitals_nyc.parquet")
    law_enforce_nyc.write_parquet("poc/law_enforcement_nyc.parquet")
    print(f"  Saved poc/hospitals_nyc.parquet       ({len(hospitals_nyc)} records)")
    print(f"  Saved poc/law_enforcement_nyc.parquet ({len(law_enforce_nyc)} records)")


if __name__ == "__main__":
    main()
