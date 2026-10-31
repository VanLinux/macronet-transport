"""Ejecutor sin Qt: detección, cancelación de procesos y lectura incremental de XML."""

from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock
from xml.etree import ElementTree as ET

from macronet.sumo.scenario import SumoCancelled, SumoError, prepare_scenario, write_json

TOOLS = ("sumo", "netconvert", "duarouter")
_DLL_LOCK = Lock()


def bundled_bin_directory():
    """SUMO privado junto al ejecutable, independiente del PATH y de SUMO_HOME."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "sumo" / "bin"
    return None


def _command_environment(executable):
    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS).resolve()
        env["PATH"] = os.pathsep.join(
            part
            for part in env.get("PATH", "").split(os.pathsep)
            if part and not Path(part).resolve().is_relative_to(bundle)
        )
        if os.name != "nt":
            original = env.pop("LD_LIBRARY_PATH_ORIG", None)
            if original is None:
                env.pop("LD_LIBRARY_PATH", None)
            else:
                env["LD_LIBRARY_PATH"] = original
    executable = Path(executable).resolve()
    if executable.stem in TOOLS:
        env["PATH"] = str(executable.parent) + os.pathsep + env.get("PATH", "")
        # Las rutas de schemas y recursos corresponden al motor elegido.
        if (executable.parent.parent / "data").is_dir():
            env["SUMO_HOME"] = str(executable.parent.parent)
    return env


@contextmanager
def _native_dll_search():
    """Evita que el motor C++ cargue DLL de Qt/Python del paquete congelado."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes

    with _DLL_LOCK:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
        kernel.GetDllDirectoryW.restype = ctypes.c_uint
        previous = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(previous), previous)
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            kernel.SetDllDirectoryW(previous.value or None)


