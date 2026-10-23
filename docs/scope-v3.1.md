# MacroNet Transport 3.1 — calibración y asignación

Acuerdos del 22 de octubre de 2026. Evolución de la versión 3: no hay salto a 4.
Se conserva la operación inicial manual, la fricción exponencial y AON. No se
agregan etapas de transporte ni se alteran los valores del caso didáctico anterior.

## Parámetros por etapa

| Etapa | Parámetros | Interpretación |
| --- | --- | --- |
| Producción | β₀, βH, βV | Intercepto y efectos de hogares/vehículos |
| Atracción | α₀, αE, αS | Intercepto y efectos de empleos/estudiantes |
| Distribución | β y/o α | Fricción exponencial, potencia o combinada |
| Elección modal | ASC, βt, βc | Utilidad de alternativas y atributos |
| Asignación vial | α BPR, β BPR | Función volumen-demora; no son coeficientes conductuales |

La procedencia es independiente por etapa/modelo. Editar un coeficiente estimado
lo vuelve manual sin borrar el diagnóstico del ajuste. Cambiar el selector de
origen permite volver al ingreso manual; no revierte ni aplica valores por sí solo.

## Flujo de calibración

1. Seleccionar **Estimados** en la etapa.
2. Abrir **Importar, estimar y revisar**. Descargar una plantilla de encabezados.
3. Importar CSV UTF-8 con encabezados únicos. Se reconocen coma, punto y coma o
   tabulador como separador. Las columnas numéricas usan punto decimal.
4. Asignar una columna diferente a cada dato requerido.
5. Estimar y revisar identificación, parámetros, errores estándar, IC 95%, métricas
   y gráficos. La estimación se ejecuta en un hilo separado de la interfaz.
6. Pulsar **Aplicar parámetros estimados** y después **Calcular** en la etapa.

Importar o estimar no cambia los coeficientes actuales. Los datos, el mapeo y el
ajuste se guardan en `.mnet`; los modelos de producción y atracción tienen registros
separados. El origen aplicado conserva nombre del archivo, número de filas y huella
SHA-256. Los CSV importados se integran al ejercicio: no dependen de rutas externas.
El CSV individual admite hasta 5 MB y 30 000 filas; el ejercicio completo hasta 10 MB.

### Generación / atracción

Columnas de plantilla: `id,x1,x2,y,sample`.

- **Producción:** `x1` = hogares, `x2` = vehículos; `y` = viajes observados.
- **Atracción:** `x1` = empleos, `x2` = estudiantes; `y` = viajes observados.
- `id`: observación independiente única; la independencia debe justificarse en el estudio.
- `sample`: opcional; `train` (o vacío) para ajuste y `validation` para validación independiente.

Se requiere rango completo y más observaciones que parámetros: OLS/Poisson, n>3;
NB2, n>4. Esto es un mínimo numérico, no una garantía de calidad estadística.
Se detectan faltantes, no finitos, colinealidad exacta y valores negativos. Se
advierten colinealidad elevada, predicciones OLS negativas y extrapolación en validación.
Sin muestra independiente las métricas se identifican como ajuste dentro de muestra.

OLS es el inicio y usa `E[y|X] = intercepto + coeficientes × variables`.
Poisson y **binomial negativa NB2** se habilitan explícitamente para conteos enteros;
usan `E[y|X] = exp(intercepto + coeficientes × variables)`. NB2 estima la dispersión
de `Var(y|X)=μ+dispersion*μ²`, que no debe confundirse con α de atracción o α BPR.
Se rechazan ajustes sin convergencia o con incertidumbre no identificable. Se informa
RMSE/MAE, R² solo en OLS, verosimilitud/AIC para conteos y dispersión NB2 cuando corresponde.
Los intervalos OLS usan t de Student; los de máxima verosimilitud son asintóticos.

### Distribución

Fricción inicial exponencial `exp(-βc)`. La casilla **Habilitar potencia y combinada**
permite elegir `c^(-α)` o `c^α exp(-βc)`. Estas últimas requieren impedancias
estrictamente positivas; no se reemplazan ceros silenciosamente.

CSV largo: `origin,destination,trips`, con todas las celdas (incluidos ceros) y los
nombres exactos de zona. Los marginales observados deben coincidir con los ingresados
en la etapa. Las impedancias actuales deben representar la misma población y periodo.
Si se usan marginales observados, introdúzcalos en la tabla antes de calibrar.

Se minimiza SSE de las celdas OD y cada evaluación resuelve Furness completo.
Rangos exploratorios: α y β entre 0 y 10; se advierte si el ajuste alcanza una frontera.
No se entregan intervalos como si las celdas OD restringidas fueran observaciones
independientes. No se implementa aún calibración por bandas de longitud de viaje ni
comparación estadística automática de funciones: se puede estimar cada función habilitada.

### Elección modal

CSV largo: `id,mode,chosen,time,cost,available`. Tres filas por persona/viaje, con
IDs estables `m1`, `m2`, `m3` correspondientes al orden de los modos en la etapa.
La interfaz muestra la relación con los nombres editables. Renombrar no cambia el ID.

- `chosen` y `available`: 0/1. Una elección disponible por observación.
- Al menos dos modos disponibles; completar los atributos de las tres alternativas.
- `time`: minutos; `cost`: MXN. Para alternativas no disponibles, se aceptan ceros
  de relleno no negativos, excluidos del denominador de probabilidades.

MNL estima ASC_m2, ASC_m3, βt y βc por máxima verosimilitud; ASC_m1=0 identifica el
modelo. Se comprueba el rango de la matriz de información. Se muestran errores
estándar, intervalos asintóticos, verosimilitud, AIC y cuotas observadas/predichas.
Las métricas corresponden a la muestra de ajuste. No se implementa aún partición
automática de muestra o validación cruzada modal.

