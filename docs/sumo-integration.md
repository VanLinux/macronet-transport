# MacroNet Transport 3.2.0 · Microsimulación opcional con Eclipse SUMO

Fecha: 24 de octubre de 2026. Autor del proyecto: Héctor Alonso Benítez García.

## Alcance

La integración aplica la propuesta de conservar Python como núcleo matemático
y añadir SUMO al final de la asignación. **Las cuatro etapas siguen siendo cuatro**.
La pestaña adicional no sustituye generación, distribución, elección modal,
AON/Wardrop, calibración ni los reportes anteriores. El programa inicia, calcula,
guarda y exporta sin SUMO.

Esta primera integración permite construir redes viales simplificadas y simular
automóviles con cruces prioritarios. El usuario revisa coordenadas, longitudes,
velocidades y carriles. Las conexiones se generan con `netconvert`; dos arcos que
se cruzan geométricamente no crean por sí solos un nodo de intersección.
No se importan todavía redes OSM/SUMO existentes ni planes semafóricos, restricciones
de giro, itinerarios de autobuses o peatones. No se ejecutan `marouter` ni
`duaIterate.py`; la implementación no afirma resolver equilibrio dinámico.

## Instalación

Desde la carpeta del repositorio y con su entorno virtual activo:

```bash
git pull --ff-only
python -m pip install -e ".[sumo]"
macronet
```

El extra `sumo` instala el paquete oficial `eclipse-sumo` cuando hay una distribución
compatible con el sistema. Se puede usar en su lugar una instalación externa
de Eclipse SUMO **1.18 o posterior**, con `sumo`, `netconvert` y `duarouter` de la
misma versión. En Ubuntu:

```bash
sudo apt install sumo sumo-tools
```

En Windows se puede seleccionar la carpeta `bin` de la distribución oficial.
La detección automática busca en la carpeta del intérprete Python, `SUMO_HOME/bin`
y `PATH`. Un error de detección afecta al módulo de simulación; el resto del
programa sigue disponible. No se instala software automáticamente al abrir un proyecto.

## Uso

1. Calcule las cuatro etapas y seleccione el modo cuya OD se asignará. Aplique
   primero los cambios pendientes de asignación con **Asignar** o **Comparar**.
2. Abra **Microsimulación SUMO** y pulse **Actualizar geometría desde la asignación**
   si cambió nodos o arcos. Se conservan las celdas de geometría de IDs existentes;
   los nuevos reciben valores de ejemplo. Los IDs se corresponden con MacroNet.
3. Revise coordenadas en metros, longitud en metros, velocidad en km/h y carriles.
   Las longitudes deben ser al menos la distancia recta entre sus nodos; no se
   aceptan nodos coincidentes, arcos sin geometría ni números no finitos.
4. Especifique **viajes-persona por periodo** o **vehículos por periodo**. La ocupación
   sólo se aplica a personas. El modo debe representar demanda vial que pueda
   modelarse con automóviles; renombrar una alternativa no transforma pasajeros
   de autobús o peatones en vehículos particulares.
5. Declare el periodo al que corresponden tanto la OD como las capacidades BPR.
   El despeje añade tiempo sin nueva demanda. El multiplicador permite estudiar
   cambios de demanda; no cambia la capacidad. Seleccione salidas uniformes globales o
   aleatorias, semilla y límite de tiempo **real** de ejecución.
6. Marque la confirmación de revisión y pulse **Ejecutar SUMO…**. Elija una carpeta
   contenedora: cada ejecución crea su propio subdirectorio y conserva los anteriores.
7. Revise conteos, indicadores, evolución temporal y contraste por arco. La interfaz
   sigue disponible durante la simulación; **Cancelar ejecución** detiene los procesos.
   Cerrar la ventana cancela primero y después ofrece guardar los cambios pendientes.
   Espere o cancele antes de abrir otro ejercicio.
8. Guarde el `.mnet` y exporte el informe habitual desde **Resumen**. Los indicadores
   de microsimulación se incluyen en una sección independiente. Si cambian entradas
   o asignación, los resultados previos se identifican como una ejecución anterior.

**Exportar escenario sin ejecutar…** genera los archivos de entrada y un `README.txt`
con los comandos necesarios, sin requerir el motor instalado. No genera indicadores
simulados. La carpeta también puede abrirse después con herramientas externas de SUMO.

## Demanda y referencia estática

Para cada celda OD se aplica:

\[
Q^{veh}_{ij}=Q_{ij}\,m/o\quad\text{si la OD está en personas};\qquad
Q^{veh}_{ij}=Q_{ij}\,m\quad\text{si ya está en vehículos}.
\]

`m` es el multiplicador y `o` la ocupación. Se excluyen viajes entre zonas que
comparten el mismo centroide, incluidos los intrazonales. Se guarda esa cantidad
en vehículos equivalentes. No se inventan rutas internas para ellos.

SUMO necesita vehículos enteros. El método de **resto mayor** conserva el total
intercentroide redondeado al entero más próximo (mitades hacia arriba); los restos
se asignan en orden descendente, con desempate por orden OD. Cada celda difiere
menos de un vehículo de su valor convertido. Los marginales no se conservan
exactamente. Se registran la matriz resultante y el ajuste total de redondeo.

La referencia AON o UE se vuelve a calcular **dentro del escenario**, con esa
misma matriz vehicular, las capacidades declaradas y `t0 = longitud/velocidad`.
Se conservan α, β, tolerancia y límite de iteraciones de la asignación vigente.
La asignación original de las cuatro etapas no se modifica. El estado de
convergencia de la nueva referencia UE queda en `manifest.json`.

