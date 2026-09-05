# MacroNet Transport

**MacroNet** es una aplicación educativa, interactiva y de código abierto para estudiar el modelo clásico de transporte de cuatro etapas.

El proyecto busca que el estudiante pueda observar el proceso completo, modificar datos y parámetros, revisar ecuaciones y cálculos intermedios, y comprobar cómo cada decisión afecta las etapas posteriores.

## Alcance inicial

La versión `0.1` cubrirá:

1. Generación y atracción de viajes.
2. Distribución de viajes.
3. Elección modal.
4. Asignación de viajes a la red.

Cada módulo deberá separar el modelo matemático de la interfaz gráfica y conservar resultados intermedios para su explicación y validación manual.

## Principios del proyecto

- **Educativo:** explica el procedimiento, no solo entrega el resultado.
- **Interactivo:** permite modificar datos y observar sus efectos.
- **Transparente:** muestra ecuaciones, unidades, supuestos y cálculos intermedios.
- **Verificable:** incluye casos pequeños que pueden resolverse manualmente.
- **Modular:** cada etapa puede estudiarse por separado o dentro del flujo completo.
- **Libre:** se distribuye bajo la licencia GNU GPL v3.0.

## Estado

El proyecto se encuentra en su fase inicial de diseño y construcción. Ya incluye un recorrido funcional por las cuatro etapas: generación y atracción, distribución gravitacional, elección modal logit y asignación Todo-o-Nada.

## Tecnología prevista

- Python 3.11 o posterior.
- PySide6 para la aplicación de escritorio.
- NumPy y pandas para cálculo y datos.
- NetworkX para redes y asignación.
- Matplotlib para visualizaciones didácticas.
- pytest para pruebas automatizadas.

## Ejecución durante el desarrollo

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m macronet
```

En Windows, la activación del entorno virtual se realiza con:

```powershell
.venv\Scripts\activate
```

## Pruebas

```bash
pytest
```

## Documentación

El alcance funcional de la primera versión se encuentra en [`docs/scope-v0.1.md`](docs/scope-v0.1.md).

El caso didáctico incluido en el primer módulo está documentado en [`docs/examples/generation-four-zones.md`](docs/examples/generation-four-zones.md).

La distribución del mismo caso se documenta en [`docs/examples/distribution-four-zones.md`](docs/examples/distribution-four-zones.md).

La elección modal se desarrolla en [`docs/examples/mode-choice-four-zones.md`](docs/examples/mode-choice-four-zones.md).

La asignación de la demanda de automóvil se documenta en [`docs/examples/all-or-nothing-four-zones.md`](docs/examples/all-or-nothing-four-zones.md).
