# Bitácora de versiones — MacroNet Transport

## 3.3.2 — 2026-10-31

- Resumen de las cuatro etapas con indicadores, participación modal, congestión
  por relación volumen/capacidad y resultados SUMO cuando estén disponibles.
- Informe LaTeX ampliado con parámetros, ecuaciones, gráficas autocontenidas,
  conclusiones numéricas y anexos con matrices OD y variables de entrada.
- Instalador completo para Windows x64 de la misma versión 3.3.2, con Python,
  bibliotecas y SUMO 1.28.0 incluidos; informes `.tex` para Overleaf, sin LaTeX.
- Comprobación del número de versión del ejecutable instalado, del Resumen y
  de la exportación real del informe con gráficas autocontenidas y matrices.
- Se conservan los modelos de cálculo y la compatibilidad de los ejercicios.

## 3.3.1 — 2026-10-31

- Instalador completo para Windows x64 con Python, bibliotecas, fuentes y la
  distribución oficial de Eclipse SUMO 1.28.0, verificada mediante SHA256.
- Instalación por usuario, acceso directo al escritorio y menú Inicio,
  desinstalador y carpeta de trabajo inicial en Documentos/MacroNet.
- Detección automática prioritaria del SUMO incluido; se conserva la selección
  manual del motor y la ejecución desde código fuente en Linux y Windows.
- Aislamiento de bibliotecas al ejecutar el motor nativo desde PyInstaller y
  manejo de entrada estándar para aplicaciones sin consola.
- Compatibilidad con rutas de instalación con acentos: los esquemas de SUMO se
  consultan con una ruta local relativa para evitar un fallo del lector XML nativo.
- Construcción en GitHub Actions, prueba del ejecutable instalado con PATH
  aislado, escenario SUMO real de 19 vehículos, exportaciones, calibración,
  fuentes, persistencia, render de pestañas y comprobación de desinstalación.
- Incluye licencias, inventario de componentes y fuente exacta de MacroNet.
  Los informes siguen exportándose en `.tex` para compilar en Overleaf.
- Distribución inicial para prueba docente; la verificación visual final en
  Windows 11 se realiza antes de compartirla con los estudiantes.

## 3.3.0 — 2026-10-28

- Tarifas opcionales por modo en elección modal: plana, intervalos de distancia,
  por kilómetro y mixta. El cálculo anterior se conserva como predeterminado.
  Los esquemas activos sustituyen el costo monetario anterior sin doble cobro.
- Matrices de distancias en km por modo, con procedencia explícita, captura,
  plantilla e importación/exportación CSV; matrices de costos en MXN y vista previa.
- Intervalos con límites crecientes, inclusión explícita del extremo superior y
  último intervalo sin límite; validación de distancias, importes y cobertura.
- Hasta 20 instantáneas tarifarias por ejercicio y comparación de participación
  y viajes con la misma base. Se conserva el total OD; los contextos o distancias
  diferentes no se presentan como efecto exclusivo de la tarifa.
- Configuración e instantáneas guardadas en `.mnet`, CSV con costos/distancias y
  detalle modal, e informe carta con reglas, matrices y comparación de escenarios.
  Esquema de archivo 4, con lectura de esquemas 1, 2 y 3.
- Ayuda → Acerca de con descripción, autoría, GPL-3.0-only y opción Contacto:
  correo de contacto `prof.benitezgh@gmail.com`, copia y apertura del cliente de correo.
- Integración mediante un botón en elección modal y los diálogos necesarios;
  se conserva la apariencia general, distribución, asignación y motor SUMO.

## 3.2.0 — 2026-10-24

- Integración opcional de Eclipse SUMO después de la asignación, conservando
  las cuatro etapas, AON/Wardrop, la calibración y las exportaciones existentes.
- Geometría vial editable, correspondencia de nodos/arcos y TAZ por centroide;
  conversión explícita de viajes-persona a vehículos, multiplicador de demanda,
  redondeo por resto mayor y exclusión documentada de viajes intracentroide.
- Referencia estática recalculada con la misma OD vehicular y tiempos de flujo
  libre de la geometría. Enrutamiento único con esos costos, sin presentar el
  resultado como equilibrio dinámico ni como reproducción del reparto UE.
- Ejecución sin GUI mediante netconvert/duarouter/sumo, en un trabajador separado,
  con cancelación de procesos, límite de tiempo real y cierre seguro de la ventana.
- Indicadores de recorridos completados, vehículos pendientes/en red/retirados,
  evolución temporal y contraste por arco. Carpeta única por escenario con XML,
  CSV, semillas, versiones, comandos, huellas de archivos y registros de errores.
- `.mnet` esquema 3: configuración, borradores de geometría y última ejecución;
  conserva compatibilidad de lectura con esquemas 1 y 2. Reporte LaTeX carta con
  una sección separada de microsimulación y aviso de resultados anteriores.
