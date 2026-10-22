# Bitácora de versiones — MacroNet Transport

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
- Pruebas automatizadas ampliadas y CI en Ubuntu/Windows, Python 3.11/3.12.
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
