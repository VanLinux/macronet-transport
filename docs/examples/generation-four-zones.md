# Caso didáctico: generación y atracción en cuatro zonas

## Objetivo

Calcular los viajes producidos y atraídos por cuatro zonas y aplicar un balanceo para cumplir la condición del sistema:

\[
\sum_i P_i = \sum_i A_i^*
\]

## Modelos utilizados

Para esta demostración se emplean modelos lineales deliberadamente sencillos:

\[
P_i = 2H_i + V_i
\]

\[
A_i = 2E_i + S_i
\]

donde:

- \(H_i\): hogares de la zona \(i\).
- \(V_i\): vehículos de la zona \(i\).
- \(E_i\): empleos de la zona \(i\).
- \(S_i\): estudiantes de la zona \(i\).
- \(P_i\): viajes producidos.
- \(A_i\): viajes atraídos sin balancear.

## Datos y cálculo directo

| Zona | Hogares | Vehículos | Empleos | Estudiantes | Producción | Atracción inicial |
|---|---:|---:|---:|---:|---:|---:|
| Centro | 100 | 60 | 200 | 100 | 260 | 500 |
| Norte | 120 | 80 | 100 | 150 | 320 | 350 |
| Sur | 110 | 70 | 80 | 150 | 290 | 310 |
| Oriente | 120 | 90 | 120 | 100 | 330 | 340 |
| **Total** | **450** | **300** | **500** | **500** | **1200** | **1500** |

## Balanceo de atracciones

El factor de balanceo es:

\[
F = \frac{\sum_i P_i}{\sum_i A_i} = \frac{1200}{1500} = 0.8
\]

Cada atracción se multiplica por \(F\):

| Zona | Atracción inicial | Factor | Atracción balanceada |
|---|---:|---:|---:|
| Centro | 500 | 0.8 | 400 |
| Norte | 350 | 0.8 | 280 |
| Sur | 310 | 0.8 | 248 |
| Oriente | 340 | 0.8 | 272 |
| **Total** | **1500** |  | **1200** |

La igualdad final se cumple:

\[
\sum_i P_i = \sum_i A_i^* = 1200\ \text{viajes}
\]

Los coeficientes y datos son sintéticos. Su propósito es explicar el procedimiento y permitir una comprobación manual; todavía no representan un modelo calibrado con observaciones reales.
