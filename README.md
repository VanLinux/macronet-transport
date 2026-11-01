# MacroNet Transport

**MacroNet** es una aplicación educativa, interactiva y de código abierto para estudiar el modelo clásico de transporte de cuatro etapas.

El proyecto busca que el estudiante pueda observar el proceso completo, modificar datos y parámetros, revisar ecuaciones y cálculos intermedios, y comprobar cómo cada decisión afecta las etapas posteriores.

## Alcance actual

La versión `3.3.2` (familia **3.x**) incluye:

1. Generación y atracción de viajes.
2. Distribución de viajes.
3. Elección modal.
4. Asignación de viajes a la red.
5. Resumen integrado de resultados.

También permite guardar y reabrir ejercicios completos en `.mnet`, exportar la matriz
origen-destino y las matrices de los tres modos en CSV, la red asignada en GraphML
y un informe ampliado en LaTeX con el nombre del usuario. El informe se configura
en tamaño carta y no utiliza `fontenc`. Incluye gráficas autocontenidas con PGFPlots
y matrices en anexos; puede compilarse con `pdflatex` u Overleaf. La red GraphML conserva dirección, tiempos de flujo
libre, capacidades, flujos y relaciones volumen/capacidad para su análisis en Gephi.

Cada módulo deberá separar el modelo matemático de la interfaz gráfica y conservar resultados intermedios para su explicación y validación manual.

## Principios del proyecto

- **Educativo:** explica el procedimiento, no solo entrega el resultado.
- **Interactivo:** permite modificar datos y observar sus efectos.
- **Transparente:** muestra ecuaciones, unidades, supuestos y cálculos intermedios.
- **Verificable:** incluye casos pequeños que pueden resolverse manualmente.
- **Modular:** cada etapa puede estudiarse por separado o dentro del flujo completo.
- **Libre:** se distribuye bajo la licencia GNU GPL v3.0.

## Estado

El proyecto incluye un recorrido funcional por las cuatro etapas: generación y atracción,
distribución gravitacional, elección modal logit y asignación Todo-o-Nada o Wardrop UE.
Se conservan los parámetros manuales y se añade calibración por etapa con datos observados.
La interfaz usa Latin Modern Roman y temas neutrales claro/oscuro; el menú **Apariencia**
permite seguir al sistema o elegir un tema. Las fuentes incluidas conservan su licencia GUST/LPPL.
La pestaña **Microsimulación SUMO** añade evaluación vehicular opcional después de
la asignación: geometría editable, conversión de personas a vehículos, demanda
temporal, ejecución cancelable, indicadores y contraste con una referencia estática.
Las cuatro etapas siguen funcionando sin instalar SUMO.
La versión anterior se conserva en `release/v3.2.0`. Las ramas históricas
`release/v0.2.0` y `release/v0.1.0` siguen disponibles. La numeración pasó de
0.2.0 a 3.0.0 por decisión del proyecto y continúa dentro de la familia 3.x.

## Guardar, continuar y exportar

- **Archivo → Guardar ejercicio** (`Ctrl+S`) y **Guardar ejercicio como**
  (`Ctrl+Shift+S`) guardan el ejercicio completo en `.mnet`.
- **Archivo → Abrir ejercicio** (`Ctrl+O`) recupera zonas, coeficientes,
  marginales editados, impedancias, parámetros de distribución, los tres modos,
  centroides, arcos, modo asignado y nombre del usuario. Se reconstruyen los últimos
  resultados válidos y se conservan las celdas todavía en edición. Pulse el botón
  de cálculo de la etapa correspondiente para aplicar esos cambios pendientes.
- El asterisco del título identifica cambios sin guardar. Al abrir otro archivo
  o cerrar se ofrece guardar, descartar o cancelar.
- En **Elección modal**, edite los nombres de los tres modos en la primera columna
  y pulse **Calcular elección modal**. Deben ser únicos y no estar vacíos.
  **Descargar matrices de todos los modos (.csv)** guarda un único archivo con un
  bloque de matriz y marginales por modo, etiquetas y precisión numérica.
- En **Asignación**, elija explícitamente el modo cuya demanda cargará en la red.
  La selección se conserva al renombrar modos; revise que la red represente ese modo.
  **Todo-o-Nada** mantiene las rutas de flujo libre. **Wardrop UE** usa Frank–Wolfe
  y BPR; solicita α, β, tolerancia de brecha relativa y máximo de actualizaciones.
  La demanda vial y las capacidades deben corresponder al mismo periodo y estar
  en vehículos. **Comparar métodos** ejecuta ambos sobre la misma OD y red, evalúa
  los tiempos con la misma BPR y habilita el CSV comparativo. No confundir UE con
  el óptimo del sistema.
- En las tres primeras etapas, **Origen de parámetros → Estimados** habilita
  **Importar, estimar y revisar**. Descargue la plantilla, importe observaciones,
  mapee columnas y revise los diagnósticos. Los coeficientes solo se sustituyen al
  pulsar **Aplicar parámetros estimados**; después pulse **Calcular** en la etapa.
  Producción y atracción se estiman por separado mediante OLS inicialmente. Poisson
  y binomial negativa NB2 requieren habilitación explícita y usan enlace logarítmico.
  Distribución comienza con fricción exponencial; potencia y combinada se habilitan
  con una casilla. La calibración modal estima MNL con las alternativas estables
  `m1/m2/m3`, disponibilidad y un modo elegido por observación.
