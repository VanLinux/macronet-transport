# Caso didáctico: asignación Todo-o-Nada

## Objetivo

Asignar la matriz de viajes en automóvil a una red dirigida. Toda la demanda de cada relación origen-destino utiliza una sola ruta mínima calculada con tiempos de flujo libre.

## Demanda

La elección modal produce 493.380504 viajes en automóvil:

- Viajes intrazonales: 228.160160.
- Viajes interzonales asignables a la red: 265.220345.

Los viajes intrazonales permanecen dentro del nodo centroide y no cargan ningún arco.

## Red didáctica

Cada conexión existe en ambos sentidos. Los tiempos son costos de flujo libre y las capacidades corresponden al periodo de análisis.

| Conexión | Tiempo | Capacidad por sentido |
|---|---:|---:|
| Centro–Norte | 6 | 50 |
| Centro–Sur | 9 | 40 |
| Centro–Oriente | 16 | 30 |
| Norte–Sur | 5 | 40 |
| Norte–Oriente | 10 | 30 |
| Sur–Oriente | 4 | 45 |

## Ruta mínima

Para cada relación \(ij\), el algoritmo de Dijkstra obtiene:

\[
r_{ij}^{*}=\arg\min_r\sum_{a\in r}t_a^0
\]

Los principales resultados interzonales son:

| Origen | Destino | Demanda | Ruta | Costo |
|---|---|---:|---|---:|
| Centro | Norte | 21.149754 | Centro → Norte | 6 |
| Centro | Sur | 10.229486 | Centro → Sur | 9 |
| Centro | Oriente | 7.193491 | Centro → Sur → Oriente | 13 |
| Norte | Centro | 46.993305 | Norte → Centro | 6 |
| Norte | Sur | 18.407700 | Norte → Sur | 5 |
| Norte | Oriente | 11.803704 | Norte → Sur → Oriente | 9 |
| Sur | Centro | 27.995767 | Sur → Centro | 9 |
| Sur | Norte | 22.672918 | Sur → Norte | 5 |
| Sur | Oriente | 27.617328 | Sur → Oriente | 4 |
| Oriente | Centro | 22.651906 | Oriente → Sur → Centro | 13 |
| Oriente | Norte | 16.728333 | Oriente → Sur → Norte | 9 |
| Oriente | Sur | 31.776651 | Oriente → Sur | 4 |

Por ejemplo, Centro → Oriente no utiliza el arco directo de costo 16. La ruta Centro → Sur → Oriente tiene costo \(9+4=13\).

## Acumulación de flujos

El flujo de cada arco se obtiene mediante:

\[
x_a=\sum_i\sum_j q_{ij}\delta_{a,r_{ij}^{*}}
\]

donde \(\delta_{a,r_{ij}^{*}}=1\) cuando el arco \(a\) pertenece a la ruta mínima seleccionada.

| Arco | Desde | Hasta | Flujo | Capacidad | \(v/c\) |
|---|---|---|---:|---:|---:|
| L01 | Centro | Norte | 21.149754 | 50 | 0.423 |
| L10 | Norte | Centro | 46.993305 | 50 | 0.940 |
| L02 | Centro | Sur | 17.422977 | 40 | 0.436 |
| L20 | Sur | Centro | 50.647673 | 40 | 1.266 |
| L03 | Centro | Oriente | 0.000000 | 30 | 0.000 |
| L30 | Oriente | Centro | 0.000000 | 30 | 0.000 |
| L12 | Norte | Sur | 30.211404 | 40 | 0.755 |
| L21 | Sur | Norte | 39.401251 | 40 | 0.985 |
| L13 | Norte | Oriente | 0.000000 | 30 | 0.000 |
| L31 | Oriente | Norte | 0.000000 | 30 | 0.000 |
| L23 | Sur | Oriente | 46.614523 | 45 | 1.036 |
| L32 | Oriente | Sur | 71.156891 | 45 | 1.581 |

## Interpretación crítica

Los valores \(v/c>1\) indican que la asignación de flujo libre concentra más demanda que la capacidad declarada. Sin embargo, el método Todo-o-Nada no actualiza tiempos por congestión y, por ello, no redistribuye esos viajes.

Este resultado no representa un equilibrio de Wardrop. Su función es mostrar con claridad la lógica de rutas mínimas y acumulación de flujos. Una versión posterior podrá incorporar funciones volumen-demora y el algoritmo de Frank–Wolfe.

La red, los tiempos y las capacidades son sintéticos y se utilizan exclusivamente con fines didácticos.