Cada zona se vincula mediante TAZ a los arcos que salen/entran de su centroide.
`duarouter` selecciona una ruta con los tiempos de la referencia; SUMO la simula
sin iteración de reasignación. **No se descompone el flujo UE en rutas ni se afirma
reproducir su reparto**. Las capacidades BPR no se traducen automáticamente en
capacidades microscópicas: éstas dependen de carriles, interacción y cruces.

La configuración de automóvil usa Krauss, aceleración 2.6 m/s², desaceleración
4.5 m/s², longitud 5 m, separación 2.5 m, `tau=1 s`, `sigma=0.5` y factor de
velocidad 1. Son valores de ejemplo explícitos en el XML, no una calibración local.
El paso es 1 s, el calentamiento 0 s y se desactiva la teleportación por bloqueo.
Las salidas uniformes distribuyen todos los vehículos a intervalos iguales y
mezclan sus pares OD mediante la semilla; no imponen espaciamiento uniforme por
cada celda OD. Las aleatorias ordenan tiempos muestreados dentro del periodo.

## Indicadores y comparación

| Indicador | Definición |
|---|---|
| Generados | Vehículos enteros programados dentro del periodo |
| Insertados | Vehículos que pudieron entrar en la red |
| Llegados | Recorridos completados, excluyendo vehículos retirados sin completar |
| En red | Vehículos todavía circulando al final del horizonte |
| Pendientes | Generados menos insertados; no desaparecen del balance |
| Retirados sin completar | Insertados menos llegados y todavía en red |
| Tiempo medio | Duración de los recorridos completados, sin retraso de inserción |
| Espera | Tiempo detenido según la definición `waitingTime` de SUMO |
| Pérdida de tiempo | `timeLoss`; distinta de espera y de demora de control HCM |
| Retraso de inserción | `departDelay`, mostrado por separado |
| Velocidad agregada | Distancia total / tiempo total de los recorridos completados |
| Entradas por arco | `entered + departed` del agregado SUMO |
| Tiempo por arco SUMO | Estimación `traveltime` de las muestras del arco, en minutos |

Los agregados por arco incluyen **todo el horizonte, con despeje**. La comparación
con tiempos/volúmenes estáticos es un contraste descriptivo, no una prueba de
equilibrio ni una igualdad de definiciones. Si no hay llegadas o muestras se
muestra su ausencia, en vez de inventar promedios cero. El cierre del horizonte
no implica que todos los vehículos hayan completado el recorrido.

## Persistencia y reproducibilidad

El `.mnet` usa esquema 3 y admite lectura de esquemas 1 y 2. Guarda configuración,
tablas en edición, última ejecución, matriz vehicular, referencia, indicadores y
procedencia. Un archivo nuevo requiere MacroNet 3.2 o posterior para abrirse.
Abrirlo **nunca inicia ejecutables** ni exige que existan las carpetas externas.

La carpeta de ejecución conserva nodos, arcos, TAZ, viajes, pesos, configuración,
red compilada, rutas, salidas XML, `demand.csv`, `comparison.csv`, registros y
`manifest.json`. El manifiesto registra versión de MacroNet/SUMO, semilla,
configuración, comandos, estado, tiempo real, huella de entradas y SHA-256 de
los XML. La cancelación y los fallos conservan un diagnóstico en esa carpeta.
Las salidas completas permanecen fuera del `.mnet` para evitar archivos enormes.
La reproducibilidad estadística se comprueba con igual versión, configuración y
semilla; no se promete identidad entre versiones de SUMO.

## Arquitectura y verificación

- `sumo/scenario.py`: contratos, validación, demanda, adaptador MacroNet y archivos.
- `sumo/runner.py`: detección, procesos sin shell, cancelación de grupos de procesos,
  límite de tiempo, lectura XML e indicadores; independiente de Qt.
- `ui/microsimulation_widget.py`: entradas, trabajador, estados y presentación.
- Persistencia y reporte conservan una instantánea separada de las cuatro etapas.

El ejecutor está aislado para facilitar su extracción posterior a una biblioteca
compartida; esta entrega modifica únicamente MacroNet.

Las pruebas incluyen motor real con AON y UE, demanda conservada, ausencia del
motor, salidas reproducibles, vehículos pendientes, cancelación, respuesta gráfica,
guardado/reapertura y compatibilidad con archivos anteriores. CI ejecuta la matriz
general Ubuntu/Windows y trabajos adicionales con SUMO real en ambos sistemas. La versión
de motor utilizada se conserva en cada manifiesto.

Se admite una ejecución a la vez y de 1 a 50 000 vehículos por escenario. El
límite no constituye un benchmark. **No se ha medido rendimiento en Raspberry Pi 4**;
en equipos de 4 GB se deben comenzar con redes y demandas pequeñas y medir recursos.

## Fuentes oficiales

- [Redes PlainXML y netconvert](https://sumo.dlr.de/docs/Networks/PlainXML.html).
- [Matrices OD y TAZ](https://sumo.dlr.de/docs/Demand/Importing_O/D_Matrices.html).
- [Enrutamiento por TAZ](https://sumo.dlr.de/docs/Demand/Shortest_or_Optimal_Path_Routing.html).
- [duarouter](https://sumo.dlr.de/docs/duarouter.html).
- [TripInfo y recorridos incompletos](https://sumo.dlr.de/docs/Simulation/Output/TripInfo.html).
- [Agregados por arco](https://sumo.dlr.de/docs/Simulation/Output/Lane-_or_Edge-based_Traffic_Measures.html).
- [Resumen de vehículos](https://sumo.dlr.de/docs/Simulation/Output/Summary.html).
- [Instalación de SUMO](https://sumo.dlr.de/docs/Installing/index.html).

MacroNet conserva GPL-3.0-only y la autoría del proyecto. SUMO se utiliza como
herramienta externa bajo su propia licencia; no se cambia la licencia de MacroNet.