- En **Resumen → Descargar informe (.tex)** se solicita el nombre del usuario
  en cada exportación. El nombre anterior se ofrece como valor inicial y se guarda
  en el ejercicio. El archivo se compila con `pdflatex resumen_macronet.tex` para
  obtener un PDF carta. El programa exporta la fuente `.tex`; no requiere LaTeX
  para ejecutar los modelos.

## Tarifas y costos de viaje

En **3. Elección modal → Tarifas y costos de viaje…** puede conservar el cálculo
actual o elegir, para cada modo, una tarifa plana, por intervalos, por kilómetro
o mixta. Un esquema activo sustituye el costo fijo + variable anterior del modo.
Los importes son MXN por persona y viaje; las tarifas por distancia requieren
su propia matriz en km, con origen sobre red o estimación entre zonas.

El editor permite importar/exportar distancias, consultar costos monetarios y
guardar escenarios para compararlos con la misma OD, tiempos y coeficientes.
La configuración, distancias e instantáneas se guardan en `.mnet`; los costos y
resultados se exportan en CSV y se incorporan al informe LaTeX. Consulte
[`docs/fares.md`](docs/fares.md) para unidades, límites y comparación.

En **Ayuda → Acerca de… → Contacto** encontrará el correo del autor,
`prof.benitezgh@gmail.com`, con opciones para copiarlo o abrir su aplicación de correo.

## Tecnología prevista

- Python 3.11 o posterior.
- PySide6 para la aplicación de escritorio.
- NumPy y pandas para cálculo y datos.
- SciPy y statsmodels para estimación, optimización y diagnósticos.
- NetworkX para redes y asignación.
- Matplotlib para visualizaciones didácticas.
- pytest para pruebas automatizadas.

## Microsimulación opcional con SUMO

En el entorno virtual existente, instale el motor opcional:

```bash
python -m pip install -e ".[sumo]"
macronet
```

También puede utilizar una instalación del sistema de Eclipse SUMO 1.18 o posterior.
En Ubuntu: `sudo apt install sumo sumo-tools`. En **Microsimulación SUMO**, pulse
**Comprobar SUMO**; si no se detecta, seleccione su carpeta `bin`.

Después de calcular la asignación, revise el modo vial, las unidades de la OD,
la ocupación, el periodo, la geometría y la capacidad por periodo. Confirme la
revisión y pulse **Ejecutar SUMO…**. Se crea una carpeta nueva con escenario,
registros, manifiesto, resultados XML y `comparison.csv`. El botón **Exportar
escenario sin ejecutar…** funciona aunque SUMO no esté instalado.

El ejercicio `.mnet` conserva configuración, geometría, indicadores y procedencia;
los XML y registros completos permanecen en la carpeta de ejecución. La apertura
de un ejercicio no ejecuta SUMO. La guía, supuestos y límites están en
[`docs/sumo-integration.md`](docs/sumo-integration.md).

## Ejecución durante el desarrollo

### Windows: instalador completo para estudiantes

En [Releases](https://github.com/VanLinux/macronet-transport/releases) se publica
el instalador completo de Windows 11 x64, una vez superada la construcción y
verificación automática. Descargue el archivo `MacroNet-Transport-3.3.2-Windows-x64-Setup.exe`,
ábralo y siga el asistente. El acceso directo inicia MacroNet sin terminal.
El instalador corresponde a la versión 3.3.2 e incluye el Resumen actualizado
y el informe ampliado con gráficas autocontenidas y matrices en anexos.
Incluye Python, sus bibliotecas y Eclipse SUMO 1.28.0; no necesita instalaciones
adicionales ni Internet para calcular. SUMO se detecta dentro de MacroNet aunque
ya exista otro motor en el equipo. No se modifica el PATH del sistema.

Los informes `.tex` pueden compilarse en Overleaf; no se incluye LaTeX.
El instalador no está firmado digitalmente. Se recomienda comprobarlo en el equipo
docente antes de compartirlo con el grupo. Véase [la guía de Windows](docs/windows-installer.md).

### Desde el código fuente (Linux o Windows)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m macronet
```

En Windows, la activación del entorno virtual se realiza con:

```powershell
.venv\Scripts\activate
```

## Pruebas

```bash
pytest
```

## Documentación

El alcance funcional de la primera versión se encuentra en [`docs/scope-v0.1.md`](docs/scope-v0.1.md).

Las incorporaciones de la versión 3.0 se documentan en
[`docs/scope-v3.0.md`](docs/scope-v3.0.md), y su historial en
[`CHANGELOG.md`](CHANGELOG.md).

La asignación y calibración de la versión 3.1, sus datos de entrada, supuestos y
compatibilidad se describen en [`docs/scope-v3.1.md`](docs/scope-v3.1.md).

Las incorporaciones de la versión 0.2 se documentan en [`docs/scope-v0.2.md`](docs/scope-v0.2.md).

El caso didáctico incluido en el primer módulo está documentado en [`docs/examples/generation-four-zones.md`](docs/examples/generation-four-zones.md).

La distribución del mismo caso se documenta en [`docs/examples/distribution-four-zones.md`](docs/examples/distribution-four-zones.md).

La elección modal se desarrolla en [`docs/examples/mode-choice-four-zones.md`](docs/examples/mode-choice-four-zones.md).

La asignación de la demanda de automóvil se documenta en [`docs/examples/all-or-nothing-four-zones.md`](docs/examples/all-or-nothing-four-zones.md).


