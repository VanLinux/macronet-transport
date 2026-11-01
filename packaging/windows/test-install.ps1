param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion
)
$ErrorActionPreference = 'Stop'
$Installer = (Resolve-Path $Installer).Path
$testRoot = Join-Path $env:RUNNER_TEMP 'Prueba Héctor México'
$installDir = Join-Path $testRoot 'MacroNet Transport'
$reportDir = Join-Path $env:GITHUB_WORKSPACE 'installation-results'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$installLog = Join-Path $reportDir 'instalacion.log'
$process = Start-Process $Installer -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$installDir`"", "/LOG=`"$installLog`"") -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Instalación fallida: $($process.ExitCode)" }
$exe = Join-Path $installDir 'MacroNet.exe'
if (-not (Test-Path $exe)) { throw 'No se instaló MacroNet.exe' }
if ((Get-Item $exe).VersionInfo.ProductVersion -ne $ExpectedVersion) {
    throw "El ejecutable no corresponde a MacroNet $ExpectedVersion"
}
$shortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'MacroNet Transport.lnk'
if (-not (Test-Path $shortcut)) { throw 'No se creó el acceso directo' }
# Sin acceso a los Python/SUMO que pudiera tener la imagen de GitHub.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$env:SUMO_HOME = Join-Path $testRoot 'SUMO externo inexistente'
$env:PYTHONHOME = Join-Path $testRoot 'Python externo inexistente'
$env:PYTHONPATH = ''
Remove-Item Env:QT_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_PLATFORM_PLUGIN_PATH -ErrorAction SilentlyContinue
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:HTTP_PROXY = 'http://127.0.0.1:9'
$env:HTTPS_PROXY = 'http://127.0.0.1:9'
$report = Join-Path $reportDir 'comprobacion.json'
$process = Start-Process $exe -ArgumentList @('--self-test', "`"$report`"") -PassThru
if (-not $process.WaitForExit(180000)) {
    $process.Kill()
    throw 'La prueba del ejecutable excedió tres minutos'
}
if (-not (Test-Path $report)) { throw "El ejecutable no produjo diagnóstico (código $($process.ExitCode))" }
$result = Get-Content $report -Raw | ConvertFrom-Json
Write-Output (Get-Content $report -Raw)
if (-not $result.ok) { throw $result.error }
if ($result.version -ne $ExpectedVersion) { throw 'La versión interna no corresponde al instalador' }
if ($result.checks -notcontains 'summary_and_self_contained_report') {
    throw 'No se verificaron el Resumen y el nuevo informe'
}
if ($process.ExitCode -ne 0) { throw "El ejecutable terminó con código $($process.ExitCode)" }
if ($result.sumo_statistics.arrived -ne 19) { throw 'La simulación real no completó 19 viajes' }
# El desinstalador debe conservar los trabajos fuera de la instalación.
$uninstall = Join-Path $installDir 'unins000.exe'
$process = Start-Process $uninstall -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Falló la desinstalación' }
if (Test-Path $exe) { throw 'El ejecutable sigue instalado' }
if (-not (Test-Path (Join-Path $reportDir 'Práctica México.mnet'))) { throw 'Se perdió el ejercicio del usuario' }
if (Test-Path $shortcut) { throw 'El acceso directo no se retiró' }


