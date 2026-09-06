# Caso didáctico: elección modal en cuatro zonas

## Objetivo

Dividir cada celda de la matriz origen-destino entre tres alternativas: automóvil, transporte público y bicicleta. El modelo conserva los viajes de cada par:

\[
\sum_m T_{mij}=T_{ij}
\]

## Construcción de atributos

MacroNet parte de la impedancia \(c_{ij}\) utilizada durante la distribución. Para cada modo calcula tiempo y costo:

\[
t_{mij}=t_m^0+\lambda_m c_{ij}
\]

\[
C_{mij}=C_m^0+\gamma_m c_{ij}
\]

Los parámetros iniciales son sintéticos:

| Modo | ASC | Multiplicador de tiempo \(\lambda_m\) | Tiempo fijo \(t_m^0\) | Costo fijo \(C_m^0\) | Costo variable \(\gamma_m\) |
|---|---:|---:|---:|---:|---:|
| Automóvil | 0.3 | 1.00 | 0 | 5 | 0.25 |
| Transporte público | 0.6 | 1.35 | 5 | 6 | 0.00 |
| Bicicleta | −0.8 | 2.20 | 0 | 0 | 0.00 |

## Utilidad y probabilidad

La utilidad sistemática se calcula con:

\[
U_{mij}=ASC_m+\beta_t t_{mij}+\beta_c C_{mij}
\]

Para el ejemplo:

\[
\beta_t=-0.08,
\qquad
\beta_c=-0.18
\]

La probabilidad logit multinomial es:

\[
P_{mij}=\frac{e^{U_{mij}}}{\sum_k e^{U_{kij}}}
\]

y los viajes asignados a cada modo son:

\[
T_{mij}=T_{ij}P_{mij}
\]

## Ejemplo para Centro → Norte

La matriz de distribución contiene \(T_{ij}=50.495638\) viajes y la impedancia es \(c_{ij}=10\).

| Modo | Tiempo | Costo | Utilidad | Probabilidad | Viajes modales |
|---|---:|---:|---:|---:|---:|
| Automóvil | 10.0 | 7.5 | −1.8500 | 0.418852 | 21.150198 |
| Transporte público | 18.5 | 6.0 | −1.9600 | 0.375222 | 18.947069 |
| Bicicleta | 22.0 | 0.0 | −2.5600 | 0.205926 | 10.398372 |
| **Total** |  |  |  | **1.000000** | **50.495638** |

## Resultado agregado

Al aplicar el modelo a las 16 relaciones origen-destino se obtiene:

| Modo | Viajes | Participación |
|---|---:|---:|
| Automóvil | 493.380457 | 41.115038 % |
| Transporte público | 431.147357 | 35.928946 % |
| Bicicleta | 275.472186 | 22.956016 % |
| **Total** | **1200.000000** | **100.000000 %** |

## Interpretación

Un coeficiente negativo indica que un aumento del tiempo o costo reduce la utilidad y, por tanto, la probabilidad de elegir ese modo. Las constantes específicas representan efectos propios de cada alternativa que no están explicados por las variables observadas.

Los parámetros no están calibrados con encuestas de preferencia revelada o declarada. El caso sirve exclusivamente para estudiar el mecanismo del logit multinomial y analizar sensibilidad; no debe interpretarse como una estimación real de participación modal.
