# Manual de Usuario

El presente manual constituye una guía operativa destinada a orientar al usuario en la instalación, puesta en marcha y utilización de la prueba de concepto *NYC Crime SDM Dashboard*. La inclusión de este manual responde al objetivo metodológico de asegurar la transferibilidad y reproducibilidad técnica del sistema para futuras investigaciones. El público objetivo incluye investigadores criminalísticos, analistas de datos y auditores metodológicos que requieran interactuar empíricamente con la herramienta. A diferencia de los los capítulos anteriores, que documentan las decisiones de diseño e implementación interna, este manual se enfoca exclusivamente en la perspectiva del usuario final.

El manual se organiza de la siguiente manera: la sección correspondiente detalla los requisitos del sistema y el procedimiento de instalación; la sección correspondiente presenta la estructura general de la interfaz, el sistema de filtros globales y el manejo de recursos computacionales; la sección correspondiente describe la operación del módulo de estadísticas descriptivas; la sección correspondiente aborda el módulo de análisis avanzado; y la sección correspondiente ofrece una guía para la correcta interpretación de los resultados.

## Requisitos Previos e Instalación

Para garantizar la reproducibilidad del entorno analítico, la prueba de concepto fue empaquetada íntegramente en contenedores lógicos aislados. Esto implica que el usuario no necesita instalar intérpretes de lenguajes de programación, bibliotecas de análisis de datos ni dependencias auxiliares de manera individual en su sistema operativo. El único requisito indispensable es la plataforma de contenerización.

### Requisitos del Sistema

En la la tabla se detallan los requisitos mínimos y recomendados para la ejecución del sistema.

| Componente | Requisito | Observaciones |
|---|---|---|
| Plataforma de contenerización | Docker 20.10+ con Docker Compose V2 | Disponible para Windows, macOS y Linux. Incluye la orquestación de servicios. |
| Memoria RAM | 16 GB mínimo (32 GB recomendado) | El pipeline procesa masivamente en memoria. 32 GB aseguran estabilidad. |
| Espacio en disco | 3 GB libres | Contempla la imagen de Docker y los datos en Parquet. |
| Conexión a internet | Solo durante la extracción | Una vez ejecutado, el dashboard opera en modo local sin conectividad. |

### Procedimiento de Instalación

El despliegue del sistema se realiza en tres pasos secuenciales. En primer lugar, se obtiene el repositorio del proyecto. Seguidamente, se ejecuta el *pipeline* de extracción y transformación de datos. Finalmente, se inicia el servidor del *dashboard* interactivo.

#### Paso 1: Obtención del repositorio.
El código fuente del proyecto se distribuye mediante un sistema de control de versiones. El usuario debe clonar el repositorio en su equipo local mediante el comando correspondiente de la herramienta *Git*:

"`bash
git clone https://github.com/{UsuarioGitHub}/Tesis-Repo.git
    cd Tesis-Repo
"`

#### Paso 2: Ejecución del pipeline ETL.
Este proceso descarga los datos crudos desde las fuentes primarias —los *datasets* oficiales de denuncias del NYPD desde NYC Open Data, las capas de equipamiento institucional desde el servicio WFS del USGS National Map y las paradas de ómnibus desde el portal de datos abiertos del estado de Nueva York—, los transforma, valida su consistencia geoespacial y los almacena en formato optimizado Parquet. Se ejecuta una única vez o cuando se desee actualizar el corpus de datos:

"`bash
docker compose run --rm pipeline
"`

La ejecución puede demorar entre cinco y veinte minutos según la velocidad de la conexión a internet, dado que descarga y procesa un volumen masivo de registros históricos. Al finalizar, el sistema reporta los artefactos generados junto con sus tamaños en disco, como se ilustra en la la ilustración.

![Ejecución del *pipeline* ETL con el resumen de artefactos generados.](Tesis/Imagenes/Manual/EjecucionExitosa.png)

*Ejecución del *pipeline* ETL con el resumen de artefactos generados.*

En caso de que ya se disponga de los datos descargados y solo se requiera re-ejecutar la fase de transformación (sin volver a descargar), se puede emplear la opción correspondiente:

