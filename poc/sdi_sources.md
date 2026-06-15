# SDI Data Sources — Verified Live US OGC Endpoints

All endpoints return valid OGC XML (`WFS_Capabilities` / `WMS_Capabilities`).
Verified live May 2026. All are part of NSDI (National Spatial Data Infrastructure).

---

## USGS National Map — carto-wfs.nationalmap.gov (WFS 2.0.0)

### Structures WFS ✓ LIVE
Police stations, hospitals, prisons, schools, fire stations.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../structures/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer?request=GetCapabilities&service=WFS)
- FeatureType: `structures:USGS_TNM_Structures`
- FType codes: 740 = law enforcement/fire, 800 = hospitals, 730 = schools, 820 = cemeteries

### Transportation WFS ✓ LIVE
Roads, rail, airports — accessibility and routine activity theory variables.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../transportation/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/transportation/MapServer/WFSServer?request=GetCapabilities&service=WFS)
- FeatureTypes: `transportation:Interstate`, `transportation:US_Route`, `transportation:State_Route`, `transportation:US_Railroad`, `transportation:Local_Road`, `transportation:Airport`

### Government Units WFS ✓ LIVE
Administrative boundaries — counties, incorporated places, congressional districts, civil divisions.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../govunits/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0](https://carto-wfs.nationalmap.gov/arcgis/services/govunits/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0)
- FeatureTypes: `County_or_Equivalent`, `Incorporated_Place`, `Unincorporated_Place`, `Minor_Civil_Division`, `Congressional_District`, `National_Park`, `Military_Reserve`

### Geographic Names WFS ✓ LIVE
GNIS named places — administrative, transportation, hydrography, historical.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../geonames/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0](https://carto-wfs.nationalmap.gov/arcgis/services/geonames/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0)

---

## USGS National Map — carto.nationalmap.gov (WMS 1.3.0)

### Government Units WMS ✓ LIVE
40 layers: congressional districts, counties, incorporated places, civil divisions, national parks, military reserves.
- GetCapabilities: [carto.nationalmap.gov/.../govunits/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/govunits/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

### Structures WMS ✓ LIVE
Same infrastructure data as Structures WFS, rendered as map tiles.
- GetCapabilities: [carto.nationalmap.gov/.../structures/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/structures/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

### Transportation WMS ✓ LIVE
- GetCapabilities: [carto.nationalmap.gov/.../transportation/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/transportation/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

---

## USGS National Map — basemap.nationalmap.gov (WMS 1.3.0)

### Topo Basemap WMS ✓ LIVE
- GetCapabilities: [basemap.nationalmap.gov/.../USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://basemap.nationalmap.gov/arcgis/services/USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Hydrography Basemap WMS ✓ LIVE
- GetCapabilities: [basemap.nationalmap.gov/.../USGSHydroCached/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://basemap.nationalmap.gov/arcgis/services/USGSHydroCached/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## USGS MRLC — www.mrlc.gov/geoserver (Real GeoServer, not ArcGIS)

The only confirmed federal endpoint running a real GeoServer (not ArcGIS WMSServer adapter).

### NLCD Land Cover WMS ✓ LIVE
National Land Cover Database — impervious surface %, urban intensity, tree canopy, land cover class by year (2001–2021). Key variable for environmental criminology (broken windows, heat island, urban density).
- GetCapabilities: [www.mrlc.gov/geoserver/ows?service=WMS&request=GetCapabilities&version=1.3.0](https://www.mrlc.gov/geoserver/ows?service=WMS&request=GetCapabilities&version=1.3.0)
- Key layers: `mrlc_display:NLCD_2021_Land_Cover_L48`, `mrlc_display:NLCD_2021_Impervious_L48`, `mrlc_display:NLCD_2021_Canopy_L48`

### NLCD WFS ✓ LIVE
Vector reference layers: county boundaries, HUC8 watersheds, map zones.
- GetCapabilities: [www.mrlc.gov/geoserver/ows?service=WFS&request=GetCapabilities&version=2.0.0](https://www.mrlc.gov/geoserver/ows?service=WFS&request=GetCapabilities&version=2.0.0)

---

## Census TIGERweb — tigerweb.geo.census.gov (WMS 1.3.0)

Census tract and block group boundaries. WMS only — no WFS available.

### ACS 2024 WMS ✓ LIVE
- GetCapabilities: [tigerweb.geo.census.gov/.../tigerWMS_ACS2024/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://tigerweb.geo.census.gov/arcgis/services/TIGERweb/tigerWMS_ACS2024/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Tracts & Block Groups WMS ✓ LIVE
- GetCapabilities: [tigerweb.geo.census.gov/.../Tracts_Blocks/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://tigerweb.geo.census.gov/arcgis/services/TIGERweb/Tracts_Blocks/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## New York State GIS — gisservices.its.ny.gov (WMS 1.3.0)

All 5 NYC boroughs covered. ArcGIS WMSServer = genuine OGC WMS 1.3.0.

### Civil Boundaries WMS ✓ LIVE
State, counties, cities, towns, villages.
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Civil_Boundaries/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Civil_Boundaries/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Tax Parcels WMS ✓ LIVE
Parcel-level land use type and property data (2024–2025 assessment roll).
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Tax_Parcels_Public/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Tax_Parcels_Public/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Streets WMS ✓ LIVE
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Streets/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Streets/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Schools WMS ✓ LIVE
Public K-12, private K-12, charter schools, colleges, school districts.
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Schools/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Schools/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## Dead Ends (investigated, not OGC-compliant)

| Source | Status |
|---|---|
| FGDC GeoPlatform WFS/WMS | Fully offline — connection refused |
| BTS geodata.bts.gov | REST only, no OGC WFS/WMS |
| GSA FRPP | Flat file download only (CSV/Excel), no OGC service |
| FEMA NFHL WMS | TLS failure from test environment |
| HUD ArcGIS | FeatureServer only, no WFS/WMS |
| EPA geodata.epa.gov | HTTP 400 on WMS requests |
| DOT geo.dot.gov | HTTP 400 on WMS requests |
| DOJ/FBI | No OGC services found |
| EJSCREEN | Removed February 2025 |
| CEJST | Removed January 2025 |

---

## Summary by Thesis Use

| Layer | Source | Standard | NYC Use |
|---|---|---|---|
| Police stations, hospitals, schools, prisons | USGS Structures WFS | WFS 2.0 | Yes — filter STATE='NY' |
| Roads, rail, airports | USGS Transportation WFS | WFS 2.0 | Yes |
| Counties, places, congressional districts | USGS Govunits WFS | WFS 2.0 | Yes |
| Land cover, impervious surface (urban density) | MRLC NLCD WMS | WMS 1.3 | Yes — clip to NYC bbox |
| Census tract / block group boundaries | TIGERweb WMS | WMS 1.3 | Yes |
| Parcel-level land use | NYS Tax Parcels WMS | WMS 1.3 | Yes — all 5 boroughs |
| Street network | NYS Streets WMS | WMS 1.3 | Yes |
| Schools (state-level) | NYS Schools WMS | WMS 1.3 | Yes |
| Admin boundaries | NYS Civil Boundaries WMS | WMS 1.3 | Yes |
