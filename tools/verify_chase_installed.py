"""Run from outside checkout using only installed origins and saved full reports."""

from pathlib import Path
import importlib
import json
import subprocess
import sys
import tempfile
import copy

expected = json.load(open(sys.argv[1]))
origins = []
for name in [
    "provlab",
    "provlab.input",
    "provlab.chase",
    "provlab.chase_verify",
    "provlab.chase_cli",
]:
    m = importlib.import_module(name)
    p = Path(m.__file__).resolve()
    assert "site-packages" in p.parts, (name, str(p))
    origins.append(str(p))
from provlab.chase import analyze
from provlab.chase_verify import verify

entry = [str(Path(sys.executable).with_name("provlab-chase"))]
modules = [sys.executable, "-m", "provlab.chase_cli"]
for e in expected:
    assert analyze(e["input"]) == e["report"]
    assert verify(e["report"])
with tempfile.TemporaryDirectory() as d:
    for command in [modules, entry]:
        for e in expected:
            p = subprocess.run(
                command + ["-"],
                input=json.dumps(e["input"]),
                text=True,
                capture_output=True,
                cwd=d,
            )
            assert p.returncode == 0, p.stderr
            assert json.loads(p.stdout) == e["report"]
            p = subprocess.run(
                command + ["-", "--verify"],
                input=json.dumps(e["report"]),
                text=True,
                capture_output=True,
                cwd=d,
            )
            assert p.returncode == 0, p.stderr
            assert json.loads(p.stdout) == {
                "valid": True,
                "schema": "provlab-chase-v1",
            }
    for i in range(20):
        r = copy.deepcopy(expected[i % len(expected)]["report"])
        r["literal_constants"] = "forged"
        p = subprocess.run(
            entry + ["-", "--verify"],
            input=json.dumps(r),
            text=True,
            capture_output=True,
            cwd=d,
        )
        assert p.returncode == 2
        assert p.stdout == ""
        assert "Traceback" not in p.stderr
print(
    json.dumps(
        {
            "reports": len(expected),
            "entrypoints": 2,
            "installed_origins": origins,
            "forged_cli_rejections": 20,
        }
    )
)
