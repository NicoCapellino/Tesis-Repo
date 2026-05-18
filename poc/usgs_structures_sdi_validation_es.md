# Por qué esto es SDI/NSDI — USGS Structures WFS

## Qué se obtuvo

Ubicaciones de hospitales, servicios de emergencia y fuerzas del orden para la ciudad de Nueva York, a través de:
```
https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
```

Este es un endpoint **OGC WFS 2.0.0**. Se verificó que devolvía una respuesta XML `<wfs:WFS_Capabilities>` válida durante la sesión del POC. Al 18 de mayo de 2026, el servicio retornó capacidades WFS válidas y datos de entidades correctamente. El script del POC se ejecutó con éxito, produciendo 71 hospitales y 305 registros de servicios de emergencia y fuerzas del orden. El servicio mostró disponibilidad intermitente en verificaciones posteriores, incluyendo respuestas 504. No se identificó ningún SLA para este endpoint.

---

## La cadena SDI — evidencia institucional

### 1. FGDC — El organismo rector

El **Federal Geographic Data Committee (FGDC)** es el organismo interagencial establecido por la **Circular A-16 de la Oficina de Gestión y Presupuesto (OMB)** para coordinar los datos geoespaciales federales y liderar la NSDI. El FGDC gestiona el portafolio NGDA bajo los procesos de la Circular A-16 de la OMB y la Ley de Datos Geoespaciales (Geospatial Data Act), mediante los cuales los conjuntos de datos son designados como **National Geospatial Data Assets (NGDAs)**.

> "The NSDI provides the technology, policies, criteria, standards, and employees necessary to promote geospatial data sharing throughout the Federal, State, Tribal, and local governments, and the private sector."

> *(La NSDI provee la tecnología, políticas, criterios, estándares y personal necesarios para promover el intercambio de datos geoespaciales entre los gobiernos federales, estatales, tribales y locales, y el sector privado.)*

