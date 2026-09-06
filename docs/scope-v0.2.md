# Alcance funcional de MacroNet Transport 0.2.0

La versión 0.2.0 amplía el recorrido educativo estable de las cuatro etapas sin cambiar
los modelos matemáticos de la versión anterior.

## Cambios principales

- Tolerancia predeterminada de 0.01 viajes y máximo de 100 iteraciones en Distribución.
- Exportación de la matriz origen-destino con marginales en CSV UTF-8.
- Vista ampliada de la red asignada.
- Exportación GraphML compatible con Gephi y NetworkX.
- Pestaña Resumen actualizada automáticamente por las cuatro etapas.
- Informe LaTeX con resultados zonales, convergencia, participación modal y flujos.

## Formatos abiertos

Los archivos exportados no dependen de servicios externos:

- CSV para matrices y hojas de cálculo.
- GraphML para redes dirigidas con atributos.
- LaTeX para informes reproducibles y editables.

## Compatibilidad

La versión funcional previa se conserva en la rama `release/v0.1.0`. La versión 0.2.0
mantiene el mismo caso didáctico y la propagación automática entre etapas.
