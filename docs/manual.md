# Manual de usuario · MacroNet Transport

MacroNet es una herramienta de modelación macroscópica para estudiar la demanda y
su asignación a una red. El ejercicio se organiza en cuatro etapas. La
microsimulación vehicular con SUMO es opcional y se ejecuta por separado.

## Iniciar, guardar y abrir

- **Archivo → Nuevo** crea un ejercicio vacío. Captura tus datos en la etapa 1 o
  selecciona **Proyecto → Cargar caso demostrativo** para trabajar con cuatro
  zonas y una red ficticia. El demostrativo no se carga al iniciar.
- **Archivo → Guardar / Abrir** conserva datos, resultados calculados y capturas
  pendientes en un archivo `.mnet`. Los proyectos parciales requieren MacroNet
  3.4 o posterior.
- **Vista** cambia entre tema claro y oscuro. La rueda desplaza el panel; cambia
  los campos numéricos con el teclado o con las flechas del control.

## Resolver el modelo

| Etapa | Datos y acción | Cómo leer la salida |
| --- | --- | --- |
| 1. Generación y atracción | Agrega zonas. Captura hogares, vehículos, empleos y estudiantes. Revisa los coeficientes y pulsa **Calcular**. | La producción y la atracción inicial se estiman por zona. El factor de balanceo escala las atracciones para igualar la producción total. |
| 2. Distribución | Captura la matriz de impedancias; usa la misma unidad en todas las celdas. Pulsa **Distribuir viajes**. | La matriz OD contiene viajes, no impedancias. Revisa marginales y error final antes de usarla; si no se alcanza la tolerancia, revisa los insumos. |
| 3. Elección modal | Edita nombres, tiempos, costos y coeficientes de las alternativas. Si aplica, configura las [tarifas](fares.md). | La participación indica cómo se repartió la demanda OD bajo los supuestos del caso. El reparto no valida los coeficientes ni estima viajes inducidos. |
| 4. Asignación | Elige un modo, indica los nodos centroides y agrega arcos dirigidos con tiempo libre y capacidad. Usa Todo o Nada o Wardrop. | Todo o Nada usa tiempos libres. Wardrop aplica la función BPR; revisa la brecha y si el cálculo convergió. Una relación v/c alta señala presión sobre la capacidad; no equivale a un nivel de servicio HCM. |

Con las entradas preparadas, **Proyecto → Simular → Calcular las cuatro etapas**
ejecuta todo en orden. Si falta un dato, abre la etapa que lo requiere. Puedes
[revisar los casos de ejemplo](examples/) para contrastar los cálculos.

## Microsimulación con SUMO

Desde **Proyecto → Simular → Microsimulación con SUMO…**, revisa la geometría,
unidades de demanda, duración y semilla antes de ejecutar. La geometría inicial es
una propuesta editable. Su comparación usa una referencia estática con la misma
demanda vehicular y los tiempos libres de la geometría. Consulta la
[guía de SUMO](sumo-integration.md) para configuración, supuestos y resultados.

## Resumen y exportaciones

**Archivo → Exportar** reúne el informe LaTeX, las matrices OD y modales, los
flujos y la red GraphML. El informe conjunto requiere resultados de las cuatro
etapas. Incluye una síntesis numérica, interpretación por etapa y matrices en
anexos. Los datos son los de los últimos cálculos válidos; vuelve a calcular si
editaste entradas que aún no se reflejan en los resultados.

El informe es autocontenido en tamaño carta. En **Ayuda → Compilar .tex en
Overleaf**, crea un proyecto en blanco, sube el archivo y selecciónalo como
documento principal. Compila con **pdfLaTeX** y descarga el PDF.
