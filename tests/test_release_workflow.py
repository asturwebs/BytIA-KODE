"""AST-22: release.yml publica en PyPI por Trusted Publishers (OIDC).

El workflow es el PROD GATE en forma GitHub: tags `v*` → gates + build →
publish en el environment `pypi` (required reviewer = aprobación del Socio)
con `id-token: write` y cero secretos en el repo.
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def _workflow():
    raw = WORKFLOW.read_text(encoding="utf-8")
    return yaml.safe_load(raw), raw


def _triggers(wf):
    # yaml 1.1 parsea la clave `on` como boolean True
    return wf.get(True) or wf.get("on") or {}


def test_workflow_triggers_only_on_version_tags():
    wf, _ = _workflow()
    push = _triggers(wf)["push"]
    assert push.get("tags") == ["v*"]
    assert "branches" not in push


def test_workflow_default_permissions_are_read_only():
    wf, _ = _workflow()
    assert wf["permissions"] == {"contents": "read"}


def test_publish_runs_in_pypi_environment():
    wf, _ = _workflow()
    publish = wf["jobs"]["publish"]
    assert publish["environment"] == "pypi", "PROD GATE: environment con required reviewer"
    assert publish["needs"] == "build"


def test_publish_uses_oidc_without_secrets():
    wf, raw = _workflow()
    publish = wf["jobs"]["publish"]
    assert publish["permissions"]["id-token"] == "write"
    steps = [s.get("uses") for s in publish["steps"]]
    assert "pypa/gh-action-pypi-publish@release/v1" in steps
    for step in publish["steps"]:
        with_block = step.get("with") or {}
        assert not {"password", "api-token"} & set(with_block), (
            "el publish no debe llevar credenciales: sólo OIDC"
        )
    assert "secrets." not in raw, "cero secretos referenciados en el workflow"


def test_build_runs_gates_before_packaging():
    wf, _ = _workflow()
    build = wf["jobs"]["build"]
    names = [s.get("name") or s.get("uses") or "" for s in build["steps"]]
    joined = " | ".join(names)
    order = [joined.find(m) for m in ("Secret scan", "Validate metadata", "Run tests", "Build distributions")]
    assert all(i >= 0 for i in order), f"gates ausentes en build: {joined}"
    assert order == sorted(order), "los gates deben correr antes de construir el paquete"