"`bash
docker compose run --rm pipeline python -m src.pipeline --skip-extract
"`

#### Paso 3: Inicio del dashboard.
Una vez completado el *pipeline*, se levanta el servidor web del *dashboard*:

"`bash
docker compose up dashboard
"`

El sistema queda accesible en el navegador en la dirección `http://localhost:8501`. Para ejecutar el servidor en segundo plano sin ocupar la terminal, se agrega la bandera `-d`:

"`bash
docker compose up -d dashboard
"`

### Resolución de Problemas Comunes (Troubleshooting)

Durante el proceso de despliegue, pueden surgir algunos inconvenientes vinculados al entorno local del usuario. A continuación se detallan soluciones a los problemas más frecuentes:

    - **Puerto 8501 ocupado:** Si el contenedor del *dashboard* falla al iniciar indicando que el puerto ya está en uso, el usuario puede modificar el archivo `docker-compose.yml` cambiando la regla de mapeo de puertos (por ejemplo, a `8502:8501`).
    - **Fallo en la descarga de datos (ETL):** Si por cortes de internet o tiempos de espera agotados en la API del NYPD el proceso ETL se interrumpe, los archivos parciales pueden corromper ejecuciones futuras. Dado que el directorio `./data` se monta desde el sistema anfitrión, eliminar los volúmenes de Docker no lo afecta: se recomienda borrar manualmente el subdirectorio afectado dentro de `./data` y volver a ejecutar el Paso 2.
    - **Falta de memoria RAM en Docker:** Si el *pipeline* se detiene abruptamente (*Killed* o *OOMKilled*), verifique que los recursos asignados a la máquina virtual de Docker (en Docker Desktop o equivalente) cumplan con los requisitos mínimos establecidos en la la tabla.
    - **Fallas silenciosas:** Si un proceso se interrumpe sin mostrar errores evidentes en la web, se recomienda revisar los registros internos de los contenedores ejecutando el comando `docker compose logs pipeline` o `docker compose logs dashboard`.
    - **Permisos en entornos Linux:** En algunas distribuciones de Linux, si el usuario local no pertenece al grupo `docker`, será necesario anteponer `sudo` a todas las instrucciones (*e.g.*, `sudo docker compose up dashboard`).

## Interfaz General del Dashboard

Al acceder al *dashboard* mediante el navegador web, el usuario se encuentra con una interfaz organizada en dos componentes principales: una barra de navegación lateral que permite seleccionar el módulo analítico deseado, y un área de contenido principal donde se despliegan las visualizaciones y resultados correspondientes al módulo activo.

### Estructura de Navegación

La barra lateral izquierda organiza las diez vistas analíticas del sistema en dos secciones temáticas, como se observa en la la ilustración:

    - **Estadísticas Descriptivas**: agrupa las vistas de análisis exploratorio basadas en distribuciones y conteos — Resumen General, Temporal, Geoespacial y Demográfico.
    - **Análisis Avanzado**: agrupa las vistas que emplean técnicas de *Spatial Data Mining* — Comparativo, Proximidad, *Clustering* K-Means, Reglas de Asociación, Predicción ML y Anomalías.

Cinco de estas vistas aparecen en la barra lateral con el sufijo *V2*: *Geoespacial V2*, *Comparativo V2*, *Proximidad V2*, *Reglas V2* y *Predicción ML V2*. El sufijo identifica a las vistas que operan sobre las capas de equipamiento institucional del *USGS National Map*, incorporadas en la segunda versión de la prueba de concepto. Las cinco restantes no lo llevan porque no utilizan esas capas.

![Estructura de navegación del *dashboard* con las secciones y módulos analíticos disponibles.](Tesis/Imagenes/Manual/BarraLateralDeFiltros.png)

*Estructura de navegación del *dashboard* con las secciones y módulos analíticos disponibles.*

### Sistema de Filtros Globales

Debajo de la barra de navegación, la interfaz presenta tres filtros globales que afectan simultáneamente a **todas** las vistas del sistema. Esta característica resulta fundamental para la exploración analítica, ya que permite al investigador definir un subconjunto de datos y mantenerlo invariante al navegar entre los distintos módulos.

