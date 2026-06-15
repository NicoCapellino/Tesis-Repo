# Fuentes SDI — Endpoints OGC Activos Verificados (EE.UU.)

Todos los endpoints devuelven XML OGC válido (`WFS_Capabilities` / `WMS_Capabilities`).
Verificados activos en mayo de 2026. Todos forman parte de la NSDI (National Spatial Data Infrastructure).

---

## USGS National Map — carto-wfs.nationalmap.gov (WFS 2.0.0)

### Structures WFS ✓ ACTIVO
Comisarías de policía, hospitales, prisiones, escuelas, estaciones de bomberos.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../structures/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer?request=GetCapabilities&service=WFS)
- FeatureType: `structures:USGS_TNM_Structures`
- Códigos FType: 740 = fuerzas del orden/bomberos, 800 = hospitales, 730 = escuelas, 820 = cementerios

### Transportation WFS ✓ ACTIVO
Rutas, ferroviario, aeropuertos — variables de accesibilidad y teoría de la actividad rutinaria.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../transportation/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/transportation/MapServer/WFSServer?request=GetCapabilities&service=WFS)
- FeatureTypes: `transportation:Interstate`, `transportation:US_Route`, `transportation:State_Route`, `transportation:US_Railroad`, `transportation:Local_Road`, `transportation:Airport`