def stop_process(process):
    """Detiene también los hijos de los lanzadores de SUMO instalados mediante pip."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                [
                    str(Path(os.environ["SystemRoot"]) / "System32" / "taskkill.exe"),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=5,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait(timeout=5)


def command(args, directory, log_name, cancel, deadline):
    if cancel.is_set():
        raise SumoCancelled("Simulación cancelada.")
    options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    log_path = Path(directory) / log_name
    with log_path.open("w", encoding="utf-8") as log:
        try:
            with _native_dll_search():
                process = subprocess.Popen(
                    [str(arg) for arg in args],
                    cwd=directory,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=_command_environment(args[0]),
                    **options,
                )
        except OSError as error:
            raise SumoError(f"No se pudo ejecutar {Path(args[0]).name}: {error}") from error
        try:
            while process.poll() is None:
                if cancel.wait(0.05):
                    raise SumoCancelled(
                        "Simulación cancelada; se conservaron archivos y registros."
                    )
                if time.monotonic() > deadline:
                    raise SumoError("Se alcanzó el límite de tiempo real; revise el registro.")
        finally:
            stop_process(process)
    # Solo la cola del registro: los errores de redes grandes no deben llenar la RAM.
    with log_path.open("rb") as stream:
        stream.seek(max(0, log_path.stat().st_size - 6000))
        tail = stream.read().decode("utf-8", errors="replace")
    if process.returncode != 0:
        raise SumoError(f"{Path(args[0]).name} terminó con código {process.returncode}.\n{tail}")
    return tail


def detect_tools(bin_directory="", *, cancel=None, deadline=None):
    cancel = cancel if cancel is not None else Event()
    deadline = deadline if deadline is not None else time.monotonic() + 15
    suffix = ".exe" if os.name == "nt" else ""
    candidates = (
        [Path(bin_directory)]
        if bin_directory
        else [
            *([bundled_bin_directory()] if bundled_bin_directory() is not None else []),
            Path(sys.executable).parent,
            *([Path(os.environ["SUMO_HOME"]) / "bin"] if os.environ.get("SUMO_HOME") else []),
            None,
        ]
    )
    paths = None
    for folder in candidates:
        found = {
            tool: str((folder / (tool + suffix)).resolve()) if folder else shutil.which(tool)
            for tool in TOOLS
        }
        if all(path and Path(path).is_file() for path in found.values()):
            paths = found
            break
    if paths is None:
        raise SumoError(
            "No se encontraron sumo, netconvert y duarouter. Instale SUMO "
            "o seleccione su carpeta bin. Las cuatro etapas siguen disponibles."
        )
    versions = {}
    with tempfile.TemporaryDirectory(prefix="macronet-sumo-check-") as directory:
        for tool, path in paths.items():
            text = command([path, "--version"], directory, f"{tool}.log", cancel, deadline)
            match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", text)
            if not match or tuple(map(int, match.groups()[:2])) < (1, 18):
                raise SumoError(f"{tool}: se requiere Eclipse SUMO 1.18 o posterior.")
            versions[tool] = match.group(0)
    if len(set(versions.values())) != 1:
        raise SumoError(
            "Las herramientas SUMO tienen versiones distintas; use una sola instalación."
        )
    return paths, versions


def parse_outputs(directory, manifest):
    root = Path(directory)
    count = 0
    totals = dict(
        duration_s=0.0, waiting_s=0.0, time_loss_s=0.0, depart_delay_s=0.0, distance_m=0.0
    )
    attributes = dict(
        duration_s="duration",
        waiting_s="waitingTime",
        time_loss_s="timeLoss",
        depart_delay_s="departDelay",
        distance_m="routeLength",
    )
    for _, element in ET.iterparse(root / "tripinfo.xml", events=("end",)):
        if element.tag == "tripinfo":
            if float(element.attrib["arrival"]) >= 0 and element.get("vaporized", "") in (
                "",
                "0",
                "false",
            ):
                count += 1
                for key, attribute in attributes.items():
                    totals[key] += float(element.attrib[attribute])
            element.clear()
    last_step = None
    series = []
    inputs = manifest["inputs"]["settings"]
    stride = max(1, (inputs["period_s"] + inputs["clearance_s"] + 399) // 400)
    for _, element in ET.iterparse(root / "summary.xml", events=("end",)):
        if element.tag == "step":
            last_step = dict(element.attrib)
            if int(float(last_step["time"])) % stride == 0:
                series.append(
                    [float(last_step["time"]), int(last_step["running"]), int(last_step["arrived"])]
                )
            element.clear()
    if last_step is None:
        raise SumoError("SUMO no produjo el resumen de vehículos.")
    final = [float(last_step["time"]), int(last_step["running"]), int(last_step["arrived"])]
    if not series or series[-1] != final:
        series.append(final)
    inserted = int(last_step["inserted"])
    running = int(last_step["running"])
    pending = manifest["generated"] - inserted
    removed = inserted - count - running
    if min(inserted, running, pending, removed) < 0:
        raise SumoError("Las salidas SUMO no conservan el conteo de vehículos.")
    stats = dict(
        generated=manifest["generated"],
        inserted=inserted,
        arrived=count,
        running=running,
        pending=pending,
        removed=removed,
        mean_duration_s=totals["duration_s"] / count if count else None,
        mean_waiting_s=totals["waiting_s"] / count if count else None,
        mean_time_loss_s=totals["time_loss_s"] / count if count else None,
        mean_depart_delay_s=totals["depart_delay_s"] / count if count else None,
        mean_speed_kmh=3.6 * totals["distance_m"] / totals["duration_s"]
        if totals["duration_s"]
        else None,
    )
    reverse = {edge: name for name, edge in manifest["edge_map"].items()}
    reference = {item["link"]["link_id"]: item for item in manifest["reference"]["link_results"]}
    samples = {}
    for _, element in ET.iterparse(root / "edges.xml", events=("end",)):
        if element.tag == "edge" and element.get("id") in reverse:
            samples[reverse[element.get("id")]] = dict(element.attrib)
            element.clear()
    rows = []
    for name, item in reference.items():
        sample = samples.get(name, {})
        rows.append(
            dict(
                link_id=name,
                static_vehicles=item["volume"],
                static_time_min=item["travel_time"],
                sumo_entered=int(sample.get("entered", 0)) + int(sample.get("departed", 0)),
                sumo_time_min=float(sample["traveltime"]) / 60 if "traveltime" in sample else None,
                sumo_speed_kmh=float(sample["speed"]) * 3.6 if "speed" in sample else None,
            )
        )
    return stats, rows, series


def run_scenario(
    parent,
    source,
    nodes,
    roads,
    settings,
    *,
    bin_directory="",
    execute=True,
    cancel=None,
    progress=lambda _message: None,
):
    """Una carpeta nueva por ejecución; conserva el diagnóstico incluso al cancelar."""
    cancel = cancel if cancel is not None else Event()
    settings.validate()
    started = time.monotonic()
    deadline = started + settings.timeout_s

    def check():
        if cancel.is_set():
            raise SumoCancelled("Simulación cancelada.")
        if time.monotonic() > deadline:
            raise SumoError("Se alcanzó el límite de tiempo real.")

    check()
    paths, versions = (
        detect_tools(bin_directory, cancel=cancel, deadline=deadline) if execute else ({}, {})
    )
    directory = Path(tempfile.mkdtemp(prefix="macronet-sumo-", dir=parent)).resolve()
    manifest = dict(status="preparing", app="MacroNet", directory=str(directory))
    try:
        progress("Preparando demanda, geometría y referencia estática…")
        manifest = prepare_scenario(directory, source, nodes, roads, settings, check=check)
        manifest.update(
            directory=str(directory), versions=versions, created_at=datetime.now(UTC).isoformat()
        )
        if execute:
            commands = [
                [
                    paths["netconvert"],
                    "--node-files",
                    "nodes.nod.xml",
                    "--edge-files",
                    "roads.edg.xml",
                    "--output-file",
                    "network.net.xml",
                ],
                [
                    paths["duarouter"],
                    "--net-file",
                    "network.net.xml",
                    "--additional-files",
                    "zones.taz.xml",
                    "--route-files",
                    "trips.trips.xml",
                    "--weight-files",
                    "weights.xml",
                    "--with-taz",
                    "--seed",
                    str(settings.seed),
                    "--output-file",
                    "routes.rou.xml",
                ],
                [paths["sumo"], "-c", "simulation.sumocfg", "--no-step-log", "true"],
            ]
            for index, args in enumerate(commands):
                check()
                progress(("Construyendo red…", "Calculando rutas…", "Simulando vehículos…")[index])
                manifest["commands"].append(args)
                write_json(directory / "manifest.json", manifest)
                command(
                    args, directory, f"{index + 1}-{TOOLS[(index + 1) % 3]}.log", cancel, deadline
                )
            progress("Leyendo resultados y verificando vehículos…")
            check()
            stats, rows, series = parse_outputs(directory, manifest)
            check()
            manifest.update(status="completed", statistics=stats, edges=rows, series=series)
            with (directory / "comparison.csv").open(
                "w", encoding="utf-8-sig", newline=""
            ) as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        manifest["elapsed_s"] = time.monotonic() - started
        manifest["sha256"] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.iterdir()
            if path.suffix == ".xml"
        }
        write_json(directory / "manifest.json", manifest)
        return manifest
    except (OSError, ValueError, ET.ParseError, KeyError) as error:
        manifest.update(
            status="cancelled" if isinstance(error, SumoCancelled) else "failed",
            error=str(error),
            elapsed_s=time.monotonic() - started,
        )
        write_json(directory / "manifest.json", manifest)
        error_type = SumoCancelled if isinstance(error, SumoCancelled) else SumoError
        raise error_type(f"{error}\nArchivos de diagnóstico: {directory}") from error