- Dependencia SUMO opcional (`.[sumo]`), exportación de escenarios sin el motor
  instalado y guía de instalación, metodología y límites de la primera integración.
- Pruebas de motor real, conservación, reproducibilidad, cancelación, respuesta
  gráfica, persistencia, archivos antiguos y CI adicional con SUMO en Ubuntu/Windows.

## 3.1.1 — 2026-10-23

- Corregido el crecimiento continuo de las gráficas al abrir **Convergencia UE**
  dentro de la ventana completa, que podía bloquear la aplicación y provocar
  una violación de segmento. El tamaño recomendado del lienzo se conserva
  independiente del tamaño asignado por el diseño de Qt.
- Prueba de regresión con la ventana visible y el bucle de eventos activo:
  convergencia UE, cambios de pestaña, redimensionamiento, temas claro/oscuro y
  conservación del historial numérico. Se ejecuta en un proceso separado para
  detectar bloqueos y cierres nativos.

## 3.1.0 — 2026-10-22

Actualización de la familia 3.x según la propuesta de calibración y asignación;
se conserva el flujo manual y AON como selección inicial.

- Asignación Wardrop UE por Frank–Wolfe con BPR editable (α=0.15, β=4), brecha
  relativa, límite de actualizaciones, estado de convergencia e historial gráfico.
- Comparación reproducible AON/UE sobre la misma OD y red; evaluación BPR de
  flujos AON sin alterar las rutas de flujo libre; CSV comparativo y GraphML con tiempos.
- Motor de calibración independiente de Qt: OLS para producción y atracción,
  Poisson/NB2 habilitables, calibración de gravedad con Furness completo y MNL
  desagregado con disponibilidad e identificación mediante ASC de referencia cero.
- Importación CSV con mapeo de columnas, plantillas, diagnóstico, intervalos,
  residuales, cuotas modales y aplicación explícita; controles manuales conservados.
- Funciones de fricción potencia y combinada habilitables; exponencial predeterminada.
- `.mnet` esquema 2: observaciones, mapeo, procedencia, modelos y diagnósticos por
  etapa, configuración de asignación y resultados auditables; apertura de esquema 1.
- Reportes carta sin `fontenc`, con parámetros, diagnósticos y comparación de asignación.
- Interfaz neutral en grises, tipografía Latin Modern Roman incluida con su licencia,
  temas claro/oscuro/sistema y desplazamiento para pantallas pequeñas.
- Pruebas analíticas del ejercicio lineal 500/500 vehículos y 20/20 minutos,
  conservación de flujo, estimación, sesiones antiguas y reapertura completa.
- Autoría y licencia GPL-3.0-only preservadas. No se cambia a versión 4.

## 3.0.0 — 2026-10-22

Entrega solicitada como versión 3.0; sucede directamente a 0.2.0.

- Nombre del usuario solicitado en cada exportación del informe LaTeX.
- Informe en tamaño carta, sin `\usepackage[T1]{fontenc}`.
- Abrir, guardar y guardar como ejercicios completos `.mnet`, con esquema
  versionado, validación y escritura atómica.
- Conservación de datos, parámetros, red, nombre del usuario, últimos cálculos
  válidos y borradores pendientes de calcular.
- Aviso de cambios sin guardar al abrir otro ejercicio o cerrar.
- CSV de las matrices de todos los modos, con marginales y nombres personalizados.
- Nombres editables de los tres modos documentados y verificados en todas las etapas.
- Selector explícito del modo a asignar, conservado al renombrar alternativas.
- Confirmación de la celda activa al guardar con Ctrl+S o cerrar la aplicación.
- Pruebas automatizadas ampliadas y CI en Ubuntu/Windows, Python 3.11/3.12/3.14.
- Dependencia Qt limitada a versiones anteriores a 6.12 tras reproducir un fallo
  de destrucción de tablas en PySide6 6.12.0 con Python 3.11; verificada 6.11.2.
- Versión 0.2.0 preservada en `release/v0.2.0` antes del desarrollo.

## 0.2.0 — 2026-09-06

- Distribución: tolerancia predeterminada 0.01 y máximo 100 iteraciones.
- CSV de matriz OD, GraphML de la red y visor ampliado.
- Pestaña Resumen e informe LaTeX.
- Integrada mediante PR #8; versión anterior conservada en `release/v0.1.0`.

## 0.1.0 — 2026-09-05

- Base educativa de cuatro etapas: generación/atracción, distribución
  gravitacional/Furness, elección modal logit y asignación Todo-o-Nada/Dijkstra.
- Correcciones de contraste, sincronización de nombres de zona y autoría.

La bitácora histórica compartida por el desarrollador conserva el detalle
documental de conversaciones y decisiones anteriores. Esta bitácora registra
las versiones del repositorio y no atribuye implementación a propuestas futuras.