Los filtros disponibles (véase la la ilustración) son:

    - **Año(s)**: permite seleccionar uno o más años del período 2020--2025. Por defecto, todos los años se encuentran seleccionados.
    - **Borough(s)**: permite seleccionar uno o más de los cinco distritos de Nueva York (Manhattan, Brooklyn, Queens, Bronx, Staten Island). Por defecto, todos se encuentran activos.
    - **Nivel de ofensa**: permite filtrar por la gravedad del delito según la clasificación legal del NYPD (*Felony*, *Misdemeanor*, *Violation*). Por defecto, los tres niveles se encuentran seleccionados.

![Filtros globales del *dashboard*. Los cambios se propagan a todas las vistas de forma inmediata.](Tesis/Imagenes/Manual/BarraConFiltros.png)

*Filtros globales del *dashboard*. Los cambios se propagan a todas las vistas de forma inmediata.*

Al modificar cualquiera de estos filtros, el subconjunto de datos activo se recalcula de forma inmediata y todas las visualizaciones se actualizan automáticamente para reflejar el nuevo recorte.

### Indicadores de Procesamiento en Segundo Plano

Varios de los módulos de análisis avanzado (como *Clustering*, Reglas de Asociación, Predicción y Anomalías) ejecutan algoritmos de aprendizaje automático que pueden requerir varios segundos de procesamiento. Para estos casos, el sistema presenta una barra de progreso con indicación del paso actual, como se muestra en la la ilustración.

![Indicador de progreso durante la ejecución de modelos de aprendizaje automático.](Tesis/Imagenes/Manual/BarraDeCarga.png)

*Indicador de progreso durante la ejecución de modelos de aprendizaje automático.*

A nivel de rendimiento, el entrenamiento de un modelo complejo —como un ensamble de *Random Forest* con validación cruzada sobre una muestra representativa— requiere aproximadamente entre 15 y 30 segundos, dependiendo de la capacidad de procesamiento del equipo *host*. Una propiedad relevante de este mecanismo es que el usuario puede navegar a otra pestaña del *dashboard* mientras el cómputo se ejecuta en segundo plano. Al regresar a la pestaña original, los resultados se presentan de forma inmediata sin necesidad de re-ejecutar el algoritmo, siempre que los parámetros no hayan sido modificados.

### Manejo de Errores y Límites Computacionales

Debido a la naturaleza intensiva de los algoritmos de *Spatial Data Mining*, el sistema cuenta con mecanismos de protección contra el agotamiento de memoria RAM (*MemoryError*). Si el usuario define configuraciones computacionalmente inviables —como aplicar el algoritmo FP-Growth con un soporte mínimo extremadamente bajo (ej. 0,001)— el servidor interceptará el fallo para evitar la caída de la aplicación. En estos casos, la interfaz desplegará un mensaje de advertencia indicando que se ha excedido la capacidad de memoria disponible. La solución operativa ante este escenario consiste en reducir el volumen de datos mediante los filtros globales (seleccionando menos años o un solo *borough*) o ajustar los parámetros algorítmicos hacia valores más restrictivos.

## Módulo de Estadísticas Descriptivas

Este módulo comprende cuatro vistas orientadas a la exploración inicial del corpus de datos. Su propósito es brindar al analista un panorama general de la distribución criminal a través de conteos, proporciones y visualizaciones de distribución, sin recurrir a técnicas de aprendizaje automático.

### Resumen General

La vista de Resumen General constituye la página de inicio del *dashboard* y ofrece una síntesis cuantitativa del conjunto de datos activo según los filtros aplicados (la ilustración). Se presentan cuatro indicadores clave de rendimiento (KPIs):

    - **Total de registros**: cantidad total de denuncias en el subconjunto filtrado.
    - **Felonies**: cantidad de delitos clasificados como graves (*felonies*).
    - **Boroughs**: cantidad de distritos representados en los datos filtrados.
    - **Período**: rango temporal cubierto por los datos (por ejemplo, "2020--2025").

