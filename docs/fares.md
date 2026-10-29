# MacroNet Transport 3.3.0 · Tarifas y costos de viaje

La extensión se utiliza desde **3. Elección modal → Tarifas y costos de viaje…**.
El diálogo conserva la apariencia de la aplicación. La opción inicial de cada
modo es **Cálculo actual**, que usa `C = costo fijo + costo variable × impedancia`
y reproduce los resultados de las versiones anteriores.

## Esquemas por modo

| Esquema | Costo monetario del viaje |
|---|---|
| Cálculo actual | Fórmula anterior del ejercicio |
| Tarifa plana | `C = F` |
| Intervalos de distancia | Tarifa total del intervalo que contiene la distancia |
| Por kilómetro | `C = r × d` |
| Mixta | `C = F0 + r × d` |

Los importes activos se expresan en **MXN por persona y viaje**, las distancias
en **km** y los tiempos del modelo en **minutos**. Use coeficientes de utilidad
compatibles: βc por MXN y βt por minuto. Los esquemas activos **sustituyen** el
costo anterior del modo; no se suma otra vez su costo fijo o variable.

La utilidad sigue siendo `ASC + βt × tiempo + βc × costo`. Los coeficientes
manuales y los estimadores estadísticos continúan disponibles. La tarifa no se
agrega automáticamente a la distribución ni se convierte en peaje de una ruta.

Para intervalos, capture límites superiores positivos y crecientes. La primera
fila representa `0 ≤ d ≤ límite`; las siguientes `límite anterior < d ≤ límite`.
Deje vacío el límite de la última fila para cubrir toda distancia superior.
No se admiten filas sin tarifa, límites repetidos o decrecientes, valores negativos
o no finitos. La tarifa cero sí permite representar un servicio gratuito.

Ejemplo hipotético: hasta 5 km, 8 MXN; hasta 10 km, 12 MXN; sin límite, 25 MXN.
Un viaje de 5 km cuesta 8; de 7.5 km, 12; de 10 km, 12; de más de 10 km, 25.
La aplicación no redondea primero la distancia para decidir el intervalo.

## Distancias

La tarifa plana no necesita distancias. Los otros tres esquemas requieren una
matriz completa por modo y la selección de su origen: **Sobre la red** o
**Estimación entre zonas**. El campo de fuente permite documentar método, fecha
o procedencia. La matriz no se obtiene automáticamente de los tiempos, de la
impedancia de distribución, de coordenadas ni de SUMO.

Use **Plantilla de distancias (.csv)** para obtener los encabezados y el orden
de zonas. Complete todas las celdas con distancias no negativas en km, incluidas
las intrazonales, y pulse **Importar distancias (.csv)**. El CSV utiliza coma como
separador y admite números con punto decimal; una coma decimal debe ir dentro
de una celda CSV entrecomillada. Unidades y orden se validan antes de sustituir
la tabla. También se pueden capturar o exportar las distancias desde el diálogo.

Los viajes intrazonales reciben la tarifa correspondiente a su distancia; no
se suponen gratuitos. Se permite una distancia intrazonal positiva estimada.
Al renombrar zonas en el editor del ejercicio se conservan las posiciones de la
matriz. Si cambia su dimensión, se exige revisar y completar las distancias.

## Vista previa y aplicación

Seleccione un modo en la parte superior. En **Matriz de costos**, pulse
**Calcular vista previa** para revisar los costos de ese modo. La vista previa
valida las configuraciones de todos los modos y no modifica el ejercicio.

**Aplicar y calcular** conserva las configuraciones y recalcula elección modal
cuando cambian las tarifas; los resultados se propagan según el flujo habitual
del programa. **Cancelar** descarta las modificaciones del diálogo. Los modos
que mantienen Cálculo actual siguen usando sus costos anteriores.

**Restaurar parámetros**, en la pantalla principal de elección modal, restablece
también el cálculo tarifario predeterminado. Las instantáneas guardadas se
conservan como escenarios independientes.

## Escenarios tarifarios

En **Escenarios tarifarios → Guardar escenario actual…**, asigne un nombre único.
Se guardan OD total, tiempos/impedancias, nombres y parámetros de los modos,
coeficientes y tarifas con sus distancias. Se admiten hasta 20 escenarios.
Los cambios de la lista se confirman con **Aplicar y calcular**; guardar sólo
escenarios no reemplaza los parámetros del ejercicio ni recalcula sus resultados.

**Comparar escenarios** presenta viajes y participación por modo, y diferencias
respecto al primer escenario. Se exige la misma OD, tiempos, modos y coeficientes.
Los esquemas dependientes de distancia deben utilizar la misma matriz y origen
de distancias por modo. Una tarifa plana puede compararse con un esquema por
distancia aunque no haya necesitado distancias para calcular su costo.

Si los contextos difieren, las instantáneas se conservan y se pueden exportar,
pero la comparación de efectos tarifarios se rechaza. El informe identifica
los contextos distintos y muestra sus resultados como independientes.

El total de viajes de cada par OD se conserva. Cambiar el precio redistribuye
esos viajes entre modos; no calcula viajes inducidos, cambios de destino,
asignación de pasajeros a servicios o equilibrio dinámico. La validez como
pronóstico depende de datos y coeficientes adecuados al caso de estudio.

## Guardado y exportación

- `.mnet`: guarda las tarifas en edición y las aplicadas, distancias e instantáneas.
  La versión 3.3.0 lee los esquemas de archivo 1, 2 y 3 y escribe el esquema 4.
  Un archivo nuevo requiere esta versión o posterior para preservar las tarifas.
- **Exportar costos, distancias y elección modal (.csv)…**: exporta la vista previa
  con reglas, distancia utilizada, procedencia, costo, tiempo, utilidad,
  probabilidad y viajes por modo/OD. Para una tarifa plana o el cálculo actual,
  la columna de distancia queda vacía porque no interviene en esa fórmula.
- **Exportar escenarios (.csv)…**: exporta el detalle de todas las instantáneas,
  incluyendo sus coeficientes y parámetros originales. Las matrices modales CSV
  anteriores mantienen su formato y su botón habitual.
- El informe LaTeX de **Resumen** sigue siendo carta y sin `fontenc`. Añade reglas,
  procedencia, matrices de costos/distancias usadas y resultados de escenarios.
  El cuerpo principal conserva los últimos cálculos válidos; las instantáneas
  se identifican por su propio nombre y contexto.

## Contacto

En **Ayuda → Acerca de… → Contacto**, el correo del autor es
`prof.benite.gh@mail.com`. Se puede copiar o abrir el cliente de correo con un
asunto de sugerencias. La aplicación no envía mensajes ni adjunta datos por sí sola.

## Verificación

Las pruebas cubren las cuatro fórmulas, extremos de intervalos, sustitución de
costos, distancias y CSV inválidos, conservación de demanda, comparación de
escenarios, vista previa/cancelación, `.mnet` antiguos, reapertura de tarifas,
reportes y enlace de contacto. Se mantiene la suite anterior, incluida la
regresión de Convergencia UE y la integración opcional con SUMO.
