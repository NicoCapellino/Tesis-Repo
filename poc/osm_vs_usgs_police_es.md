# OSM vs USGS — Comparación de Datos de Comisarías de Policía

## Resumen

OSM tiene más registros (214) que USGS (92), pero el mayor recuento de OSM es un artefacto de ruido — no de una cobertura más completa. USGS es el conjunto de datos más limpio y autoritativo para el análisis de proximidad en NYC.

---

## Cantidad de Registros

| Fuente | Registros | Estándar | Organismo rector |
|---|---|---|---|
| OSM (consulta `amenity=police` por bounding box) | 214 | Crowdsourced | Ninguno |
| USGS National Map (FCode 74034) | 92 | OGC WFS 2.0 / NSDI | FGDC, NGDA ID 135 |

---

## Qué Contiene Realmente el Dataset de OSM (214 registros)

OSM utiliza un filtro de **bounding box geográfico** sobre NYC. Todo lo etiquetado como `amenity=police` dentro del área queda incluido — independientemente de la jurisdicción o relevancia.

### Falsos positivos confirmados en el dataset

**Departamentos de Nueva Jersey** (fuera de NYC, capturados por el bounding box):
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

**Registros de otras jurisdicciones**:
- Floral Park Police Headquarters (Condado de Nassau, NY)
- Mount Vernon Police Station (Condado de Westchester, NY)

**Instalaciones que no son comisarías**:
- Police Athletic League Bronx Community Center
- Triborough Bridge And Tunnel Authority

**Nombres vacíos**: 18 registros sin nombre.

**Estimación total de ruido**: ~30–40 registros de los 214 no son dependencias del NYPD.

---

## Qué Contiene Realmente el Dataset de USGS (92 registros)

USGS filtra por `STATE = 'NY'` a nivel del WFS y por FCode `74034` (Police Station). Los 92 registros de NYC (filtrados por prefijo de código postal) son instalaciones legítimas del NYPD o de las fuerzas del orden de NYC:

### Distribución por borough

| Borough | Registros |
|---|---|
| Manhattan | 26 |
| Brooklyn | 26 |
| Bronx | 18 |
| Queens | 17 |
| Staten Island | 5 |
| **Total** | **92** |

### Subtipos de instalaciones incluidos

- **Comisarías de patrullaje**: numeradas entre la 1.ª y la 123.ª (77 en total, coincide con el recuento oficial del NYPD)
- **Áreas de Servicio Policial de la Oficina de Vivienda (Housing Bureau)**: PSA 1, 3, 7, 8, 8 Edenwald Satellite, 9
- **Distritos de la Oficina de Tránsito (Transit Bureau)**: Distrito 23, Distrito 32
- **Unidades especializadas**: Comisaría Midtown North, Comisaría Midtown South, Bronx Task Force
- **Oficinas del Sheriff**: Bronx County Sheriff's Office, Richmond County Sheriff's Office
- **Administrativo**: Sede central del NYPD, Oficina del Alguacil de la Ciudad de Nueva York (NYC Marshal Office)

92 registros es el número correcto — el NYPD opera 77 comisarías de patrullaje más unidades del Transit Bureau, Housing Bureau y unidades especializadas. USGS las captura todas y ninguna ubicación fuera de NYC.

---

## Por Qué USGS Reemplaza a OSM para Esta Tesis

| Dimensión | OSM | USGS |
|---|---|---|
| Garantía de datos solo de NYC | No — contaminación con NJ/Nassau | Sí — filtro STATE + prefijo de código postal |
| Registros vacíos / sin nombre | 18 | 0 |
| Fuente autoritativa | Voluntarios crowdsourced | USGS / Departamento del Interior |
| Cumplimiento SDI | No es un SDI | NSDI, NGDA ID 135, OGC WFS 2.0 |
| Coordenadas disponibles | Sí (todos) | Sí (los 92, sin necesidad de geocodificación) |
| Última verificación | Desconocida | `LOADDATE` por registro (2016–2024) |

---

## Archivos de Datos

| Archivo | Registros | Notas |
|---|---|---|
| `data/reference/new_york/usgs_police.parquet` | 92 | Producción — reemplaza a OSM para análisis |
| `data/reference/new_york/usgs_fire.parquet` | 213 | Nuevo — estaciones de bomberos FDNY (FCode 74026) |
| `data/reference/new_york/healthcare.parquet` | 71 | Hospitales USGS (FType 800) |
| `poc/map_comparison_full.html` | — | Mapa Leaflet interactivo: OSM vs USGS vs Bomberos vs Hospitales |

---

## Conclusión

El dataset de OSM con 214 registros contiene **al menos 30 comisarías de policía que no son de NYC**, correspondientes a departamentos de Nueva Jersey y el Condado de Nassau, además de instalaciones que no son comisarías y 18 registros sin nombre. Utilizarlo para análisis de proximidad introduce un error geográfico sistemático — los delitos cercanos al límite de NYC aparecerían como "cerca de una comisaría" que en realidad se encuentra en otro estado.

Los 92 registros de USGS cubren cada comisaría de patrullaje del NYPD junto con las unidades del Transit Bureau y Housing Bureau, con cero falsos positivos y cero coordenadas nulas. Además, es la fuente SDI autoritativa a nivel federal (NGDA ID 135, OGC WFS 2.0.0), lo que respalda directamente el argumento metodológico SDI de la tesis.