Debajo de los indicadores, se despliega una guía de navegación que describe brevemente el propósito de cada sección del *dashboard*, funcionando como un índice interactivo para el usuario.

![Vista de Resumen General con los indicadores clave y la guía de navegación.](Tesis/Imagenes/Manual/ResumenGeneral.png)

*Vista de Resumen General con los indicadores clave y la guía de navegación.*

### Análisis Temporal

La vista temporal provee tres visualizaciones complementarias para el estudio de patrones cronológicos en la actividad criminal:

    - **Evolución mensual por nivel de ofensa**: un gráfico de líneas que despliega la tendencia mes a mes, segregada por nivel de gravedad (*Felony*, *Misdemeanor*, *Violation*). El eje horizontal representa el tiempo y el eje vertical la cantidad de denuncias. Permite identificar estacionalidad y tendencias de largo plazo.

    - **Mapa de calor día de semana × hora**: una matriz visual donde las filas representan los días de la semana (lunes a domingo) y las columnas las horas del día (0 a 23). La intensidad del color indica la concentración de crímenes. Las celdas más oscuras revelan las combinaciones día/hora con mayor actividad delictiva (ver la ilustración).

    - **Comparación año contra año**: un gráfico de barras con el total anual de denuncias para cada año del período. Permite evaluar variaciones interanuales que podrían correlacionarse con políticas públicas o eventos extraordinarios.

![Mapa de calor temporal: concentración de crímenes por día de semana y hora del día.](Tesis/Imagenes/Manual/MapaDeCalor.png)

*Mapa de calor temporal: concentración de crímenes por día de semana y hora del día.*

### Análisis Geoespacial

Esta vista proyecta los datos sobre cartografía digital interactiva, ofreciendo dos elementos principales:

    - **Mapa de calor de densidad**: un *heatmap* superpuesto sobre el mapa base de la ciudad de Nueva York que muestra la concentración geográfica de los crímenes. Las zonas con mayor densidad se representan con tonos cálidos (rojo intenso), mientras que las zonas con menor actividad se muestran en tonos fríos. Para garantizar un rendimiento fluido, el mapa muestrea hasta 50.000 puntos del conjunto de datos activo. Este muestreo utiliza una semilla aleatoria fija (`random\_state=42`), por lo que la visualización será idéntica en distintas sesiones para los mismos filtros.

    - **Distribución por *borough***: un gráfico de barras que cuantifica la cantidad de crímenes registrados en cada distrito, ordenados de mayor a menor.

Adicionalmente, si se dispone de datos de infraestructura, el mapa superpone marcadores azules que representan la ubicación de las comisarías de policía. El control de capas, ubicado en la esquina superior derecha del mapa, permite activar o desactivar la visualización de cada capa de forma independiente (ver la ilustración).

![Mapa de calor de densidad criminal con la capa de comisarías superpuesta.](Tesis/Imagenes/Manual/Comisarias.png)

*Mapa de calor de densidad criminal con la capa de comisarías superpuesta.*

### Análisis Demográfico

La vista demográfica despliega el perfil estadístico de las víctimas y de los tipos de delito registrados. Se compone de tres bloques:

    - **Tipos de delito más frecuentes**: un gráfico de barras horizontales con los N tipos de crimen predominantes, donde N es ajustable mediante un deslizador interactivo (rango: 5 a 30). Permite identificar rápidamente los delitos con mayor incidencia en el subconjunto filtrado.

    - **Perfil de víctimas**: tres gráficos de torta que distribuyen las víctimas según grupo etario ($<$18, 18--24, 25--44, 45--64, 65+), sexo y raza. Los códigos internos del NYPD (por ejemplo, el código "D" para organizaciones comerciales en el campo de sexo) son traducidos automáticamente a etiquetas descriptivas, tal como se ilustra en la la ilustración.

    - **Tipo de premisa**: un gráfico de barras horizontales con los quince tipos de lugar más frecuentes donde ocurren los delitos (calle, residencia, comercio, entre otros).

![Perfil demográfico de víctimas: distribución por grupo etario, sexo y raza.](Tesis/Imagenes/Manual/Demografico.png)

