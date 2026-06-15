# USGS Structures WFS — Explicación del POC

## ¿Qué es esto?

Este POC obtiene datos de ubicación de hospitales y fuerzas del orden para Nueva York desde el **USGS National Map**, utilizando un servicio OGC WFS 2.0 genuino — sin descargas de archivos planos, sin ArcGIS REST. Este es el enfoque SDI: un servicio interoperable estandarizado consumido de forma programática.

**Endpoint del servicio:**
```
https://carto-wfs.nationalmap.gov/arcgis/services/structures/MapServer/WFSServer
```

---

## ¿Por qué esta fuente?

La capa de Estructuras del USGS forma parte de la **NSDI (National Spatial Data Infrastructure)** — datos gubernamentales autoritativos, mantenidos por el USGS y publicados a través de un WFS compatible con OGC. Esto reemplaza los datos de OpenStreetMap utilizados actualmente en la aplicación, que son de contribución comunitaria y no son autoritativos.

Para una tesis de criminología, la distinción importa: los hospitales y comisarías de OSM son de origen colaborativo. Las estructuras del USGS son datos federales verificados.

---

## Datos obtenidos

| FType | Categoría | Total estado de NY |
|---|---|---|
| 800 | Hospitales / Centros Médicos | 236 |
| 740 | Fuerzas del Orden y Estaciones de Bomberos | ~400+ |

**Nota sobre prisiones:** FType 810 (Instalaciones Correccionales) no devolvió registros para NY. Las prisiones no están actualmente incluidas en el dataset de Estructuras del USGS para el estado de Nueva York.

### Campos disponibles

| Campo | Descripción |
|---|---|
| `NAME` | Nombre de la instalación |
| `FType` | Código de tipo de feature (800 = hospital, 740 = fuerzas del orden) |
| `FCode` | Código de subtipo (p. ej. 80012 = edificio hospitalario) |
| `ADDRESS` | Dirección postal |
| `CITY` | Nombre de la ciudad |
| `STATE` | Abreviatura del estado |
| `ZIPCODE` | Código postal |
| `LOADDATE` | Fecha en que el registro fue actualizado por última vez en el dataset |
| `SOURCE_DATADESC` | Descripción del lote de actualización de la fuente |

---

## Cómo funciona la consulta WFS

Este servicio **requiere una solicitud POST con un cuerpo de filtro XML OGC** — las solicitudes GET con parámetros de consulta son ignoradas. El filtro utiliza la sintaxis OGC FES 2.0:

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

La respuesta es OGC GML — procesada con `xml.etree.ElementTree` de Python y convertida a un DataFrame de Polars.

---

## Qué verifica el notebook

### 1. Descripción general del estado de NY
Total de registros obtenidos por categoría y una vista previa de los datos en bruto.

### 2. Verificación de completitud (estado de NY)
Para cada campo clave (`NAME`, `ADDRESS`, `CITY`, `ZIPCODE`, `LOADDATE`), se informa:
- Cuántos registros tienen valor
- Cuántos están ausentes
- Porcentaje de completitud

Esto es importante para la tesis: revela las brechas en los datos SDI federales que deberían completarse desde otras fuentes.

### 3. Filtro de NYC
Acota los registros a los boroughs de NYC cruzando `CITY` con nombres de ciudades conocidos de NYC (Brooklyn, Queens, Bronx, Staten Island, Nueva York/Manhattan y los principales barrios).

### 4. Distribución por ciudad
Agrupa los registros de NYC por nombre de ciudad para ver cómo se distribuyen las instalaciones entre los boroughs.

### 5. Subtipos FCode
Dentro de FType 740 (fuerzas del orden), existen subtipos: comisarías, estaciones de bomberos, EMS, subestaciones. Este desglose muestra la composición de tipos de instalaciones en los datos.

### 6. Verificación de completitud en NYC
Repite la verificación de completitud en el subconjunto filtrado de NYC — la completitud puede diferir del panorama estatal.

### 7. Detalle de direcciones faltantes
Lista específicamente qué instalaciones de NYC carecen de datos de dirección — útil para identificar registros que no pueden ser geocodificados o unidos espacialmente.

### 8. Exportación
Guarda cuatro archivos parquet en `poc/`:
- `hospitals_ny.parquet` — todos los hospitales del estado de NY
- `law_enforcement_ny.parquet` — todas las fuerzas del orden del estado de NY
- `hospitals_nyc.parquet` — hospitales solo de NYC
- `law_enforcement_nyc.parquet` — fuerzas del orden solo de NYC

---

## Relevancia criminológica

| Capa | Uso analítico |
|---|---|
| Hospitales | Proximidad a centros de trauma — la investigación vincula la proximidad hospitalaria con las tasas de supervivencia en homicidios por armas de fuego. También se usan como atractores de crimen (estacionamientos, actividad nocturna). |
| Ubicaciones de fuerzas del orden | Validar datos existentes de comisarías, calcular zonas de cobertura/tiempo de respuesta, identificar brechas de cobertura. |

Ambas capas se incorporan al **análisis de proximidad** — el núcleo de las páginas comparativas y de proximidad de la aplicación existente.

---

## Limitaciones

- **Sin geometría (POC original):** El WFS devuelve ubicaciones de puntos como `gml:PointPropertyType`; las coordenadas aparecieron nulas en los registros probados durante el POC original. La unión espacial requiere geocodificar las direcciones o utilizar otra fuente de coordenadas. El servicio en producción sí devuelve coordenadas GML válidas (verificado el 18 de mayo de 2026).
- **Nombres de ciudades en NYC son inconsistentes:** Los registros de NYC aparecen bajo múltiples nombres de ciudad (p. ej. "New York", "Manhattan", nombres de barrios). El notebook cubre los más comunes pero puede omitir algunos.
- **Sin prisiones:** FType 810 está ausente del dataset de NY. Para datos de instalaciones correccionales, HIFLD (`hifld-geoplatform.hub.arcgis.com`) es la alternativa — pero ese es ArcGIS REST, no OGC WFS.
- **El recuento es menor a 5000:** Ambas categorías están muy por debajo del límite de 5000 registros, por lo que una sola solicitud recupera el dataset completo.
