# Why This is SDI/NSDI — USGS Structures WFS

## What was fetched

Hospitals and emergency response and law enforcement locations for New York City via:
```
https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
```

This is an **OGC WFS 2.0.0** endpoint. It was verified returning a valid `<wfs:WFS_Capabilities>` XML response during the POC session (May 2026), and the POC script ran successfully against it producing 71 hospitals and 305 emergency response and law enforcement records. It has shown intermittent availability in subsequent checks, including 504 responses, but currently returns valid WFS capabilities. Federal WFS services do not guarantee uptime.

---

## The SDI chain — who validates this

### 1. FGDC — The governing body

The **Federal Geographic Data Committee (FGDC)** is the interagency body established by the **Office of Management and Budget (OMB) Circular A-16** to coordinate federal geospatial data and lead the NSDI. It is the authority that designates which datasets qualify as **National Geospatial Data Assets (NGDAs)**.

> "The NSDI provides the technology, policies, criteria, standards, and employees necessary to promote geospatial data sharing throughout the Federal, State, Tribal, and local governments, and the private sector."

- FGDC NSDI overview: [www.fgdc.gov/nsdi/nsdi.html](https://www.fgdc.gov/nsdi/nsdi.html)
- FGDC NGDA themes & datasets: [www.fgdc.gov/what-we-do/manage-federal-geospatial-resources/a-16-portfolio-management/ngda-themes-and-datasets](https://www.fgdc.gov/what-we-do/manage-federal-geospatial-resources/a-16-portfolio-management/ngda-themes-and-datasets)

---

### 2. USGS National Map — the data producer

The **USGS National Map** is the federal program that produces and maintains the Structures dataset. It is explicitly described as a key implementation of the NSDI:

> "NGTOC provides geospatial technical expertise in support of the National Geospatial Program in its development of The National Map... and implementation of key components of the National Spatial Data Infrastructure (NSDI)."

— USGS Fact Sheet 2009-3017, National Geospatial Technical Operations Center

- USGS National Map program: [www.usgs.gov/programs/national-geospatial-program/national-map](https://www.usgs.gov/programs/national-geospatial-program/national-map)
- USGS + NSDI (direct citation): [pubs.usgs.gov/publication/fs20093017](https://pubs.usgs.gov/publication/fs20093017)

---

### 3. NGDA designation — official registry entry

The USGS National Structures Dataset is officially registered as **NGDA ID 135** under the **Real Property NGDA theme**. This is its entry in the federal geospatial data portfolio mandated by OMB A-16.

- USGS Science Data Catalog entry (NGDAID 135): [data.usgs.gov/datacatalog/data/USGS:db4fb1b6-1282-4e5b-9866-87a68912c5d1](https://data.usgs.gov/datacatalog/data/USGS:db4fb1b6-1282-4e5b-9866-87a68912c5d1)
- data.gov mirror: [catalog.data.gov/dataset/usgs-national-structures-dataset-usgs-national-map-downloadable-data-collection](https://catalog.data.gov/dataset/usgs-national-structures-dataset-usgs-national-map-downloadable-data-collection)
- NGDA portfolio registry (NGDAID 135): [ngda-portfolio-community-geoplatform.hub.arcgis.com/datasets/534b02ebedcd4c9ab69f0db42fd77bc6/about](https://ngda-portfolio-community-geoplatform.hub.arcgis.com/datasets/534b02ebedcd4c9ab69f0db42fd77bc6/about)
- NGDA Real Property theme hub: [ngda-real-property-geoplatform.hub.arcgis.com](https://ngda-real-property-geoplatform.hub.arcgis.com/)
- ScienceBase catalog: [www.sciencebase.gov/catalog/item/4f70b240e4b058caae3f8e1b](https://www.sciencebase.gov/catalog/item/4f70b240e4b058caae3f8e1b)

---

### 4. Data standard — FGDC-STD-019-2014

The Real Property NGDA theme is governed by the **Real Property Asset Data Standard (RPADS)**, formally endorsed by FGDC. RPADS is a broader real property management standard covering federal asset inventory. The specific FType and FCode values used in this POC are defined by the **USGS National Map Structures content specification**, not RPADS directly.

- FGDC RPADS standard: [www.fgdc.gov/standards/projects/RPADS/RPADS_final/view](https://www.fgdc.gov/standards/projects/RPADS/RPADS_final/view)
- Structures content specification (FType/FCode definitions): [www.usgs.gov/ngp-standards-and-specifications/national-map-structures-content](https://www.usgs.gov/ngp-standards-and-specifications/national-map-structures-content)

---

### 5. OGC compliance — the interoperability layer

The service responds to standard **OGC WFS 2.0.0** requests. OGC compliance is the interoperability layer of the SDI chain — SDI status as a whole comes from governance, authoritative stewardship, metadata, standards, and services together:

- OGC-compliant clients (QGIS, GeoServer, Python OWSLib, etc.) should be able to query it without custom integration when the service is available
- The `GetCapabilities` response documents the service contract in a machine-readable, standardized format
- Data is filtered and returned using **OGC FES 2.0** (Filter Encoding Standard) predicates

`GetCapabilities` URL (intermittent availability — returned 504 on subsequent checks after POC session):
[carto-wfs.nationalmap.gov/.../structures/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer?request=GetCapabilities&service=WFS)

REST service metadata (FType codes, fields, coverage):
[carto.nationalmap.gov/arcgis/rest/services/structures/mapserver](https://carto.nationalmap.gov/arcgis/rest/services/structures/mapserver)

---

## FType codes used in this POC

| FType | Category | NYC records |
|---|---|---|
| 800 | Health and Medical (hospitals) | 71 |
| 740 | Emergency Response and Law Enforcement | 305 |

Record counts come from the POC query output (`poc/ouput`) — not from service metadata. The FType/FCode schema is visible on individual feature layers:
- Hospitals (FType 800): [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/49](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/49)
- Police Stations / FType 740 schema: [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/53](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/53)

---

## SDI/NSDI evidence checklist

This checklist supports the claim: *this POC consumes an authoritative NSDI/SDI data asset through interoperable geospatial service standards.* SDI is not a single pass/fail certification — the table below presents the chain of evidence, not a binary compliance verdict.

| SDI/NSDI dimension | Evidence |
|---|---|
| Authoritative producer | USGS / Department of the Interior |
| Federal mandate | OMB Circular A-16, NGDA designation |
| Governing body validation | FGDC, NGDAID 135 |
| Open data standard | FGDC-STD-019-2014 (RPADS) + USGS Structures content specification |
| Interoperable service | OGC WFS 2.0.0, OGC FES 2.0 |
| Discoverable metadata | ScienceBase, data.gov, USGS Science Data Catalog |
| Machine-readable capabilities | GetCapabilities XML — HTTP 200, verified May 18 2026 |

---

## Caveats

This validates the source and service as part of the U.S. NSDI ecosystem. It does not prove:

- **NYC subset completeness** — only records with NYC-range ZIP codes were retrieved; coverage gaps may exist
- **Positional accuracy** — geometries were null in the WFS response; coordinates are not verified
- **Real-time freshness** — REST service metadata states data was last refreshed April 2026; individual records carry their own `LOADDATE`
- **Guaranteed service uptime** — the WFS endpoint returned 504 in at least one check during the POC period; federal services do not guarantee SLA