*Perfil demográfico de víctimas: distribución por grupo etario, sexo y raza.*

## Módulo de Análisis Avanzado

El módulo de análisis avanzado comprende seis vistas que implementan técnicas de *Spatial Data Mining*. A diferencia del módulo descriptivo, estas vistas incorporan parámetros configurables que el usuario puede ajustar para explorar distintas perspectivas analíticas. Los cálculos intensivos se ejecutan en segundo plano, permitiendo la navegación fluida durante el procesamiento.

### Análisis Comparativo

Esta vista cruza los datos de criminalidad con los datos de infraestructura urbana (comisarías de policía y estaciones de transporte público) para revelar relaciones espaciales. Se compone de cinco visualizaciones:

    - **Ratio crímenes por comisaría**: un gráfico de barras que muestra cuántos crímenes le corresponden a cada comisaría en cada *borough*. Un ratio elevado sugiere zonas con cobertura policial insuficiente.

    - **Distancia a comisaría más cercana**: un histograma con la distribución de distancias (en kilómetros) entre cada crimen y la comisaría más próxima. Se presentan tres indicadores: distancia media, distancia mediana y porcentaje de crímenes a más de 2 km de una comisaría.

    - **Densidad alrededor de estaciones de transporte**: el usuario ajusta un radio de análisis (100 m a 2,5 km) mediante un deslizador, y el sistema calcula cuántos crímenes ocurren dentro de ese radio alrededor de cada estación de transporte. Se muestran las veinte estaciones con mayor densidad criminal.

    - **Mapa combinado**: un mapa interactivo que superpone tres capas: el *heatmap* de crímenes (rojo), las comisarías (azul) y las estaciones de transporte público (verde, naranja y violeta según el tipo). Cada capa se puede activar o desactivar de forma independiente (la ilustración).

    - **Nivel de ofensa por *borough***: un gráfico de barras agrupadas que compara la proporción de *felonies*, *misdemeanors* y *violations* en cada distrito.

![Mapa combinado: densidad criminal superpuesta con infraestructura de servicios públicos (transporte, hospitales, estaciones de policía).](Tesis/Imagenes/Manual/MapaCrimenes.png)

*Mapa combinado: densidad criminal superpuesta con infraestructura de servicios públicos (transporte, hospitales, estaciones de policía).*

### Análisis de Proximidad

Esta vista permite investigar si los crímenes que ocurren cerca de una comisaría presentan características distintas a los que ocurren lejos. El usuario define el umbral de distancia que separa "cerca" de "lejos" mediante un deslizador continuo (rango: 0,1 km a 3,0 km).

#### Controles interactivos.

    - **Umbral de distancia** (rango: 0,1 a 3,0 km): deslizador que define el punto de corte. Los crímenes a menos de esta distancia de la comisaría más cercana se clasifican como "CERCA"; los demás como "LEJOS".
    - **Muestra** (rango: 5.000 a 50.000 registros): cantidad de registros sobre la que se calculan las distribuciones de la vista, con 20.000 por defecto.

#### Visualizaciones principales.

    - **Distribución horaria (CERCA vs. LEJOS)**: un par de diagramas de caja (*boxplots*) que compara la distribución de la hora del día en ambos grupos. Cada punto individual del conjunto de datos es visible (con transparencia y *jitter*). Una diferencia en las medianas podría sugerir que la presencia policial disuade crímenes en ciertos horarios (ver la ilustración).

    - **Distancia al transporte (CERCA vs. LEJOS de policía)**: otro par de *boxplots* que evalúa si los crímenes lejanos a comisarías también tienden a estar lejos del transporte público, revelando zonas con baja cobertura dual.

    - **Distancia por tipo de crimen (top 10)**: *boxplots* que muestran la distribución de distancia a comisaría para los diez tipos de delito más frecuentes. Tipos con mediana elevada indican delitos que tienden a ocurrir lejos de la cobertura policial.

