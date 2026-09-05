# Caso didáctico: distribución de viajes en cuatro zonas

## Objetivo

Distribuir los 1200 viajes obtenidos en generación entre cuatro orígenes y cuatro destinos, respetando simultáneamente:

\[
\sum_j T_{ij}=O_i
\qquad\text{y}\qquad
\sum_i T_{ij}=D_j
\]

## Datos marginales

| Zona | Producciones \(O_i\) | Atracciones \(D_j\) |
|---|---:|---:|
| Centro | 260 | 400 |
| Norte | 320 | 280 |
| Sur | 290 | 248 |
| Oriente | 330 | 272 |
| **Total** | **1200** | **1200** |

## Impedancias

La impedancia \(c_{ij}\) representa un tiempo sintético de viaje en minutos.

| Origen / destino | Centro | Norte | Sur | Oriente |
|---|---:|---:|---:|---:|
| Centro | 3 | 10 | 15 | 20 |
| Norte | 10 | 3 | 12 | 18 |
| Sur | 15 | 12 | 3 | 9 |
| Oriente | 20 | 18 | 9 | 3 |

## Función de fricción

Se utiliza una función exponencial con \(\beta=0.1\):

\[
f(c_{ij})=e^{-\beta c_{ij}}
\]

Las impedancias grandes producen factores de fricción pequeños y, en igualdad de condiciones, reducen la interacción entre zonas.

| Origen / destino | Centro | Norte | Sur | Oriente |
|---|---:|---:|---:|---:|
| Centro | 0.740818 | 0.367879 | 0.223130 | 0.135335 |
| Norte | 0.367879 | 0.740818 | 0.301194 | 0.165299 |
| Sur | 0.223130 | 0.301194 | 0.740818 | 0.406570 |
| Oriente | 0.135335 | 0.165299 | 0.406570 | 0.740818 |

## Modelo doblemente restringido

\[
T_{ij}=a_iO_i\,b_jD_j\,f(c_{ij})
\]

Los factores \(a_i\) y \(b_j\) se determinan iterativamente. MacroNet aplica el procedimiento de Furness: ajusta las filas a las producciones, después las columnas a las atracciones y repite el ciclo hasta cumplir la tolerancia.

## Matriz origen-destino obtenida

| Origen / destino | Centro | Norte | Sur | Oriente | Total origen |
|---|---:|---:|---:|---:|---:|
| Centro | 168.45 | 50.49 | 24.10 | 16.96 | 260.00 |
| Norte | 112.20 | 136.39 | 43.64 | 27.78 | 320.00 |
| Sur | 65.97 | 53.75 | 104.05 | 66.23 | 290.00 |
| Oriente | 53.39 | 39.37 | 76.20 | 161.04 | 330.00 |
| **Total destino** | **400.00** | **280.00** | **248.00** | **272.00** | **1200.00** |

Los valores se muestran con dos decimales, por lo que las sumas manuales de la tabla redondeada pueden diferir algunas centésimas. El cálculo interno conserva toda la precisión.

## Convergencia

Con una tolerancia de \(10^{-6}\) viajes, el ejemplo converge en 14 iteraciones.

| Iteración | Error máximo en filas | Error máximo en columnas |
|---:|---:|---:|
| 1 | 42.726826794 | 0.000000000 |
| 2 | 8.108881121 | 0.000000000 |
| 5 | 0.129662021 | 0.000000000 |
| 10 | 0.000116632 | 0.000000000 |
| 14 | 0.000000426 | 0.000000000 |

El error de columnas es prácticamente cero después de cada iteración porque el último ajuste de cada ciclo se realiza precisamente sobre las columnas. La convergencia se alcanza cuando las filas también respetan sus marginales dentro de la tolerancia.

Los datos son sintéticos y tienen una finalidad didáctica. El parámetro \(\beta\) no procede todavía de una calibración empírica.
