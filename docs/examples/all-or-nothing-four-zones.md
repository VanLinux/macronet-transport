# Caso didáctico: asignación Todo-o-Nada

## Objetivo

Asignar la matriz de viajes en automóvil a una red dirigida. Toda la demanda de cada relación origen-destino utiliza una sola ruta mínima calculada con tiempos de flujo libre.

## Demanda

La elección modal produce 493.380457 viajes en automóvil:

- Viajes intrazonales: 228.160935.
- Viajes interzonales asignables a la red: 265.219521.

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
| Centro | Norte | 21.150198 | Centro → Norte | 6 |
| Centro | Sur | 10.229869 | Centro → Sur | 9 |
| Centro | Oriente | 7.193828 | Centro → Sur → Oriente | 13 |
| Norte | Centro | 46.993685 | Norte → Centro | 6 |
| Norte | Sur | 18.408216 | Norte → Sur | 5 |
| Norte | Oriente | 11.804146 | Norte → Sur → Oriente | 9 |
| Sur | Centro | 27.995110 | Sur → Centro | 9 |
| Sur | Norte | 22.672465 | Sur → Norte | 5 |
| Sur | Oriente | 27.617490 | Sur → Oriente | 4 |
| Oriente | Centro | 22.650929 | Oriente → Sur → Centro | 13 |
| Oriente | Norte | 16.727670 | Oriente → Sur → Norte | 9 |
| Oriente | Sur | 31.775916 | Oriente → Sur | 4 |

Por ejemplo, Centro → Oriente no utiliza el arco directo de costo 16. La ruta Centro → Sur → Oriente tiene costo \(9+4=13\).

## Acumulación de flujos

El flujo de cada arco se obtiene mediante:

\[
x_a=\sum_i\sum_j q_{ij}\delta_{a,r_{ij}^{*}}
\]

donde \(\delta_{a,r_{ij}^{*}}=1\) cuando el arco \(a\) pertenece a la ruta mínima seleccionada.

| Arco | Desde | Hasta | Flujo | Capacidad | \(v/c\) |
|---|---|---|---:|---:|---:|
| L01 | Centro | Norte | 21.150198 | 50 | 0.423 |
| L10 | Norte | Centro | 46.993685 | 50 | 0.940 |
| L02 | Centro | Sur | 17.423697 | 40 | 0.436 |
| L20 | Sur | Centro | 50.646039 | 40 | 1.266 |
| L03 | Centro | Oriente | 0.000000 | 30 | 0.000 |
| L30 | Oriente | Centro | 0.000000 | 30 | 0.000 |
| L12 | Norte | Sur | 30.212362 | 40 | 0.755 |
| L21 | Sur | Norte | 39.400135 | 40 | 0.985 |
| L13 | Norte | Oriente | 0.000000 | 30 | 0.000 |
| L31 | Oriente | Norte | 0.000000 | 30 | 0.000 |
| L23 | Sur | Oriente | 46.615463 | 45 | 1.036 |
| L32 | Oriente | Sur | 71.154516 | 45 | 1.581 |

## Interpretación crítica

Los valores \(v/c>1\) indican que la asignación de flujo libre concentra más demanda que la capacidad declarada. Sin embargo, el método Todo-o-Nada no actualiza tiempos por congestión y, por ello, no redistribuye esos viajes.

Este resultado no representa un equilibrio de Wardrop. Su función es mostrar con claridad la lógica de rutas mínimas y acumulación de flujos. Una versión posterior podrá incorporar funciones volumen-demora y el algoritmo de Frank–Wolfe.

La red, los tiempos y las capacidades son sintéticos y se utilizan exclusivamente con fines didácticos.

## Exportación de la red

La vista `Red y flujos` puede ampliarse en una ventana independiente. La red también se
puede descargar en GraphML para abrirla en Gephi o procesarla con NetworkX. El archivo
conserva, para cada arco, su identificador, dirección, tiempo libre, capacidad, flujo,
relación volumen/capacidad y estado de utilización.