### Government Units WFS ✓ ACTIVO
Límites administrativos — condados, lugares incorporados, distritos del Congreso, divisiones civiles.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../govunits/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0](https://carto-wfs.nationalmap.gov/arcgis/services/govunits/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0)
- FeatureTypes: `County_or_Equivalent`, `Incorporated_Place`, `Unincorporated_Place`, `Minor_Civil_Division`, `Congressional_District`, `National_Park`, `Military_Reserve`

### Geographic Names WFS ✓ ACTIVO
Lugares con nombre del GNIS — administrativos, de transporte, hidrografía, históricos.
- GetCapabilities: [carto-wfs.nationalmap.gov/.../geonames/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0](https://carto-wfs.nationalmap.gov/arcgis/services/geonames/MapServer/WFSServer?SERVICE=WFS&REQUEST=GetCapabilities&VERSION=2.0.0)

---

## USGS National Map — carto.nationalmap.gov (WMS 1.3.0)

### Government Units WMS ✓ ACTIVO
40 capas: distritos del Congreso, condados, lugares incorporados, divisiones civiles, parques nacionales, reservas militares.
- GetCapabilities: [carto.nationalmap.gov/.../govunits/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/govunits/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

### Structures WMS ✓ ACTIVO
Los mismos datos de infraestructura que el Structures WFS, renderizados como teselas de mapa.
- GetCapabilities: [carto.nationalmap.gov/.../structures/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/structures/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

### Transportation WMS ✓ ACTIVO
- GetCapabilities: [carto.nationalmap.gov/.../transportation/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0](https://carto.nationalmap.gov/arcgis/services/transportation/MapServer/WMSServer?SERVICE=WMS&REQUEST=GetCapabilities&VERSION=1.3.0)

---

## USGS National Map — basemap.nationalmap.gov (WMS 1.3.0)

### Topo Basemap WMS ✓ ACTIVO
- GetCapabilities: [basemap.nationalmap.gov/.../USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://basemap.nationalmap.gov/arcgis/services/USGSTopo/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Hydrography Basemap WMS ✓ ACTIVO
- GetCapabilities: [basemap.nationalmap.gov/.../USGSHydroCached/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://basemap.nationalmap.gov/arcgis/services/USGSHydroCached/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## USGS MRLC — www.mrlc.gov/geoserver (GeoServer real, no ArcGIS)

El único endpoint federal confirmado que ejecuta un GeoServer real (no un adaptador ArcGIS WMSServer).

### NLCD Land Cover WMS ✓ ACTIVO
National Land Cover Database — porcentaje de superficie impermeable, intensidad urbana, cobertura arbórea, clase de cobertura del suelo por año (2001–2021). Variable clave para la criminología ambiental (ventanas rotas, isla de calor, densidad urbana).
- GetCapabilities: [www.mrlc.gov/geoserver/ows?service=WMS&request=GetCapabilities&version=1.3.0](https://www.mrlc.gov/geoserver/ows?service=WMS&request=GetCapabilities&version=1.3.0)
- Capas clave: `mrlc_display:NLCD_2021_Land_Cover_L48`, `mrlc_display:NLCD_2021_Impervious_L48`, `mrlc_display:NLCD_2021_Canopy_L48`

### NLCD WFS ✓ ACTIVO
Capas de referencia vectorial: límites de condados, cuencas hidrográficas HUC8, zonas de mapa.
- GetCapabilities: [www.mrlc.gov/geoserver/ows?service=WFS&request=GetCapabilities&version=2.0.0](https://www.mrlc.gov/geoserver/ows?service=WFS&request=GetCapabilities&version=2.0.0)

---

## Census TIGERweb — tigerweb.geo.census.gov (WMS 1.3.0)

Límites de census tracts y block groups. Solo WMS — no hay WFS disponible.

### ACS 2024 WMS ✓ ACTIVO
- GetCapabilities: [tigerweb.geo.census.gov/.../tigerWMS_ACS2024/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://tigerweb.geo.census.gov/arcgis/services/TIGERweb/tigerWMS_ACS2024/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Tracts & Block Groups WMS ✓ ACTIVO
- GetCapabilities: [tigerweb.geo.census.gov/.../Tracts_Blocks/MapServer/WMSServer?request=GetCapabilities&service=WMS](https://tigerweb.geo.census.gov/arcgis/services/TIGERweb/Tracts_Blocks/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## New York State GIS — gisservices.its.ny.gov (WMS 1.3.0)

Los 5 boroughs de NYC cubiertos. ArcGIS WMSServer = OGC WMS 1.3.0 genuino.

### Civil Boundaries WMS ✓ ACTIVO
Estado, condados, ciudades, pueblos, aldeas.
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Civil_Boundaries/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Civil_Boundaries/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Tax Parcels WMS ✓ ACTIVO
Uso del suelo a nivel de parcela y datos de propiedad (rol de avalúo 2024–2025).
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Tax_Parcels_Public/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Tax_Parcels_Public/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Streets WMS ✓ ACTIVO
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Streets/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Streets/MapServer/WMSServer?request=GetCapabilities&service=WMS)

### Schools WMS ✓ ACTIVO
Escuelas públicas K-12, privadas K-12, charter, universidades, distritos escolares.
- GetCapabilities: [gisservices.its.ny.gov/.../NYS_Schools/MapServer/WMSServer?request=GetCapabilities&service=WMS](http://gisservices.its.ny.gov/arcgis/services/NYS_Schools/MapServer/WMSServer?request=GetCapabilities&service=WMS)

---

## Callejones sin salida (investigados, no compatibles con OGC)

| Fuente | Estado |
|---|---|
| FGDC GeoPlatform WFS/WMS | Completamente fuera de línea — conexión rechazada |
| BTS geodata.bts.gov | Solo REST, sin OGC WFS/WMS |
| GSA FRPP | Solo descarga de archivos planos (CSV/Excel), sin servicio OGC |
| FEMA NFHL WMS | Fallo TLS desde entorno de prueba |
| HUD ArcGIS | Solo FeatureServer, sin WFS/WMS |
| EPA geodata.epa.gov | HTTP 400 en solicitudes WMS |
| DOT geo.dot.gov | HTTP 400 en solicitudes WMS |
| DOJ/FBI | No se encontraron servicios OGC |
| EJSCREEN | Eliminado en febrero de 2025 |
| CEJST | Eliminado en enero de 2025 |

---

## Resumen por Uso en la Tesis

| Capa | Fuente | Estándar | Uso en NYC |
|---|---|---|---|
| Comisarías, hospitales, escuelas, prisiones | USGS Structures WFS | WFS 2.0 | Sí — filtrar STATE='NY' |
| Rutas, ferroviario, aeropuertos | USGS Transportation WFS | WFS 2.0 | Sí |
| Condados, lugares, distritos del Congreso | USGS Govunits WFS | WFS 2.0 | Sí |
| Cobertura del suelo, superficie impermeable (densidad urbana) | MRLC NLCD WMS | WMS 1.3 | Sí — recortar al bounding box de NYC |
| Límites de census tract / block group | TIGERweb WMS | WMS 1.3 | Sí |
| Uso del suelo a nivel de parcela | NYS Tax Parcels WMS | WMS 1.3 | Sí — los 5 boroughs |
| Red vial | NYS Streets WMS | WMS 1.3 | Sí |
| Escuelas (nivel estatal) | NYS Schools WMS | WMS 1.3 | Sí |
| Límites administrativos | NYS Civil Boundaries WMS | WMS 1.3 | Sí |