#### Tablas complementarias.
Debajo de las visualizaciones gráficas, la vista presenta tres tablas de detalle: una tabla de estadísticas descriptivas (media, mediana, desviación estándar, cuartiles, rango intercuartílico) por grupo; una tabla por tipo de crimen con distancias medias y porcentajes de proximidad; y una tabla cruzada que distribuye los crímenes en cuatro categorías de distancia simultánea a policía y transporte.

![Análisis de proximidad: distribución horaria de crímenes cerca y lejos de comisarías.](Tesis/Imagenes/Manual/BoxPlot.png)

*Análisis de proximidad: distribución horaria de crímenes cerca y lejos de comisarías.*

### Clustering K-Means

Esta vista aplica el algoritmo de agrupamiento K-Means sobre las coordenadas geográficas de los crímenes para identificar automáticamente zonas de concentración delictiva (*hotspots*).

#### Controles interactivos.

    - **Número de clusters ($k$)**: deslizador que permite ajustar la cantidad de agrupamientos (rango: 3 a 20). Un valor bajo genera zonas amplias; un valor alto produce una segmentación más granular.

#### Resultados presentados.

    - **Mapa de clusters**: un mapa interactivo donde cada crimen se colorea según el cluster al que pertenece. Los centros de cada cluster se destacan con marcadores prominentes, y círculos de 1 km de radio delinean la zona de influencia aproximada de cada agrupamiento. El usuario puede activar o desactivar cada cluster individualmente mediante el control de capas (la ilustración).

    - **Elbow Chart**: un gráfico de línea que muestra la inercia (suma de distancias al centro del cluster) para valores de $k$ entre 2 y 15. El punto de inflexión o "codo" de la curva indica el número óptimo de clusters. Una línea vertical roja señala el valor de $k$ actualmente seleccionado (la ilustración).

    - **Tabla de centros**: las coordenadas exactas (latitud, longitud) de cada centro de cluster junto con la cantidad de crímenes asignados a cada uno, ordenados por tamaño descendente.

![Mapa de *clusters* K-Means con centros y zonas de influencia ($k=10$).](Tesis/Imagenes/Manual/KMEAN.png)

*Mapa de *clusters* K-Means con centros y zonas de influencia ($k=10$).*

![Método del codo (*elbow chart*) para la determinación del $k$ óptimo.](Tesis/Imagenes/Manual/Elbow.png)

*Método del codo (*elbow chart*) para la determinación del $k$ óptimo.*

### Reglas de Asociación (FP-Growth)

Esta vista descubre patrones de co-ocurrencia entre tipos de delito y proximidad a infraestructura urbana mediante el algoritmo FP-Growth.

#### Controles interactivos.
Los tres parámetros del algoritmo se exponen mediante deslizadores:

    - **Soporte mínimo** (0,005 a 0,10): la fracción mínima de transacciones que deben contener un conjunto de ítems para considerarlo frecuente. Valores bajos generan más reglas pero potencialmente menos significativas.
    - **Confianza mínima** (0,5 a 1,0): la probabilidad mínima de que el consecuente ocurra dado el antecedente. Valores altos filtran solo las reglas con mayor poder predictivo.
    - **Umbral CERCA/LEJOS** (0,1 a 2,0 km): la distancia que separa un crimen "cercano" de uno "lejano" a la infraestructura.

#### Resultados presentados.

    - **Itemsets frecuentes**: los treinta conjuntos de ítems más frecuentes con su soporte.
    - **Reglas de asociación**: tabla con antecedente, consecuente, soporte, confianza y *lift*. Las reglas con *lift* superior a 1,5 se resaltan visualmente, indicando asociaciones más fuertes que lo esperado por azar (como se muestra en la la ilustración).
    - **KPIs**: cantidad total de reglas, cantidad de reglas con *lift* $> 1{,}5$ y confianza máxima encontrada.
    - **Gráfico de dispersión**: soporte vs. confianza para las cincuenta reglas principales, donde el tamaño y color de cada punto representan el *lift*.

#### Ejemplo de lectura.
Una regla del tipo $[\text{TIPO=ROBBERY}] \rightarrow [\text{LEJOS\_POLICIA}]$ con confianza 0,85 se interpreta de la siguiente manera: el 85\% de los robos en la muestra analizada ocurren a una distancia superior al umbral definido respecto a la comisaría más cercana.

