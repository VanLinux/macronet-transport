"""La distribución usa su motor privado sin depender del entorno del alumno."""

import os
import sys
from pathlib import Path

import pytest

from macronet.sumo import runner
from macronet.sumo.scenario import SumoError


def make_tools(root):
    root.mkdir(parents=True)
    suffix = ".exe" if os.name == "nt" else ""
    for tool in runner.TOOLS:
        (root / (tool + suffix)).write_text("placeholder")
    return root


def test_frozen_detection_prefers_private_sumo_over_existing_install(tmp_path, monkeypatch):
    application = tmp_path / "MacroNet instalado"
    bundled = make_tools(application / "sumo/bin")
    external = make_tools(tmp_path / "SUMO externo/bin")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(application / "MacroNet.exe"))
    monkeypatch.setenv("SUMO_HOME", str(external.parent))
    monkeypatch.setenv("PATH", str(external))
    calls = []

    def version(args, *unused):
        calls.append(Path(args[0]).parent)
        return "Eclipse SUMO Version 1.28.0"

    monkeypatch.setattr(runner, "command", version)
    paths, versions = runner.detect_tools()
    assert all(Path(path).parent == bundled for path in paths.values())
    assert calls == [bundled] * 3
    assert set(versions.values()) == {"1.28.0"}
    selected, _ = runner.detect_tools(str(external))
    assert all(Path(path).parent == external for path in selected.values())
    with pytest.raises(SumoError, match="No se encontraron"):
        runner.detect_tools(str(tmp_path / "inexistente"))


def test_subprocess_has_private_resources_and_clean_library_path(tmp_path, monkeypatch):
    bundle = tmp_path / "_internal"
    bundled_sumo = tmp_path / "sumo"
    (bundled_sumo / "data").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("PATH", os.pathsep.join([str(bundle), str(bundle / "PySide6"), "/usr/bin"]))
    monkeypatch.setenv("SUMO_HOME", "external")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(bundle))
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/original")
    env = runner._command_environment(bundled_sumo / "bin/sumo")
    assert env["SUMO_HOME"] == str(bundled_sumo)
    assert str(bundle) not in env["PATH"]
    assert env["PATH"].split(os.pathsep)[0] == str(bundled_sumo / "bin")
    if os.name != "nt":
        assert env["LD_LIBRARY_PATH"] == "/original"
    assert os.environ["SUMO_HOME"] == "external"


def test_unicode_engine_uses_local_schemas_without_web_lookups(tmp_path):
    home = tmp_path / "Héctor México" / "sumo"
    xsd = home / "data" / "xsd"
    xsd.mkdir(parents=True)
    (xsd / "net_file.xsd").write_text('<schema name="network"/>')
    (xsd / "common").mkdir()
    (xsd / "common/types.xsd").write_text('<schema name="types"/>')
    directory = tmp_path / "escenario"
    directory.mkdir()
    value = runner._local_schema_home(home, directory)
    assert value.isascii() and not Path(value).is_absolute()
    assert (directory / value / "data/xsd/net_file.xsd").read_bytes() == (
        xsd / "net_file.xsd"
    ).read_bytes()
    assert (directory / value / "data/xsd/common/types.xsd").exists()
    assert runner._local_schema_home(home, directory) == value
