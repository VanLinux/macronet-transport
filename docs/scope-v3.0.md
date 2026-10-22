# MacroNet Transport 3.0.0

Esta versión sucede a 0.2.0. Se adopta la numeración 3.0.0 solicitada por el
responsable del proyecto. No cambia los modelos matemáticos de las cuatro etapas.

## Ejercicios .mnet

El menú Archivo permite abrir, guardar y guardar como. Los datos se escriben en
JSON UTF-8 con identificador de formato y versión de esquema independiente de la
versión de la aplicación. No se utiliza pickle ni se ejecuta contenido del archivo.
El guardado utiliza un archivo temporal en la misma carpeta y reemplazo atómico.

Se incluyen entradas de generación y sus coeficientes, marginales de distribución
(incluidas modificaciones independientes), impedancias, beta, tolerancia,
iteraciones, las tres alternativas y sus parámetros, coeficientes de utilidad,
centroides, arcos, tiempos, capacidades, modo asignado, nombre del usuario y vista
seleccionada. Las instantáneas de las entradas utilizadas en el último cálculo
permiten reconstruir resultados sin redondear los datos ni sustituir borradores.

También se conservan celdas vacías o no numéricas todavía en edición. Al reabrir,
los resultados corresponden a los últimos cálculos válidos; se deben recalcular
las etapas para aplicar los cambios pendientes, igual que antes de guardar.
La captura continúa limitada a las filas disponibles: no se añade edición
estructural de zonas, modos o arcos.

Se valida el documento completo y se reconstruye en una vista independiente
antes de reemplazar el ejercicio abierto. Los archivos incompatibles o dañados
no alteran el trabajo activo. La aplicación avisa al cerrar o abrir otro ejercicio
si existen cambios sin guardar.

## Informes y matrices

- Cada exportación `.tex` solicita un nombre no vacío, admite cancelar y escapa
  caracteres especiales de LaTeX. Conserva el crédito del desarrollador.
- El documento y `geometry` declaran `letterpaper`; se elimina `fontenc`.
  El PDF se obtiene compilando la fuente `.tex` con una instalación de LaTeX.
- El CSV modal contiene columnas `Modo`, `Origen / destino`, los destinos y
  `Total origen`. Cada modo ocupa un bloque y termina con `Total destino`.
  UTF-8 con BOM y entrecomillado CSV conservan acentos, comas y otros nombres.
- Se mantienen exactamente tres modos editables con nombres únicos no vacíos.
  La asignación usa un selector explícito y conserva la posición de la
  alternativa seleccionada al cambiar nombres, sin buscar la palabra automóvil.

## Verificación

Las pruebas cubren reanudación completa y continuación de cálculos, borradores,
marginales personalizados, red, selector modal, archivos dañados o incompatibles,
escritura fallida, cancelación, nombre del informe y formato carta, CSV modal,
CSV OD y GraphML. CI ejecuta lint y pytest en Ubuntu y Windows, Python 3.11/3.12/3.14.
Se confirma el contenido de la celda activa antes de guardar o cerrar, incluso
si el usuario todavía está escribiendo. Se limita PySide6 a versiones anteriores
a 6.12: con 6.12.0 se reprodujo un aborto al destruir tablas en Python 3.11,
también con el código de 0.2.0; las mismas pruebas terminan con 6.11.2.
Estas pruebas no equivalen a validar un instalador ni la apariencia en todos los
escritorios. El caso didáctico sigue siendo sintético y la asignación Todo-o-Nada
no representa equilibrio ni actualiza tiempos por congestión.
