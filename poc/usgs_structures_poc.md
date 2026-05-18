# USGS Structures WFS — POC Explanation

## What is this?

This POC fetches hospital and law enforcement location data for New York from the **USGS National Map** using a genuine OGC WFS 2.0 service — no flat file downloads, no ArcGIS REST. This is the SDI way: a standardized interoperable service consumed programmatically.

**Service endpoint:**
```
https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
```

---

## Why this source?

The USGS Structures layer is part of the **NSDI (National Spatial Data Infrastructure)** — authoritative government data, maintained by USGS, served through an OGC-compliant WFS. This replaces the OpenStreetMap data currently used in the app, which is community-contributed and not authoritative.

For a criminology thesis, the distinction matters: OSM hospitals and police stations are crowd-sourced. USGS structures are verified federal data.

---

## Data retrieved

| FType | Category | NY State total |
|---|---|---|
| 800 | Hospitals / Medical Centers | 236 |
| 740 | Law Enforcement & Fire Stations | ~400+ |

**Note on prisons:** FType 810 (Correctional Facilities) returned 0 records for NY. Prisons are not currently included in the USGS Structures dataset for New York state.

### Fields available

| Field | Description |
|---|---|
| `NAME` | Facility name |
| `FType` | Feature type code (800 = hospital, 740 = law enforcement) |
| `FCode` | Sub-type code (e.g. 80012 = hospital building) |
| `ADDRESS` | Street address |
| `CITY` | City name |
| `STATE` | State abbreviation |
| `ZIPCODE` | ZIP code |
| `LOADDATE` | Date the record was last updated in the dataset |
| `SOURCE_DATADESC` | Description of the source update batch |

---

## How the WFS query works

This service **requires a POST request with an OGC XML filter body** — GET requests with query parameters are ignored. The filter uses OGC FES 2.0 syntax:

```xml
<wfs:GetFeature service="WFS" version="2.0.0" count="5000">
  <wfs:Query typeNames="structures:USGS_TNM_Structures">
    <fes:Filter>
      <fes:And>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>FType</fes:ValueReference>
          <fes:Literal>800</fes:Literal>
        </fes:PropertyIsEqualTo>
        <fes:PropertyIsEqualTo>
          <fes:ValueReference>STATE</fes:ValueReference>
          <fes:Literal>NY</fes:Literal>
        </fes:PropertyIsEqualTo>
      </fes:And>
    </fes:Filter>
  </wfs:Query>
</wfs:GetFeature>
```

The response is OGC GML — parsed with Python's `xml.etree.ElementTree` and converted to a Polars DataFrame.

---

## What the notebook checks

### 1. NY State overview
Total records fetched per category and a preview of the raw data.

### 2. Completeness check (NY State)
For each key field (`NAME`, `ADDRESS`, `CITY`, `ZIPCODE`, `LOADDATE`), reports:
- How many records have a value
- How many are missing
- Completion percentage

This is important for the thesis: it reveals gaps in the federal SDI data that would need to be filled from other sources.

### 3. NYC filter
Narrows records to NYC boroughs by matching `CITY` against known NYC city names (Brooklyn, Queens, Bronx, Staten Island, New York/Manhattan, and major neighborhoods).

### 4. Distribution by city
Groups NYC records by city name to see how facilities are distributed across boroughs.

### 5. FCode subtypes
Within FType 740 (law enforcement), there are subtypes: police precincts, fire stations, EMS, substations. This breakdown shows what mix of facility types is in the data.

### 6. NYC completeness check
Repeats the completeness check on the NYC-filtered subset — completeness may differ from the statewide picture.

### 7. Missing address detail
Lists specifically which NYC facilities are missing address data — useful for identifying records that can't be geocoded or spatially joined.

### 8. Export
Saves four parquet files to `poc/`:
- `hospitals_ny.parquet` — all NY state hospitals
- `law_enforcement_ny.parquet` — all NY state law enforcement
- `hospitals_nyc.parquet` — NYC-only hospitals
- `law_enforcement_nyc.parquet` — NYC-only law enforcement

---

## Criminology relevance

| Layer | Analytical use |
|---|---|
| Hospitals | Proximity to trauma centers — research links hospital proximity to firearm homicide survival rates. Also used as crime attractors (parking lots, late-night activity). |
| Law enforcement locations | Cross-validate existing police station data, compute coverage/response-time zones, identify coverage gaps. |

Both layers feed into **proximity analysis** — the core of the existing app's comparative and proximity pages.

---

## Limitations

- **No geometry:** The WFS returns point locations as `gml:PointPropertyType` but coordinates were null in tested records. Spatial join requires geocoding addresses or using a different source for coordinates.
- **NYC city names are inconsistent:** NYC records appear under multiple city names (e.g. "New York", "Manhattan", neighborhood names). The notebook covers the most common ones but may miss some.
- **No prisons:** FType 810 is absent from the NY dataset. For correctional facility data, HIFLD (`hifld-geoplatform.hub.arcgis.com`) is the alternative — but that's ArcGIS REST, not OGC WFS.
- **Count is under 5000:** Both categories are well under the 5000-record limit, so a single request retrieves the full dataset.