Los coeficientes positivos de tiempo/costo se muestran como diagnóstico, pero no
pueden aplicarse al modelo actual, que exige βt, βc≤0; nunca se truncan. El valor del
tiempo `60*βt/βc` se informa en MXN/h solo si ambos intervalos están completamente
por debajo de cero. Los multiplicadores y constantes de tiempo/costo actuales se
conservan: el usuario debe comprobar que sus atributos coincidan con los de la encuesta.

## Asignación

### Todo-o-Nada

Misma carga de demanda y rutas libres de la versión 3.0. Costos positivos fijos;
la capacidad solo diagnostica v/c. Dijkstra usa orden de nodos e identificador de
arco para resolver empates reproduciblemente. Ejecución directa: no se etiqueta
como convergida. La demanda intrazonal se contabiliza sin cargar enlaces.

### Wardrop UE

Equilibrio estático determinista de usuario por Frank–Wolfe, costos de enlace
separables, continuos, positivos y no decrecientes. La interfaz ofrece BPR:

`t(v)=t0*[1+α*(v/C)^β]`.

Requiere centroides distintos, red dirigida, tiempos libres y capacidades positivos;
matriz en vehículos del periodo y capacidades en vehículos por el mismo periodo.
Si la OD contiene personas hay que convertirla antes: no se estima ocupación.
Los valores ilustrativos α=0.15 y β=4 son editables, no una calibración local.
La interfaz admite α∈[0,100], β∈[1,20]; requiere tolerancia positiva≤1 y un entero
positivo de actualizaciones máximas. No se implementa calibración BPR en esta entrega.

Se inicia con una AON a flujo cero y se resuelven AON auxiliares con tiempos actuales.
La búsqueda de paso minimiza Beckmann mediante la raíz de su derivada direccional
por bisección en [0,1]. No se utilizan costos marginales sociales, propios del óptimo
del sistema, para calcular las rutas UE.

**Brecha relativa:** `max(0, Σt*x - Σt*y) / Σt*x`, donde `y` es la AON auxiliar.
Con demanda interzonal nula, la brecha es cero. Se evalúa también en el último flujo
devuelto al agotar el límite. Iteración 0 significa flujo inicial; el historial tiene
una observación más que las actualizaciones. Tolerancia 0.01 significa 1%, distinta
de la tolerancia de balanceo Furness. Se informa si no converge.

Las rutas mínimas finales son referencias con demanda OD, no una descomposición
de flujos de equilibrio por ruta. Los flujos finales se reportan por enlace. Las
funciones lineales del ejemplo original se admiten en el motor mediante función
de costo inyectable y se verifican con 500/500 vehículos y 20/20 min.

### Comparación y exportación

**Comparar métodos** calcula AON y UE sobre la misma captura de OD/red. AON elige
rutas con tiempos libres, después sus flujos se evalúan con la misma BPR usada por
UE. Se reportan flujos, diferencias absolutas/porcentuales (indefinidas con base cero),
tiempos, v/c, tiempo total veh·min y media interzonal. UE no garantiza minimizar
el tiempo total del sistema. No se incluye óptimo del sistema.

CSV exporta ambos flujos, función de evaluación, brecha final y convergencia. GraphML
conserva tiempos libres y finales. El reporte LaTeX incluye parámetros finales,
procedencia, diagnósticos aplicados y comparación; mantiene carta y excluye `fontenc`.
Exportar `.tex` sigue siendo distinto de compilar automáticamente un PDF.

## Persistencia y compatibilidad

Esquema `.mnet` 2, JSON sin código ejecutable y guardado atómico. Se leen archivos
de esquema 1 de MacroNet 3.0 con OLS, exponencial y AON como valores predeterminados.
Se conservan borradores separados de últimas entradas calculadas y resultados
auditables de asignación/comparación. Al abrir se reconstruyen resultados con
las instantáneas válidas; luego se restauran los cambios todavía sin calcular.
Abrir archivos inválidos no sustituye el ejercicio activo. Esquemas futuros se rechazan.

## Apariencia y portabilidad

Latin Modern Roman regular, negrita, cursiva y negrita cursiva incluidas sin modificar,
con avisos de licencia GUST/LPPL. No se exige instalar TeX para usar la aplicación.
Grises neutrales y paleta explícita para campos, tablas, mensajes, selección y gráficos.
**Apariencia → Seguir al sistema / Claro / Oscuro**. Cada etapa permite desplazamiento
vertical/horizontal y las tablas se pueden redimensionar. Los cambios de presentación
no modifican datos ni ecuaciones.

## Verificación y referencias

Pruebas de regresión del caso original; soluciones analíticas AON/UE; conservación,
demanda nula, desconexión, desbordamientos, no convergencia; recuperación de parámetros
con datos sintéticos; rechazo de colinealidad; mapeo, aplicación explícita y reapertura;
reporte carta sin `fontenc`; contraste y tipografía. CI Ubuntu/Windows y Python
3.11/3.12/3.14. Las pruebas sintéticas verifican el software, no validan modelos locales.

- SciPy, optimización: https://docs.scipy.org/doc/scipy/reference/optimize.html
- statsmodels, modelos estadísticos: https://www.statsmodels.org/stable/api.html
- Train, *Discrete Choice Methods with Simulation*, cap. 3:
  https://eml.berkeley.edu/books/choice2.html

Autoría: Héctor Alonso Benítez García. Software GPL-3.0-only. Se conservan las
licencias originales de las fuentes. La propuesta fuente también menciona calibración
de BPR, óptimo del sistema y validaciones ampliadas: quedan como trabajo posterior
dentro de la familia 3.x, no como funcionalidades ya implementadas.