![Reglas de asociación descubiertas por FP-Growth, con resaltado de reglas con *lift* elevado.](Tesis/Imagenes/Manual/ReglasAsociacion.png)

*Reglas de asociación descubiertas por FP-Growth, con resaltado de reglas con *lift* elevado.*

### Predicción ML

Esta vista entrena y evalúa dos modelos de clasificación para predecir el nivel de ofensa (*Felony*, *Misdemeanor* o *Violation*) a partir de variables temporales y geoespaciales.

#### Controles interactivos.

    - **Árboles** ($n\_estimators$, rango: 50 a 300): cantidad de árboles de decisión en el ensamble.
    - **Profundidad máxima** (rango: 3 a 20): profundidad máxima de cada árbol.
    - **Porcentaje de datos de test** (rango: 15\% a 40\%): proporción del conjunto de datos reservada para la evaluación final.
    - **Modelo principal**: selector entre *Random Forest* y *Gradient Boosting*.

#### Resultados presentados.

    - **KPIs de rendimiento**: *accuracy* de ambos modelos, puntuación de validación cruzada (media $\pm$ desviación estándar) y cantidad total de *features* utilizadas.

    - **Validación cruzada**: gráfico de barras agrupadas con el *accuracy* de cada uno de los cinco *folds*, comparando ambos modelos lado a lado. Permite evaluar la estabilidad del rendimiento.

    - **Matriz de confusión**: un mapa de calor que muestra la distribución de predicciones correctas e incorrectas para cada clase. La diagonal principal contiene las clasificaciones acertadas (ver la ilustración).

    - **Reporte de clasificación**: tabla con *precision*, *recall* y F1 para cada clase.

    - **Importancia de *features***: gráfico de barras horizontales con las quince *features* más influyentes en la predicción. Si las variables de distancia a infraestructura (`dist\_usgs\_v2\_policia\_km`, `dist\_usgs\_v2\_bomberos\_km` y `dist\_usgs\_v2\_salud\_km`) aparecen entre las más importantes, se confirma la hipótesis de que la proximidad a infraestructura urbana es un factor relevante en la gravedad del delito.

    - **Interpretación automática**: el sistema genera un análisis textual indicando la posición en el ranking de importancia de cada variable de distancia y cada variable temporal.

![Resultados del modelo de predicción: matriz de confusión e importancia de *features* usando random forest.](Tesis/Imagenes/Manual/MatrizDeConfusion.png)

*Resultados del modelo de predicción: matriz de confusión e importancia de *features* usando random forest.*

### Detección de Anomalías

Esta vista identifica días con actividad criminal inusualmente alta o baja mediante el algoritmo *Isolation Forest*.

#### Controles interactivos.

    - **Tasa de contaminación** (rango: 1\% a 15\%): la proporción esperada de observaciones anómalas en los datos. Un valor del 5\% implica que el algoritmo clasificará aproximadamente el 5\% de los días como anómalos.
    - **Granularidad**: permite seleccionar entre analizar toda la ciudad en conjunto o segmentar por *borough*.

#### Resultados presentados.

    - **KPIs**: períodos totales analizados, cantidad de anomalías detectadas, porcentaje de anomalías y media de crímenes en los días anómalos.

    - **Timeline**: una serie temporal donde los días normales se representan como una línea azul continua y las anomalías como marcadores rojos en forma de cruz. Una línea horizontal punteada gris indica la media de los días normales, facilitando la comparación visual. Al posicionar el cursor sobre un marcador, se despliega información contextual (fecha, conteo de crímenes, *borough*), como se observa en la la ilustración.

    - **Tabla de top anomalías**: las veinte anomalías más extremas, ordenadas por su *score* de anomalía (valores más negativos indican mayor grado de atipicidad). Incluye fecha, conteo de crímenes, *borough* (si corresponde) y día de la semana.

    - **Distribución por *borough***: gráfico de barras que muestra qué distritos concentran más días anómalos.

    - **Histograma de *scores***: distribución del *anomaly score* del modelo, diferenciando visualmente las observaciones clasificadas como normales (azul) de las anómalas (rojo). La zona de transición entre ambos colores corresponde al umbral de decisión del algoritmo.