- Descripción general de la NSDI del FGDC: [www.fgdc.gov/nsdi/nsdi.html](https://www.fgdc.gov/nsdi/nsdi.html)
- Temas y conjuntos de datos NGDA del FGDC: [www.fgdc.gov/what-we-do/manage-federal-geospatial-resources/a-16-portfolio-management/ngda-themes-and-datasets](https://www.fgdc.gov/what-we-do/manage-federal-geospatial-resources/a-16-portfolio-management/ngda-themes-and-datasets)

---

### 2. USGS National Map — el productor de datos

El **USGS National Map** es el programa federal que produce y mantiene el conjunto de datos de Estructuras. Está explícitamente descripto como una implementación clave de la NSDI:

> "NGTOC provides geospatial technical expertise in support of the National Geospatial Program in its development of The National Map... and implementation of key components of the National Spatial Data Infrastructure (NSDI)."

— USGS Fact Sheet 2009-3017, National Geospatial Technical Operations Center

- Programa USGS National Map: [www.usgs.gov/programs/national-geospatial-program/national-map](https://www.usgs.gov/programs/national-geospatial-program/national-map)
- USGS + NSDI (cita directa): [pubs.usgs.gov/publication/fs20093017](https://pubs.usgs.gov/publication/fs20093017)

---

### 3. Designación NGDA — entrada oficial en el registro

El USGS National Structures Dataset está registrado oficialmente como **NGDA ID 135** bajo el tema **Real Property NGDA**. Esta es su entrada en el portafolio de datos geoespaciales federales mandatado por la Circular A-16 de la OMB.

- Entrada en el Catálogo de Datos Científicos del USGS (NGDAID 135): [data.usgs.gov/datacatalog/data/USGS:db4fb1b6-1282-4e5b-9866-87a68912c5d1](https://data.usgs.gov/datacatalog/data/USGS:db4fb1b6-1282-4e5b-9866-87a68912c5d1)
- Espejo en data.gov: [catalog.data.gov/dataset/usgs-national-structures-dataset-usgs-national-map-downloadable-data-collection](https://catalog.data.gov/dataset/usgs-national-structures-dataset-usgs-national-map-downloadable-data-collection)
- Registro del portafolio NGDA (NGDAID 135): [ngda-portfolio-community-geoplatform.hub.arcgis.com/datasets/534b02ebedcd4c9ab69f0db42fd77bc6/about](https://ngda-portfolio-community-geoplatform.hub.arcgis.com/datasets/534b02ebedcd4c9ab69f0db42fd77bc6/about)
- Hub del tema NGDA Real Property: [ngda-real-property-geoplatform.hub.arcgis.com](https://ngda-real-property-geoplatform.hub.arcgis.com/)
- Catálogo ScienceBase: [www.sciencebase.gov/catalog/item/4f70b240e4b058caae3f8e1b](https://www.sciencebase.gov/catalog/item/4f70b240e4b058caae3f8e1b)

---

### 4. Estándar de datos — FGDC-STD-019-2014

El tema NGDA Real Property está asociado con el **Real Property Asset Data Standard (RPADS)**, formalmente respaldado por el FGDC. RPADS es un estándar más amplio de gestión de activos inmobiliarios que cubre el inventario de activos federales. Los valores específicos de FType y FCode utilizados en este POC están definidos por la **especificación de contenido de Estructuras del USGS National Map**, no por RPADS directamente.

- Estándar FGDC RPADS: [www.fgdc.gov/standards/projects/RPADS/RPADS_final/view](https://www.fgdc.gov/standards/projects/RPADS/RPADS_final/view)
- Especificación de contenido de Estructuras (definiciones de FType/FCode): [www.usgs.gov/ngp-standards-and-specifications/national-map-structures-content](https://www.usgs.gov/ngp-standards-and-specifications/national-map-structures-content)

---

### 5. Estándares OGC — la capa de interoperabilidad

El servicio responde a solicitudes estándar **OGC WFS 2.0.0**. El uso de estándares OGC constituye la capa de interoperabilidad de la cadena SDI — el estatus SDI en su conjunto proviene de la gobernanza, la custodia autoritativa, los metadatos, los estándares y los servicios en conjunto. Esto no implica una certificación OGC formal del servicio en sí:

- Las herramientas y bibliotecas compatibles con OGC (QGIS, Python OWSLib, almacenes de datos de GeoServer, etc.) deberían poder consultarlo sin integración personalizada cuando el servicio esté disponible
- La respuesta `GetCapabilities` documenta el contrato del servicio en un formato estandarizado y legible por máquinas
- Los datos se filtran y devuelven usando predicados **OGC FES 2.0** (Filter Encoding Standard)

URL de `GetCapabilities` (disponibilidad intermitente — devolvió 504 en verificaciones posteriores a la sesión del POC):
[carto-wfs.nationalmap.gov/.../structures/MapServer/WFSServer?request=GetCapabilities&service=WFS](https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer?request=GetCapabilities&service=WFS)

Metadatos del servicio REST (códigos FType, campos, cobertura):
[carto.nationalmap.gov/arcgis/rest/services/structures/mapserver](https://carto.nationalmap.gov/arcgis/rest/services/structures/mapserver)

---

## Códigos FType utilizados en este POC

| FType | Categoría | Registros en NYC |
|---|---|---|
| 800 | Salud y Medicina (Hospitales / Centros Médicos) | 71 |
| 740 | Respuesta de Emergencia y Fuerzas del Orden | 305 |

Los recuentos de registros provienen de la salida del POC (`poc/output`) — no de los metadatos del servicio. El esquema FType/FCode es visible en las capas de entidades individuales:
- Hospitales (FType 800): [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/49](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/49)
- FType 740 incluye múltiples subtipos. En la salida de este POC, los 305 registros de NYC se dividen en Comisarías de Policía (FCode 74034, capa 53) y Estaciones de Bomberos (FCode 74026, capa 51). Vincular solo a la capa 53 representa un ejemplo de un subtipo:
  - Comisarías de Policía (FCode 74034): [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/53](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/53)
  - Estaciones de Bomberos (FCode 74026): [carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/51](https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/51)

---

## Lista de verificación de evidencia SDI/NSDI

Esta lista sustenta el argumento de que *este POC consume un activo de datos NSDI/SDI autoritativo a través de estándares de servicio geoespacial interoperable.* SDI no es una certificación de aprobación/rechazo binaria — la tabla a continuación presenta la cadena de evidencia, no un veredicto de cumplimiento binario.

| Dimensión SDI/NSDI | Evidencia |
|---|---|
| Productor autoritativo | USGS / Departamento del Interior |
| Mandato federal | Circular A-16 de la OMB, designación NGDA |
| Validación del organismo rector | FGDC, NGDAID 135 |
| Estándar de datos abiertos | FGDC-STD-019-2014 (RPADS) + especificación de contenido de Estructuras USGS |
| Estándares OGC (interoperabilidad) | OGC WFS 2.0.0, OGC FES 2.0 |
| Metadatos descubribles | ScienceBase, data.gov, Catálogo de Datos Científicos del USGS |
| Capacidades legibles por máquina | GetCapabilities XML — HTTP 200, verificado el 18 de mayo de 2026 |

---

## Advertencias

Esto valida la fuente y el servicio como parte del ecosistema NSDI de EE.UU. No prueba:

- **Completitud del subconjunto de NYC** — los registros se filtran por prefijo de código postal (100–104, 112–114, 116). Esto excluye el prefijo `111`, que cubre partes del oeste de Queens, incluyendo Astoria y Long Island City. Otros rangos de códigos postales válidos de NYC que no estén en esta lista también podrían estar ausentes. La cobertura debe verificarse contra una referencia completa de códigos postales de NYC antes de sacar conclusiones sobre completitud espacial
- **Precisión posicional** — la validación del análisis de geometría no se realizó en la salida original del POC; el WFS en producción sí devuelve coordenadas de puntos GML (por ejemplo, `<gml:pos>40.64638524 -74.02039945</gml:pos>`), pero la precisión posicional respecto a datos de referencia no ha sido verificada
- **Actualidad de los datos** — los metadatos del servicio REST indican que los datos fueron actualizados por última vez en abril de 2026; los registros individuales llevan su propio `LOADDATE`
- **Disponibilidad garantizada del servicio** — el endpoint WFS devolvió 504 en al menos una verificación durante el período del POC; no se identificó ningún SLA para este endpoint
