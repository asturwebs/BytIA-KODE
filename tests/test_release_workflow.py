"""AST-22: release.yml publica en PyPI por Trusted Publishers (OIDC).

El workflow es el PROD GATE en forma GitHub: tags `v*` → gates + build →
publish en el environment `pypi` (required reviewer = aprobación del Socio)
con `id-token: write` y cero secretos en el repo.

AST-23: tras publicar, `github-release` crea la GitHub Release del tag con
las notas extraídas de CHANGELOG.md — fuente única de verdad.
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
    # Cero secretos: ni expresiones ${{ secrets.* }} ni credenciales en steps.
    # (El escaneo busca la sintaxis de expresión, no la subcadena "secrets." —
    # matchearía con `scripts/check_secrets.py` del job de gates.)
    assert "${{ secrets." not in raw, "cero secretos referenciados en el workflow"


def test_build_runs_gates_before_packaging():
    wf, _ = _workflow()
    build = wf["jobs"]["build"]
    names = [s.get("name") or s.get("uses") or "" for s in build["steps"]]
    joined = " | ".join(names)
    order = [joined.find(m) for m in ("Secret scan", "Validate metadata", "Run tests", "Build distributions")]
    assert all(i >= 0 for i in order), f"gates ausentes en build: {joined}"
    assert order == sorted(order), "los gates deben correr antes de construir el paquete"


# --- AST-23: GitHub Release automática, notas del CHANGELOG ------------------

def test_github_release_runs_only_after_publish():
    wf, _ = _workflow()
    release = wf["jobs"]["github-release"]
    assert release["needs"] == ["build", "publish"], (
        "la Release sólo se crea si PyPI publicó — nada de anunciar lo no publicado"
    )


def test_github_release_write_is_scoped_to_that_job():
    # El permiso de escritura vive en el job, no en el workflow: publish y
    # build siguen con el mínimo (read / id-token).
    wf, _ = _workflow()
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["github-release"]["permissions"] == {"contents": "write"}
    publish_perms = wf["jobs"]["publish"]["permissions"]
    assert "contents" not in publish_perms


def test_release_notes_come_from_changelog_not_github():
    wf, _ = _workflow()
    release = wf["jobs"]["github-release"]
    extraction = [s for s in release["steps"] if "CHANGELOG.md" in str(s.get("run", ""))]
    assert extraction, "las notas se extraen del CHANGELOG (fuente única de verdad)"
    for step in release["steps"]:
        with_block = step.get("with") or {}
        assert not with_block.get("generate_release_notes"), (
            "el PR-list de GitHub es una segunda verdad: prohibido como fuente"
        )
    uses = [s.get("uses", "") for s in release["steps"]]
    assert any(u.startswith("softprops/action-gh-release") for u in uses), uses
    assert any("body_path" in (s.get("with") or {}) for s in release["steps"]), (
        "el body de la Release nace del archivo extraído del CHANGELOG"
    )


def test_notes_extraction_fails_without_changelog_entry():
    # El extractor es fail-closed: tag sin entrada en CHANGELOG → job rojo,
    # nunca una Release vacía.
    wf, _ = _workflow()
    release = wf["jobs"]["github-release"]
    extractor = next(
        s for s in release["steps"] if "CHANGELOG.md" in str(s.get("run", ""))
    )
    run = extractor["run"]
    assert "sys.exit" in run and "GITHUB_REF_NAME" in run
