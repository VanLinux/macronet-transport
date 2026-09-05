# Alcance funcional de MacroNet 0.1

## Propósito

MacroNet 0.1 será una aplicación de escritorio para enseñar el modelo clásico de transporte de cuatro etapas mediante un caso pequeño, trazable y verificable manualmente.

No será una herramienta de simulación dinámica del tránsito ni intentará reproducir todavía el alcance de plataformas comerciales.

## Experiencia educativa mínima

En cada etapa, el estudiante podrá:

1. Consultar el objetivo y los supuestos del modelo.
2. Capturar o importar datos.
3. Consultar las ecuaciones y las unidades utilizadas.
4. Ejecutar el cálculo paso a paso.
5. Inspeccionar resultados intermedios.
6. Modificar parámetros y comparar escenarios.
7. Exportar tablas y resultados.

## Flujo de trabajo

### 1. Generación y atracción

- Definición de zonas.
- Variables socioeconómicas y de uso de suelo.
- Producciones y atracciones por zona.
- Comprobación de totales y balanceo.

### 2. Distribución

- Matriz de impedancias.
- Modelo gravitacional como método inicial.
- Factores de fricción y balanceo iterativo.
- Matriz origen-destino y comprobaciones marginales.

### 3. Elección modal

- Alternativas de transporte.
- Utilidades y variables explicativas.
- Modelo logit multinomial como método inicial.
- Probabilidades y matrices por modo.

### 4. Asignación

- Nodos, arcos, capacidades y tiempos.
- Rutas mínimas.
- Asignación Todo-o-Nada como método inicial.
- Flujos por arco y visualización de la red.

## Caso didáctico inicial

El primer caso utilizará entre tres y cinco zonas y una red pequeña. Todos los datos, cálculos y resultados de referencia deberán documentarse para que puedan reproducirse con calculadora o una hoja de cálculo.

## Fuera del alcance de 0.1

- Simulación microscópica o mesoscópica.
- Modelos dinámicos de flujo vehicular.
- Calibración automática con grandes bases de datos.
- Integración GIS avanzada.
- Redes metropolitanas de gran escala.
- Reproducción completa de PTV Visum u otros productos comerciales.

## Criterios de aceptación

- El recorrido completo puede ejecutarse con el caso didáctico.
- Cada resultado muestra su procedencia y unidades.
- Los resultados coinciden con el caso resuelto manualmente.
- Los errores de captura se explican con mensajes claros.
- El núcleo matemático puede probarse sin iniciar la interfaz.
- La aplicación puede empaquetarse para Windows sin requerir Python instalado.