![Serie temporal con anomalías detectadas por *Isolation Forest*. Los marcadores rojos señalan días con actividad criminal atípica.](Tesis/Imagenes/Manual/Anomalias.png)

*Serie temporal con anomalías detectadas por *Isolation Forest*. Los marcadores rojos señalan días con actividad criminal atípica.*

## Guía de Interpretación de Resultados

El propósito de esta sección es proveer al usuario de las herramientas conceptuales necesarias para interpretar correctamente los resultados producidos por el *dashboard*, evitando conclusiones erróneas derivadas de una lectura superficial de las métricas y visualizaciones.

### Lectura de Métricas e Indicadores

En la la tabla se describen las principales métricas utilizadas a lo largo del *dashboard*, junto con su interpretación y las precauciones que deben tomarse al momento de extraer conclusiones.

| Métrica | Módulo | Interpretación y precauciones |
|---|---|---|
| Soporte | Reglas de Asociación | Proporción de transacciones. Valores muy bajos pueden ser patrones débiles. |
| Confianza | Reglas de Asociación | Probabilidad condicional. Valores > 0.8 indican reglas fuertes. No implica causalidad. |
| Lift | Reglas de Asociación | Ratio de frecuencia. Lift=1 es azar; >1 es asociación genuina. |
| Accuracy | Predicción ML | Proporción de predicciones correctas. |
| F1 | Predicción ML | Media armónica entre precision y recall. Útil para clases desbalanceadas. |
| Inercia | Clustering | Suma de distancias al centro. |
| Anomaly Score | Anomalías | Grado de atipicidad. Valores más negativos son más anómalos. |

### Consideraciones para el Análisis

Al utilizar los resultados producidos por la prueba de concepto, el investigador debe tener presentes las siguientes consideraciones:

    - **Muestreo**: varias de las vistas analíticas operan sobre muestras del conjunto de datos completo para garantizar un rendimiento interactivo aceptable. Se aplica un muestreo aleatorio simple (*Simple Random Sampling*) preservando la distribución general de los datos. El tamaño de la muestra se indica en cada vista (por ejemplo, "muestra de 20.000 registros de 3.090.798"). Los resultados deben interpretarse como estimaciones representativas, no como cómputos exhaustivos sobre la totalidad del corpus.

    - **Cobertura del filtro por *borough***: el filtro global de *borough* descarta los registros cuyo distrito no está informado. Sobre el corpus completo producido por el *pipeline* ETL, esto representa 5.102 denuncias de un total de 3.095.900, de modo que las vistas analizan 3.090.798 registros. Se trata de una fracción menor al 0,2 \%, pero conviene tenerla presente al contrastar los totales que muestra el *dashboard* con los que reporta el ETL al finalizar su ejecución.

    - **Correlación y causalidad**: las asociaciones descubiertas por los módulos de reglas de asociación y proximidad indican patrones de co-ocurrencia estadística, pero no implican relaciones causales. La observación de que ciertos delitos ocurren lejos de comisarías no establece, por sí sola, que la ausencia de comisarías cause esos delitos.

    - **Sesgo en los datos fuente**: los datos del NYPD representan denuncias formales registradas por la policía, no la totalidad de la actividad criminal. Delitos no denunciados no aparecen en el corpus. Asimismo, los criterios de clasificación del NYPD pueden haber variado a lo largo del período 2020--2025.

    - **Reproducibilidad**: dado que los algoritmos de aprendizaje automático utilizan semillas aleatorias fijas (`random\_state=42`), los resultados son reproducibles siempre que se mantengan los mismos datos de entrada y parámetros de configuración.

    - **Actualización de datos**: el *pipeline* de extracción puede re-ejecutarse para incorporar datos más recientes. Debe tenerse presente que las capas de equipamiento del USGS National Map se actualizan según el calendario propio del organismo, de modo que la vigencia de esos datos depende de ese ciclo y no del momento en que se ejecuta la extracción.

