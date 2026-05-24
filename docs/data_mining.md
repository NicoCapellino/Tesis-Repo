# Data Mining V2

La version V2 usa solo infraestructura USGS:

- `USGS V2 - Policia`
- `USGS V2 - Bomberos`
- `USGS V2 - Salud`

## Reglas de Asociacion

Objetivo: descubrir patrones frecuentes entre tipo de delito y proximidad a
infraestructura USGS.

Cada crimen se transforma en una transaccion:

```text
TIPO=<offense_description>
CERCA_USGS_V2_POLICIA / LEJOS_USGS_V2_POLICIA
CERCA_USGS_V2_BOMBEROS / LEJOS_USGS_V2_BOMBEROS
CERCA_USGS_V2_SALUD / LEJOS_USGS_V2_SALUD
```

El umbral cerca/lejos es configurable desde la UI.

Metricas:

- Soporte
- Confianza
- Lift

## Proximidad

La pagina de proximidad calcula distancia minima desde cada crimen hacia cada
capa USGS V2. A partir de esas distancias genera:

- Grupos cerca/lejos para una capa seleccionada.
- Distribucion horaria cerca/lejos.
- Distancia por tipo de delito.
- Resumen multi-capa: media, mediana, p75 y porcentaje cerca.
- Tabla cruzada de bins de proximidad entre dos capas USGS.

## Prediccion

La pagina de prediccion agrega features de distancia al modelo:

| Feature | Descripcion |
|---|---|
| `dist_usgs_v2_policia_km` | Distancia a comisaria USGS mas cercana |
| `dist_usgs_v2_bomberos_km` | Distancia a estacion de bomberos USGS mas cercana |
| `dist_usgs_v2_salud_km` | Distancia a centro de salud USGS mas cercano |
| `log_dist_*` | Transformacion logaritmica de cada distancia |
| `ratio_dist_usgs_v2_*` | Ratios entre distancia policial y otras capas |

Estas features se combinan con hora, dia de semana, mes, borough y tipo de
premisa para clasificar `offense_level`.

## Analisis Comparativo

El comparativo V2 calcula:

- Inventario USGS por capa y borough.
- Ratio de crimenes por comisaria USGS.
- Crimenes dentro de un radio configurable alrededor de cada instalacion.
- Tipo de crimen dominante alrededor de las instalaciones con mayor exposicion.
- Capa USGS mas cercana a cada crimen y distribucion por nivel de ofensa.
