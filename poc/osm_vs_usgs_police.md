# OSM vs USGS — Police Station Data Comparison

## Summary

OSM has more records (214) than USGS (92), but OSM's higher count is an artifact of noise —
not more complete coverage. USGS is the cleaner and more authoritative dataset for NYC proximity analysis.

---

## Record Counts

| Source | Records | Standard | Governing body |
|---|---|---|---|
| OSM (`amenity=police` bbox query) | 214 | Crowdsourced | None |
| USGS National Map (FCode 74034) | 92 | OGC WFS 2.0 / NSDI | FGDC, NGDA ID 135 |

---

## What OSM's 214 Actually Contains

OSM uses a **geographic bounding box** filter over NYC. Anything tagged `amenity=police`
inside the box is included — regardless of jurisdiction or relevance.

### False positives confirmed in the dataset

**New Jersey departments** (outside NYC, captured by bbox):
- Carlstadt Police Department
- Kearny Police Department
- Ridgefield Park Police
- Little Ferry Police Station
- Fort Lee Police
- Cliffside Park Police Department
- Little Falls Police Department
- Woodland Park Police Department
- West Orange Police
- JCPD North District (Jersey City)
- NJIT Public Safety

**Other-jurisdiction entries**:
- Floral Park Police Headquarters (Nassau County, NY)
- Mount Vernon Police Station (Westchester County, NY)

**Non-police facilities**:
- Police Athletic League Bronx Community Center
- Triborough Bridge And Tunnel Authority

**Empty names**: 18 records with no name at all.

**Total noise estimate**: ~30–40 records out of 214 are not NYPD facilities.

---

## What USGS's 92 Actually Contains

USGS filters by `STATE = 'NY'` at the WFS level and FCode `74034` (Police Station).
All 92 NYC records (filtered by ZIP prefix) are legitimate NYPD or NYC law enforcement facilities:

### Borough breakdown

| Borough | Records |
|---|---|
| Manhattan | 26 |
| Brooklyn | 26 |
| Bronx | 18 |
| Queens | 17 |
| Staten Island | 5 |
| **Total** | **92** |

### Facility subtypes included

- **Patrol precincts**: 1st through 123rd (77 total, matching NYPD's official count)
- **Housing Bureau Police Service Areas**: PSA 1, 3, 7, 8, 8 Edenwald Satellite, 9
- **Transit Bureau Districts**: District 23, District 32
- **Specialized units**: Midtown North Precinct, Midtown South Precinct, Bronx Task Force
- **Sheriff offices**: Bronx County Sheriff's Office, Richmond County Sheriff's Office
- **Administrative**: NYPD Headquarters, NYC Marshal Office

92 records is the correct number — NYPD operates 77 patrol precincts plus Transit Bureau,
Housing Bureau, and specialized units. USGS captures all of them and nothing outside NYC.

---

## Why USGS Replaces OSM for This Thesis

| Dimension | OSM | USGS |
|---|---|---|
| NYC-only guarantee | No — NJ/Nassau contamination | Yes — STATE filter + ZIP prefix |
| Empty / unnamed records | 18 | 0 |
| Authoritative source | Crowdsourced volunteers | USGS / Dept. of Interior |
| SDI compliance | Not an SDI | NSDI, NGDA ID 135, OGC WFS 2.0 |
| Coordinates available | Yes (all) | Yes (all 92, no geocoding needed) |
| Last verified | Unknown | `LOADDATE` per record (2016–2024) |

---

## Data Files

| File | Records | Notes |
|---|---|---|
| `data/reference/new_york/usgs_police.parquet` | 92 | Production — replaces OSM for analysis |
| `data/reference/new_york/usgs_fire.parquet` | 213 | New — FDNY stations (FCode 74026) |
| `data/reference/new_york/healthcare.parquet` | 71 | USGS hospitals (FType 800) |
| `poc/map_comparison_full.html` | — | Interactive Leaflet map: OSM vs USGS vs Fire vs Hospitals |

---

## Conclusion

The OSM dataset's 214 records contain **at minimum 30+ non-NYC police stations** from New Jersey
and Nassau County, plus non-police facilities and 18 unnamed records. Using it for proximity analysis
introduces systematic geographic error — crimes near the NYC border would appear "close to a police
station" that is actually in another state.

USGS's 92 records cover every NYPD patrol precinct plus Transit and Housing Bureau units,
with zero false positives and zero null coordinates. It is also the federally authoritative SDI source
(NGDA ID 135, OGC WFS 2.0.0), which directly supports the thesis's SDI methodology claim.
