# Instalador completo de MacroNet para Windows

## Para estudiantes

1. Descargue el archivo terminado en `Windows-x64-Setup.exe` desde Releases.
2. Ejecútelo y siga el asistente. La instalación se realiza para su usuario.
3. Abra **MacroNet Transport** desde el escritorio o Inicio.

Incluye Python, las bibliotecas y SUMO. No necesita terminal, Python externo,
SUMO externo ni conexión a Internet para usar los modelos. En microsimulación,
deje vacía la carpeta del motor para detectar automáticamente el SUMO incluido.
La carpeta especificada manualmente tiene prioridad. La instalación no cambia
PATH ni SUMO_HOME y puede coexistir con un SUMO previamente instalado.

Guarde ejercicios `.mnet` y resultados en Documentos u otra carpeta personal.
Los informes `.tex` se suben a Overleaf para obtener PDF. No se incluye LaTeX.
Desinstale desde Configuración → Aplicaciones; los trabajos guardados fuera de
la carpeta de instalación se conservan.

## Primera prueba docente en Windows 11

La compilación y las pruebas automáticas se ejecutan en Windows Server 2022 x64.
Esta comprobación no sustituye la prueba final en un equipo Windows 11.

- Instalar primero en el equipo que ya tiene SUMO: dejar vacía la ruta del motor,
  pulsar **Comprobar SUMO** y ejecutar un escenario. En `manifest.json`, los
  comandos deben apuntar a la carpeta `MacroNet Transport/sumo/bin`.
- Repetir en otro equipo sin Python ni SUMO, con Internet desconectado durante
  la instalación y el uso. No debe solicitar descargar dependencias.
- Comprobar las cuatro etapas, Wardrop, tarifas y calibración; guardar y reabrir
  un `.mnet`, exportar matrices e informe `.tex` y compilar el informe en Overleaf.
- Revisar textos, gráficas y diálogos con la escala habitual de pantalla del
  equipo, y verificar el acceso directo y la desinstalación.

Esta primera distribución no está firmada digitalmente. Si Windows muestra un
aviso, compruebe su procedencia y el SHA256 publicado; no desactive el antivirus.

## Construcción desde Fedora o Linux

El código y la configuración se editan en Linux. El workflow
`.github/workflows/windows-installer.yml` construye el ejecutable en Windows,
sin necesitar un Windows local para la compilación. Se ejecuta al cambiar código
o configuración en `main`, en la rama de preparación `build/windows-installer`,
o manualmente desde Actions.

El proceso verifica el código, descarga el ZIP oficial de SUMO 1.28.0 con su hash
fijado, congela Python con PyInstaller y genera el asistente con Inno Setup.
Otro runner instala el resultado en una ruta con espacios y acentos, elimina del
PATH el acceso a Python y SUMO externos y ejecuta el modo de comprobación del
binario instalado. La prueba verifica Qt, cuatro etapas, Wardrop, calibración,
Excel/CSV/GraphML/LaTeX, `.mnet`, fuentes y una simulación real de 19 vehículos;
finalmente desinstala sin borrar el ejercicio de prueba.

El artefacto `MacroNet-Windows-completo` contiene instalador y SHA256. Tras superar
ambos trabajos desde `main`, el workflow publica una versión preliminar para
la prueba docente. Los resultados de instalación incluyen JSON y una captura.

## Construcción manual en Windows

Con Python 3.12 x64 e Inno Setup 6 disponibles, desde la raíz del repositorio:

```powershell
py -3.12 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r packaging/windows/requirements-build.txt
.\.venv-build\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv-build\Scripts\python.exe packaging/windows/prepare.py
.\.venv-build\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging/windows/macronet.spec
.\.venv-build\Scripts\python.exe packaging/windows/prepare.py --stage
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" /DAppVersion=3.3.1 packaging/windows/installer.iss
```

El resultado está en `dist/installer/`. El instalador copia el paquete completo;
no descarga componentes en los equipos de los alumnos. SUMO conserva sus archivos
oficiales. Python/Qt permanecen separados del motor nativo. Las licencias y el
inventario se conservan en `licenses/`; `THIRD_PARTY.txt` indica las fuentes de los
componentes y `sources/MacroNet-source.zip` contiene la fuente exacta de MacroNet.

