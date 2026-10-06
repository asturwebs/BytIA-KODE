"""Gate CI: verdad ejecutable del README (AST-33).

Semilla: la tabla de verdad de AST-32 (issue AST-32, comentario de entrega) —
los claims verificados a mano allí quedan cubiertos aquí; los que necesitan
credenciales, TTY o red fuera de PyPI viven en listas EXPLÍCITAS con causa,
a la vista en la salida del gate. El gate no finge verificarlos.

Contrato (aprobado por el Socio en AST-33):

- Verifica SIN credenciales y sin red salvo PyPI (API JSON de pypi.org):
  comandos reales del paquete, paths documentados, ficheros/tests citados,
  paquetes externos citados (existencia — y AUSENCIA: bytia-tts debe dar 404,
  como dice el README), defaults de configuración contra el código, tablas de
  comandos/temas/tools contra las fuentes.
- FAIL CERRADO: una claim del README que no case con nada (comando nuevo,
  variable nueva, enlace roto, fila de tabla sin verificar) es un error del
  gate, no un warning. El que documenta algo nuevo, añade la cobertura o la
  declara con causa.
- Las claims interactivas/credenciales se DECLARAN (causa impresa), nunca se
  ejecutan con credenciales reales.

Uso:
    python scripts/check_readme_claims.py            # como CI (red: sólo PyPI)
    python scripts/check_readme_claims.py --offline-pypi   # hook local / tests

`--readme PATH` existe para los tests del propio gate (caso negativo); sin él
se verifica SIEMPRE el README del repo.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
README_DEFAULT = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"

PYPI_JSON = "https://pypi.org/pypi/{name}/json"

# --------------------------------------------------------------------------
# Disposiciones de los comandos que el README documenta en bloques bash (y en
# la tabla "Modos de ejecución"). Primera regla que matchea gana; una línea
# sin match es una claim nueva sin cubrir → FAIL. Buckets:
#   ok       — verificada por este gate (ejecutada ahora)
#   ci       — la verifica un paso propio del workflow, nombrado
#   declared — no verificable aquí, causa explícita (interactiva/credencial/
#              red fuera de PyPI / muta el entorno del runner)
# --------------------------------------------------------------------------
COMMAND_RULES: list[tuple[str, str, str]] = [
    (r"^bytia-kode --version$",
     "ok", "ejecutada: --version imprime la versión y sale 0"),
    (r"^uv run python scripts/check_readme_claims\.py$",
     "ok", "este mismo gate corriendo"),
    (r"^uv run python scripts/validate_metadata\.py$",
     "ok", "ejecutada por este gate (metadata validation OK)"),
    (r"^uv run python scripts/check_env_example\.py$",
     "ok", "ejecutada por este gate (subproceso — gate de plantilla .env, AST-36)"),
    (r"^uv run python scripts/check_report_citations\.py$",
     "ok", "ejecutada por este gate (subproceso — gate de citas SHA de reports, AST-35)"),
    (r"^bytia-kode$",
     "declared", "arranca la TUI: necesita TTY real (suite headless: tests/test_tui_interruption.py)"),
    (r"^bytia-kode --bot$",
     "declared", "necesita TELEGRAM_BOT_TOKEN — credencial (demo con stub en AST-32; suite: tests/test_bot_lifecycle.py)"),
    (r"^uv run bytia-kode$",
     "declared", "TUI interactiva: necesita TTY"),
    (r"^uv run python -m bytia_kode --bot$",
     "declared", "necesita TELEGRAM_BOT_TOKEN — credencial"),
    (r"^curl .*install\.sh \| bash$",
     "declared", "red fuera de PyPI (raw.githubusercontent.com, astral.sh) y muta HOME del runner"),
    (r"^uv tool install bytia-kode$",
     "declared", "muta el entorno del runner; la CI instala el paquete real (pip install -e .[dev] + smoke del wheel)"),
    (r"^pip install bytia-kode$",
     "declared", "muta el entorno del runner; la CI instala el paquete real"),
    (r"^mkdir -p ~/.bytia-kode$",
     "declared", "muta HOME del runner (el formato del .env se verifica contra .env.example)"),
    (r"^cat > .*<< 'EOF'$",
     "declared", "muta HOME del runner (variables y formato verificados contra .env.example y los defaults de config)"),
    (r"^uv sync$",
     "declared", "muta el venv del runner"),
    (r"^git clone https://github\.com/asturwebs/BytIA-KODE\.git$",
     "declared", "red fuera de PyPI (github.com)"),
    (r"^cd BytIA-KODE$",
     "declared", "paso del flujo de clone; no verificable aislado"),
    (r"^git config core\.hooksPath \.githooks$",
     "declared", "muta la config git del runner (el hook .githooks/pre-commit SÍ se verifica como path)"),
    (r"^git checkout -b .*$",
     "declared", "flujo fork→PR: necesita cuenta GitHub (credenciales)"),
    (r"^git commit -m .*$",
     "declared", "flujo fork→PR: necesita cuenta GitHub (credenciales)"),
    (r"^git push origin .*$",
     "declared", "flujo fork→PR: necesita credenciales push"),
    (r"^uv run pytest -q$",
     "ci", "Run tests corre la suite completa justo después de este gate"),
    (r"^uv build$",
     "ci", "Build wheel / Build distributions construye el paquete"),
    (r"^uv run python -m twine check dist/\*$",
     "ci", "Check distributions (twine check dist/*)"),
]

# Tabla "Stack técnico": nombre como aparece en el README → disposición.
#   ("pypi", <nombre normalizado>)   — existencia en PyPI + presente en pyproject
#   ("stdlib", causa)                — de la stdlib, sin claim de PyPI
#   ("absent", causa)                — el README afirma que NO está en PyPI
#   ("declared", causa)              — sin claim verificable aquí
STACK_RULES: dict[str, tuple[str, str]] = {
    "Textual": ("pypi", "textual"),
    "Rich": ("pypi", "rich"),
    "httpx": ("pypi", "httpx"),
    "Pydantic": ("pypi", "pydantic"),
    "PyYAML": ("pypi", "pyyaml"),
    "python-dotenv": ("pypi", "python-dotenv"),
    "python-telegram-bot": ("pypi", "python-telegram-bot"),
    "sqlite3": ("stdlib", "persistencia stdlib de Python — sin claim de PyPI"),
    "bytia-tts": ("absent", "el README afirma que NO está en PyPI — el gate comprueba el 404"),
    "piper": ("declared", "binario del sistema (voz es_AR-daniela-high): no es claim de PyPI"),
}

# Variables que el gate sabe leer del AppConfig en un env limpio (subproceso
# con HOME temporal y entorno scrubbed). Las tablas "Configuración principal"
# y "Configuración" del bot deben caer TODAS aquí — si no, claim sin cubrir.
CONFIG_FIELDS = {
    "PROVIDER_BASE_URL", "PROVIDER_API_KEY", "PROVIDER_MODEL",
    "FALLBACK_BASE_URL", "FALLBACK_API_KEY", "FALLBACK_MODEL",
    "LOCAL_BASE_URL", "LOCAL_MODEL",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_ALLOWED_USERS", "TELEGRAM_API_BASE",
    "DATA_DIR", "LOG_LEVEL", "LOG_FILE", "EXTRA_BINARIES",
}

# Atajos de la tabla TUI: celda → literal Binding en tui.py (minúsculas).
KEYBINDING_LITERALS = {
    "Ctrl+P": "ctrl+p", "Ctrl+Q": "ctrl+q", "Ctrl+R": "ctrl+r",
    "Ctrl+L": "ctrl+l", "Ctrl+M": "ctrl+m", "Ctrl+T": "ctrl+t",
    "Ctrl+S": "ctrl+s", "Ctrl+D": "ctrl+d", "Ctrl+E": "ctrl+e",
    "Ctrl+X": "ctrl+x", "Ctrl+Shift+C": "ctrl+shift+c",
    "F1": "f1", "F2": "f2", "F3": "f3",
}
KEYBINDING_DECLARED = {
    "↑": "binding estándar del Input de Textual (no vive en tui.py)",
    "↓": "binding estándar del Input de Textual (no vive en tui.py)",
    "Enter": "binding estándar del Input de Textual (no vive en tui.py)",
}

# Ficheros que el README documenta por nombre (además de los enlaces, que se
# extraen solos). Si el README deja de citar alguno, sobra aquí — se limpia.
DOCUMENTED_FILES = [
    "install.sh", ".env.example", "LICENSE", "CHANGELOG.md",
    "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "RELEASING.md", "AUTHORS.md",
    "docs/TUI.md", "docs/ARCHITECTURE.md", "docs/DEVELOPMENT.md",
    "docs/devlog/2026-04-02.md",
    ".github/workflows/ci.yml", ".github/workflows/release.yml",
    ".githooks/pre-commit",
    "scripts/validate_metadata.py", "scripts/check_readme_claims.py",
    "scripts/check_report_citations.py", "scripts/check_env_example.py",
    "src/bytia_kode/guardrail.py",
    "src/bytia_kode/prompts/kernel.default.yaml",
    "src/bytia_kode/prompts/runtime.default.yaml",
]

# Paquetes citados que deben EXISTIR en PyPI (instalación/stack del README).
PYPI_MUST_EXIST = [
    "bytia-kode", "textual", "rich", "httpx", "pydantic", "pyyaml",
    "python-dotenv", "python-telegram-bot",
]
# Paquetes que el README dice que NO están en PyPI.
PYPI_MUST_ABSENT = ["bytia-tts"]

# Claims declaradas no verificables por NADIE en CI (no comando, no paso):
# cualitativas, históricas o de runtime con credenciales. Se imprimen con
# causa; están aquí para que conste que el gate las vio y las excluye a propósito.
DECLARED_CLAIMS = [
    ("failover", "failover/circuit breaker EN VIVO contra providers reales — necesita providers levantados (la constante de 60 s sí se verifica; suite: tests/test_circuit_breaker.py)"),
    ("io-benchmark", "benchmark 4.90x — medición histórica 2026-04, el propio README declara que no hay benchmark reproducible en el repo"),
    ("autosave-o1", "auto-save O(1) por mensaje — cualitativo de diseño, sin benchmark en el repo"),
    ("sessions-shared", "TUI y bot comparten sessions.db — verificado por inspección en AST-32 (ambos enrutan por config.data_dir); suite: tests/test_session.py"),
    ("tts-e2e", "TTS end-to-end (bytia-tts + piper) — binarios ausentes en el runner de CI"),
    ("telegram-real", "bot contra api.telegram.org real — necesita TELEGRAM_BOT_TOKEN (credencial); AST-32 lo demostró con stub local + tests/test_bot_lifecycle.py"),
    ("bot-banner-live", "banner del bot con token real en pantalla — credencial; forma y máscara verificadas por tests/test_bot_lifecycle.py"),
    ("limitations", "Limitaciones conocidas (safe_mode visual, MCP WIP, estimador chars/3–3.5, Shift+Enter) — claims cualitativas de limitación, verificadas por inspección en AST-32"),
    ("yaml-override", "overrides de identidad en ~/.bytia-kode/prompts/ con deep-merge sin rebuild — comportamiento de runtime verificado por inspección en AST-32 (agent.py)"),
    ("ssrf-suite", "SSRF cerrada de web_fetch y allowlist de bash — verificadas por la suite (tests/test_web_fetch_ssrf.py, tests/test_bash_allowlist.py)"),
]


# --------------------------------------------------------------------------
# Reporte
# --------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.verified: list[str] = []
        self.covered_suite: list[str] = []
        self.covered_ci: list[str] = []
        self.declared: list[str] = []
        self.skipped: list[str] = []
        self.failures: list[str] = []

    def ok(self, cid: str, detail: str) -> None:
        self.verified.append(f"{cid}: {detail}")

    def suite(self, cid: str, cause: str) -> None:
        self.covered_suite.append(f"{cid}: {cause}")

    def ci(self, cid: str, cause: str) -> None:
        self.covered_ci.append(f"{cid}: {cause}")

    def declare(self, cid: str, cause: str) -> None:
        self.declared.append(f"{cid}: {cause}")

    def skip(self, cid: str, cause: str) -> None:
        self.skipped.append(f"{cid}: {cause}")

    def fail(self, cid: str, detail: str) -> None:
        self.failures.append(f"{cid}: {detail}")

    def summary(self) -> str:
        return (
            f"{len(self.verified)} verificadas · {len(self.covered_suite)} por suite · "
            f"{len(self.covered_ci)} por paso CI · {len(self.declared)} declaradas no "
            f"verificables (causa) · {len(self.skipped)} saltadas · {len(self.failures)} FALLOS"
        )

    def dump(self) -> None:
        print("[VERIFICADAS POR ESTE GATE]")
        for line in self.verified:
            print(f"  ✔ {line}")
        if self.covered_suite:
            print("[CUBIERTAS POR LA SUITE — pytest corre como paso propio de CI]")
            for line in self.covered_suite:
                print(f"  Ⓢ {line}")
        if self.covered_ci:
            print("[CUBIERTAS POR OTRO PASO DE CI — nombrado]")
            for line in self.covered_ci:
                print(f"  Ⓒ {line}")
        print("[DECLARADAS NO VERIFICABLES POR ESTE GATE — causa explícita]")
        for line in self.declared:
            print(f"  ✋ {line}")
        if self.skipped:
            print("[SALTADAS — modo offline]")
            for line in self.skipped:
                print(f"  ⏭ {line}")
        if self.failures:
            print("[FALLOS — claims que no verifican o no casan con nada]")
            for line in self.failures:
                print(f"  ✘ {line}")


# --------------------------------------------------------------------------
# Parsing del README
# --------------------------------------------------------------------------

IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def fence_blocks(text: str) -> list[tuple[str, str]]:
    """Bloques de código como (lenguaje, contenido)."""
    blocks: list[tuple[str, str]] = []
    lang, buf = None, []
    for line in text.splitlines():
        if lang is None:
            m = re.match(r"^```(\w*)\s*$", line)
            if m:
                lang, buf = m.group(1), []
        elif line.strip() == "```":
            blocks.append((lang, "\n".join(buf)))
            lang = None
        else:
            buf.append(line)
    return blocks


def bash_commands(text: str) -> list[str]:
    """Líneas de comando de los fences bash: sin comentarios, sin cuerpos de
    heredoc, sin comentarios en línea (`cmd  # nota`)."""
    out: list[str] = []
    for lang, body in fence_blocks(text):
        if lang != "bash":
            continue
        heredoc = None
        for raw in body.splitlines():
            if heredoc is not None:
                if raw.strip() == heredoc:
                    heredoc = None
                continue
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            if " # " in s:
                s = s.split(" # ", 1)[0].strip()
            m = re.search(r"<<\s*['\"]?(\w+)", s)
            out.append(s)
            if m:
                heredoc = m.group(1)
    return out


def md_links_and_images(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Enlaces [texto](target) e imágenes ![alt](src). Las imágenes se extraen
    primero y se retiran del texto: un badge es un enlace que ENVUELVE una
    imagen y el regex de enlaces no puede con paréntesis anidados."""
    spans = [(m.start(), m.end(), m.group(1)) for m in IMG_RE.finditer(text)]
    cleaned = list(text)
    for start, end, _ in spans:
        for i in range(start, end):
            cleaned[i] = " "
    links = [(m.group(1), m.group(2)) for m in LINK_RE.finditer("".join(cleaned))]
    return links, [src for _, _, src in spans]


def github_slug(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-")


def heading_slugs(text: str) -> set[str]:
    return {
        github_slug(m.group(2))
        for m in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", text, re.M)
    }


def section(text: str, title: str, level: int) -> str | None:
    """Cuerpo de la sección `title` (heading de `level` #s) hasta el siguiente
    heading de nivel igual o superior."""
    heading = "#" * level
    m = re.search(rf"^{heading}\s+{re.escape(title)}\s*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#{1,%d}\s" % level, rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def table_rows(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells and set("".join(cells)) <= set("-: "):
            continue  # separador
        rows.append(cells)
    return rows


def cell_text(cell: str) -> str:
    m = re.match(r"^\[([^\]]+)\]\(", cell)
    if m:
        return m.group(1)
    return cell.replace("`", "").strip()


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_cli(report: Report, version: str) -> None:
    """--version real del paquete (nunca arranca TUI/bot) + validate_metadata."""
    for flags in (["--version"], ["--version", "--bot"]):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "bytia_kode", *flags],
                capture_output=True, text=True, timeout=120, cwd=ROOT,
            )
        except Exception as exc:  # pragma: no cover - entorno roto
            report.fail("cli", f"`python -m bytia_kode {' '.join(flags)}` no pudo ejecutarse: {exc}")
            continue
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        if proc.returncode != 0:
            report.fail("cli", f"`--version {' '.join(flags[1:])}` salió rc={proc.returncode}: {err[:200]}")
            continue
        if out.split("+", 1)[0] != version:
            report.fail("cli", f"`--version {' '.join(flags[1:])}` imprimió {out!r}; la versión de pyproject es {version!r}")
            continue
        report.ok("cli", f"`bytia-kode {' '.join(flags)}` → {out!r} rc=0 (la TUI/bot nunca arrancan)")

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_metadata.py")],
        capture_output=True, text=True, timeout=120, cwd=ROOT,
    )
    if proc.returncode == 0 and "metadata validation OK" in (proc.stdout or ""):
        report.ok("cli", "scripts/validate_metadata.py → metadata validation OK")
    else:
        report.fail("cli", f"validate_metadata falló (rc={proc.returncode}): {(proc.stdout or '') + (proc.stderr or '')}".strip()[:200])

    # AST-35: gate de citas SHA de reports/ — mismo trato que validate_metadata.
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_report_citations.py")],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
    )
    if proc.returncode == 0 and "GATE EN VERDE" in (proc.stdout or ""):
        report.ok("cli", "scripts/check_report_citations.py → GATE EN VERDE")
    else:
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-600:]
        report.fail("cli", f"check_report_citations falló (rc={proc.returncode}): {tail}")

    # AST-36: gate de plantilla .env — sin placeholders vacíos descomentados.
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_env_example.py")],
        capture_output=True, text=True, timeout=120, cwd=ROOT,
    )
    if proc.returncode == 0 and "GATE EN VERDE" in (proc.stdout or ""):
        report.ok("cli", "scripts/check_env_example.py → GATE EN VERDE")
    else:
        tail = ((proc.stdout or "") + (proc.stderr or "")).strip()[-600:]
        report.fail("cli", f"check_env_example falló (rc={proc.returncode}): {tail}")


def check_paths(report: Report) -> None:
    missing = [f for f in DOCUMENTED_FILES if not (ROOT / f).exists()]
    if missing:
        for f in missing:
            report.fail("paths", f"fichero documentado que NO existe: {f}")
    else:
        report.ok("paths", f"{len(DOCUMENTED_FILES)} ficheros citados por nombre existen")


def check_links(report: Report, text: str, pypi_ok: bool | None) -> None:
    links, images = md_links_and_images(text)
    slugs = heading_slugs(text)
    rel_missing: list[str] = []
    anchors_bad: list[str] = []
    for label, target in links:
        if target.startswith(("http://", "https://")):
            host = urlparse(target).netloc
            if host == "pypi.org":
                # El badge/enlace PyPI apunta a la ficha del paquete: lo cubre
                # el check de existencia en PyPI (G-pypi).
                if pypi_ok is True:
                    report.ok("links", f"enlace PyPI → {target} (ficha verificada vía API)")
                elif pypi_ok is None:
                    report.skip("links", f"enlace PyPI → {target} (G-pypi saltado en modo offline)")
                # pypi_ok False ya quedó registrado como FALLO en G-pypi
            else:
                report.declare("links", f"enlace externo fuera del perímetro de red del gate (sólo PyPI): {target}")
            continue
        if target.startswith("#"):
            if target[1:] not in slugs:
                anchors_bad.append(target)
            continue
        path = target.split("#", 1)[0]
        if path and not (ROOT / path).exists():
            rel_missing.append(target)
    for src in images:
        if not src.startswith(("http://", "https://")):
            rel_missing.append(src + " (imagen relativa: no renderiza en PyPI)")
    if rel_missing:
        for t in rel_missing:
            report.fail("links", f"ruta relativa rota en el README: {t}")
    elif anchors_bad:
        for t in anchors_bad:
            report.fail("links", f"ancla interna sin heading correspondiente: {t}")
    else:
        report.ok("links", f"{len(links)} enlaces + {len(images)} imágenes resueltos (relativos existen, anclas válidas, externos dispuestos)")


def check_arch_tree(report: Report, text: str) -> None:
    body = section(text, "Arquitectura", 2)
    if body is None:
        report.fail("tree", "no se encontró la sección '## Arquitectura'")
        return
    files: list[str] = []
    for lang, block in fence_blocks(body):
        if lang == "text":
            # 'prompts/kernel.default.yaml' trae puntos dentro del nombre:
            # el patrón admite segmentos puntuados antes de la extensión final.
            # Notación del diagrama: 'prompts/a.yaml + b.yaml' — el segundo
            # hereda el directorio del primero DENTRO de la misma línea.
            token_re = r"[\w/]+(?:\.[\w/]+)*\.(?:py|yaml)"
            for line in block.splitlines():
                dir_prefix = ""
                for tok in re.findall(token_re, line):
                    if "/" in tok:
                        dir_prefix = tok.rsplit("/", 1)[0] + "/"
                        files.append(tok)
                    else:
                        files.append(dir_prefix + tok if dir_prefix else tok)
            break
    if not files:
        report.fail("tree", "el diagrama de Arquitectura no nombra ficheros .py/.yaml")
        return
    pkg = SRC / "bytia_kode"
    missing = [f for f in files if not (pkg / f).exists()]
    if missing:
        for f in missing:
            report.fail("tree", f"fichero del diagrama de Arquitectura que NO existe: src/bytia_kode/{f}")
    else:
        report.ok("tree", f"{len(files)} ficheros del diagrama de Arquitectura existen bajo src/bytia_kode/")


def check_vendor_skills(report: Report, text: str) -> None:
    m = re.search(r"Skills vendor incluidas: (.+?)\.\s", text)
    if not m:
        report.fail("vendor", "no se encontró la frase 'Skills vendor incluidas: …' del README")
        return
    claimed = set(re.findall(r"\*\*([^*]+)\*\*", m.group(1)))
    vendor_dir = SRC / "bytia_kode" / "vendor" / "skills"
    actual = {d.name for d in vendor_dir.iterdir() if d.is_dir()} if vendor_dir.exists() else set()
    if claimed == actual and claimed:
        report.ok("vendor", f"skills vendor del README = directorios del paquete: {sorted(claimed)}")
    else:
        report.fail("vendor", f"deriva en skills vendor — README: {sorted(claimed)}, paquete: {sorted(actual)}")


def _pyproject() -> dict:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _dep_floor(deps: list[str], name: str) -> str | None:
    for dep in deps:
        base = re.match(r"[A-Za-z0-9_.\-]+", dep)
        if base and base.group(0).lower() == name.lower():
            m = re.search(r">=\s*([0-9][\w.]*)", dep)
            return m.group(1) if m else None
    return None


def check_badges(report: Report, text: str, images: list[str]) -> None:
    proj = _pyproject()["project"]
    deps = proj.get("dependencies", [])
    badges = [unquote(u) for u in images if "img.shields.io/badge/" in u]

    def badge_floor(label: str) -> str | None:
        for b in badges:
            m = re.search(rf"badge/{re.escape(label)}-([0-9.]+)\+-", b)
            if m:
                return m.group(1)
        return None

    py_floor = re.search(r">=\s*([0-9.]+)", proj.get("requires-python", ""))
    pairs = [
        ("python", "python", py_floor.group(1) if py_floor else None),
        ("Textual", "textual", _dep_floor(deps, "textual")),
        ("Telegram Bot", "python-telegram-bot", _dep_floor(deps, "python-telegram-bot")),
    ]
    for label, dep_name, real in pairs:
        claimed = badge_floor(label)
        if claimed is None:
            report.fail("badges", f"badge '{label}' no encontrada en el README (¿la quitaste? actualiza también este gate)")
        elif real is None:
            report.fail("badges", f"pyproject no declara '{dep_name}' pero el badge dice {label} {claimed}+")
        elif claimed != real:
            report.fail("badges", f"badge {label} {claimed}+ desincronizada con pyproject ({dep_name}>={real})")
        else:
            report.ok("badges", f"badge {label} {claimed}+ = pyproject ({dep_name}>={real})")

    lic = None
    for b in badges:
        m = re.search(r"badge/license-(\w+)-", b)
        if m:
            lic = m.group(1)
    license_text = str(proj.get("license", {}).get("text", ""))
    license_file = (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").exists() else ""
    if lic and license_text == lic and lic in license_file:
        report.ok("badges", f"badge license {lic} = pyproject.license + fichero LICENSE")
    else:
        report.fail("badges", f"licencia divergente: badge={lic!r} pyproject={license_text!r} LICENSE contiene {lic!r}: {lic in license_file}")

    wal = None
    for b in badges:
        m = re.search(r"badge/SQLite WAL-(\w+)-", b)
        if m:
            wal = m.group(1)
    session_src = (SRC / "bytia_kode" / "session.py").read_text(encoding="utf-8")
    if wal == "enabled" and "PRAGMA journal_mode=WAL" in session_src:
        report.ok("badges", "badge SQLite WAL enabled = 'PRAGMA journal_mode=WAL' en session.py")
    else:
        report.fail("badges", f"badge SQLite WAL={wal!r} sin respaldo en session.py (PRAGMA journal_mode=WAL)")


PROBE_CODE = '''
import json, os, sys, tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp(prefix="readme-claims-probe-"))
os.environ["HOME"] = str(home)
os.chdir(home)
for k in list(os.environ):
    if k.startswith(("PROVIDER_", "FALLBACK_", "LOCAL_", "TELEGRAM_", "DEEPSEEK_",
                     "UNSLOTH_", "JEVAL_", "LLM_", "LOG_", "DATA_DIR",
                     "EXTRA_BINARIES")):
        os.environ.pop(k, None)

src = __SRC__
if src and src not in sys.path:
    sys.path.insert(0, src)

from bytia_kode.config import AppConfig
cfg = AppConfig()

print(json.dumps({
    "PROVIDER_BASE_URL": cfg.provider.base_url,
    "PROVIDER_API_KEY": cfg.provider.api_key,
    "PROVIDER_MODEL": cfg.provider.model,
    "FALLBACK_BASE_URL": cfg.provider.fallback_url,
    "FALLBACK_API_KEY": cfg.provider.fallback_key,
    "FALLBACK_MODEL": cfg.provider.fallback_model,
    "LOCAL_BASE_URL": cfg.provider.local_url,
    "LOCAL_MODEL": cfg.provider.local_model,
    "TELEGRAM_BOT_TOKEN": cfg.telegram.bot_token,
    "TELEGRAM_ALLOWED_USERS": ",".join(str(u) for u in cfg.telegram.allowed_users),
    "TELEGRAM_API_BASE": cfg.telegram.api_base,
    "LOG_LEVEL": cfg.log_level,
    "LOG_FILE": cfg.log_file,
    "EXTRA_BINARIES": ",".join(sorted(cfg.extra_binaries)),
    "DATA_DIR": ("~/.bytia-kode" if str(cfg.data_dir) == str(home / ".bytia-kode")
                 else str(cfg.data_dir)),
}))
'''


def _probe_defaults() -> dict[str, str] | None:
    code = PROBE_CODE.replace("__SRC__", json.dumps(str(SRC)))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=180,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads((proc.stdout or "").strip().splitlines()[-1])
    except Exception:
        return None


def check_config_defaults(report: Report, text: str) -> None:
    """Tabla 'Configuración principal' + tabla de config del bot vs AppConfig
    real en un env limpio (HOME temporal, entorno scrubbed) + cobertura en
    .env.example ('todas las variables: .env.example del repo')."""
    probe = _probe_defaults()
    if probe is None:
        report.fail("cfg", "no se pudo instanciar AppConfig en env limpio (subproceso) — revisar salida manualmente")
        return

    main_body = section(text, "Configuración principal", 3)
    bot_body = section(text, "Configuración", 3)
    rows = table_rows(main_body or "")[1:] + table_rows(bot_body or "")[1:]

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    mismatches: list[str] = []
    uncovered: list[str] = []
    missing_example: list[str] = []
    checked = 0
    for cells in rows:
        if not cells or not cells[0]:
            continue
        var = cell_text(cells[0])
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", var):
            continue  # encabezado u otra tabla
        if var not in CONFIG_FIELDS:
            uncovered.append(var)
            continue
        checked += 1
        if len(cells) >= 3:
            # tabla con columna de default (Configuración principal): el
            # valor documentado debe ser el default real del código
            expected = cell_text(cells[-1])
            if expected == "vacío":
                expected = ""
            actual = probe.get(var)
            if actual != expected:
                mismatches.append(f"{var}: README={expected!r} código={actual!r}")
        # ambas tablas: cobertura en .env.example ("todas las variables").
        # AST-36: los placeholders de la plantilla van COMENTADOS (`# VAR=`)
        # — una línea vacía descomentada pisa el .env global — así que la
        # cobertura acepta la forma activa o la comentada; que no haya NINGUNA
        # de las dos sigue siendo fallo, y la forma vacía activa la caza el
        # gate propio scripts/check_env_example.py.
        if not re.search(rf"^(?:#[ \t]*)?{var}=", env_example, re.M):
            missing_example.append(var)

    if uncovered:
        for v in uncovered:
            report.fail("cfg", f"variable documentada sin cobertura en el gate (añádela a CONFIG_FIELDS o declárala): {v}")
    if mismatches:
        for mm in mismatches:
            report.fail("cfg", f"default divergente — {mm}")
    if missing_example:
        for v in missing_example:
            report.fail("cfg", f"variable del README ausente de .env.example (el README dice 'todas las variables'): {v}")
    if not (uncovered or mismatches or missing_example):
        report.ok("cfg", f"{checked} variables de configuración del README = defaults reales de AppConfig (env limpio) y documentadas en .env.example (activas o comentadas, AST-36)")


def check_themes(report: Report, text: str) -> None:
    m = re.search(
        r"`F2` para cambiar entre los (\d+) temas disponibles \((\d+) oscuros \+ (\d+) claros, por defecto `([^`]+)`\)",
        text,
    )
    if not m:
        report.fail("themes", "no se encontró la frase de temas ('F2 para cambiar entre los N temas…')")
        return
    n, dark, light, default = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    try:
        sys.path.insert(0, str(SRC))
        from bytia_kode.tui import ALL_THEMES, DEFAULT_THEME, LIGHT_THEMES
    except Exception as exc:
        report.fail("themes", f"no se pudo importar bytia_kode.tui (¿dependencias instaladas?): {exc}")
        return
    finally:
        try:
            sys.path.remove(str(SRC))
        except ValueError:  # pragma: no cover
            pass
    ok = (
        len(ALL_THEMES) == n
        and len(LIGHT_THEMES) == light
        and len(ALL_THEMES) - len(LIGHT_THEMES) == dark
        and DEFAULT_THEME == default
    )
    if ok:
        report.ok("themes", f"{n} temas ({dark} oscuros + {light} claros), default {default!r} = tui.py (ALL_THEMES/LIGHT_THEMES/DEFAULT_THEME)")
    else:
        report.fail("themes", f"deriva en temas — README: {n}/{dark}+{light} default {default!r}; tui.py: {len(ALL_THEMES)}/{len(ALL_THEMES)-len(LIGHT_THEMES)}+{len(LIGHT_THEMES)} default {DEFAULT_THEME!r}")


def _tool_names() -> set[str]:
    names: set[str] = set()
    tools_dir = SRC / "bytia_kode" / "tools"
    for py in tools_dir.glob("*.py"):
        names.update(re.findall(r'^\s{4}name = "([\w_]+)"', py.read_text(encoding="utf-8"), re.M))
    return names


def check_tools(report: Report, text: str) -> None:
    body = section(text, "Tools", 3)
    if body is None:
        report.fail("tools", "no se encontró la sección '### Tools'")
        return
    rows = table_rows(body)[1:]
    claimed = {cell_text(c[0]) for c in rows if c and c[0].startswith("`")}
    actual = _tool_names()
    if claimed != actual:
        report.fail("tools", f"deriva en tools — README: {sorted(claimed)}; código: {sorted(actual)}")
        return
    m = re.search(r"(\d+) tools \(", text)
    if m and int(m.group(1)) != len(actual):
        report.fail("tools", f"el README dice '{m.group(1)} tools' pero el código registra {len(actual)}")
        return
    report.ok("tools", f"{len(actual)} tools de la tabla = nombres registrados en src/bytia_kode/tools/ (igual en ambas direcciones)")


def check_commands(report: Report, text: str) -> None:
    tui_src = (SRC / "bytia_kode" / "tui.py").read_text(encoding="utf-8")
    bot_src = (SRC / "bytia_kode" / "telegram" / "bot.py").read_text(encoding="utf-8")

    tui_body = section(text, "Comandos", 3)  # TUI → '### Comandos' dentro de '## TUI'
    sessions_body = section(text, "Sesiones persistentes", 3)
    bot_body = section(text, "Comandos del bot", 3)

    tui_rows = table_rows(tui_body or "")[1:] + table_rows(sessions_body or "")[1:]
    missing: list[str] = []
    seen: set[str] = set()
    for cells in tui_rows:
        if not cells or not cells[0].startswith("`/"):
            continue
        # una celda puede listar varios comandos: '`/quit`, `/exit`, `/q`'
        for cmd in re.findall(r"/\w+", cells[0]):
            seen.add(cmd)
            if cmd not in tui_src:
                missing.append(cmd)
    if missing:
        for c in missing:
            report.fail("cmd", f"comando TUI documentado que NO está en tui.py: {c}")
    elif seen:
        report.ok("cmd", f"{len(seen)} comandos TUI/sesiones documentados presentes en tui.py ({sorted(seen)})")
    else:
        report.fail("cmd", "no se parseó ningún comando TUI (¿cambiaron las tablas?)")

    bot_cmds = [cell_text(c[0]).lstrip("/") for c in table_rows(bot_body or "")[1:] if c and c[0].startswith("`/")]
    bot_missing = [c for c in bot_cmds if f'CommandHandler("{c}"' not in bot_src]
    if bot_missing:
        for c in bot_missing:
            report.fail("cmd", f"comando del bot documentado sin CommandHandler en bot.py: /{c}")
    elif bot_cmds:
        report.ok("cmd", f"{len(bot_cmds)} comandos del bot registrados con CommandHandler en bot.py ({sorted(bot_cmds)})")
    else:
        report.fail("cmd", "no se parseó ningún comando del bot (¿cambió la tabla?)")


def check_keybindings(report: Report, text: str) -> None:
    body = section(text, "Atajos", 3)
    if body is None:
        report.fail("keys", "no se encontró la sección '### Atajos'")
        return
    tui_src = (SRC / "bytia_kode" / "tui.py").read_text(encoding="utf-8")
    missing: list[str] = []
    verified = 0
    for cells in table_rows(body)[1:]:
        if not cells or not cells[0]:
            continue
        raw = cells[0].replace("`", "").strip()
        # '↑ / ↓' son dos declaradas en una celda
        parts = [p.strip() for p in raw.split("/")] if raw in ("↑ / ↓",) else [raw]
        for part in parts:
            rng = re.fullmatch(r"F(\d+)–F(\d+)", part)
            if rng:  # 'F4–F8' → f4..f8, cada uno debe tener Binding
                keys = [f"f{i}" for i in range(int(rng.group(1)), int(rng.group(2)) + 1)]
            elif part in KEYBINDING_LITERALS:
                keys = [KEYBINDING_LITERALS[part]]
            elif part in KEYBINDING_DECLARED:
                report.declare("keys", f"atajo {part}: {KEYBINDING_DECLARED[part]}")
                continue
            else:
                missing.append(f"{part} (sin regla en el gate — nueva en el README)")
                continue
            for key in keys:
                if f'"{key}"' in tui_src:
                    verified += 1
                else:
                    missing.append(f"{part} (Binding '{key}' no está en tui.py)")
    if missing:
        for m in missing:
            report.fail("keys", f"atajo documentado sin respaldo: {m}")
    else:
        report.ok("keys", f"{verified} atajos con Binding literal en tui.py + {len(KEYBINDING_DECLARED)} declarados (Input estándar)")


def check_constants(report: Report, text: str) -> None:
    guardrail_src = (SRC / "bytia_kode" / "guardrail.py").read_text(encoding="utf-8")
    circuit_src = (SRC / "bytia_kode" / "providers" / "circuit.py").read_text(encoding="utf-8")
    registry_src = (SRC / "bytia_kode" / "tools" / "registry.py").read_text(encoding="utf-8")

    # JEVAL: defaults off / 0.7 / 2.0 + env TYPESAFE_API_KEY + log path citado
    jeval = [
        ("modo default `off`", '"JEVAL_MODE", "off"' in guardrail_src),
        ("threshold default `0.7`", '"JEVAL_THRESHOLD", "0.7"' in guardrail_src),
        ("timeout default `2.0` s", '"JEVAL_TIMEOUT", "2.0"' in guardrail_src),
        ("requiere TYPESAFE_API_KEY", "TYPESAFE_API_KEY" in guardrail_src),
        ("log kode-guardrail.jsonl", "kode-guardrail.jsonl" in guardrail_src),
    ]
    bad = [name for name, ok in jeval if not ok]
    if bad:
        for b in bad:
            report.fail("consts", f"claim JEVAL sin respaldo en guardrail.py: {b}")
    else:
        report.ok("consts", "JEVAL off/0.7/2.0 + TYPESAFE_API_KEY + log kode-guardrail.jsonl = guardrail.py")

    # Circuit breaker: recuperación a los 60 s
    m = re.search(r"se recupera a los (\d+) s", text)
    c = re.search(r"recovery_timeout:\s*float\s*=\s*([\d.]+)", circuit_src)
    if m and c and float(c.group(1)) == float(m.group(1)):
        report.ok("consts", f"recuperación del circuit breaker a los {m.group(1)} s = circuit.py (recovery_timeout={c.group(1)})")
    else:
        report.fail("consts", f"recuperación del breaker divergente — README: {m.group(1) if m else '?'} s; circuit.py: {c.group(1) if c else '?'}")

    # web_fetch: límite 1 MiB
    mb = re.search(r"límite (\d+) MiB", text)
    cap = re.search(r"_MAX_DOWNLOAD_BYTES = ([\d_]+)", registry_src)
    if mb and cap and int(cap.group(1).replace("_", "")) == int(mb.group(1)) * 1024 * 1024:
        report.ok("consts", f"límite {mb.group(1)} MiB de web_fetch = registry.py (_MAX_DOWNLOAD_BYTES={cap.group(1)})")
    else:
        report.fail("consts", f"límite de web_fetch divergente — README: {mb.group(1) if mb else '?'} MiB; registry.py: {cap.group(1) if cap else '?'}")

    # BashTool: sin shell + tokenización con shlex.split (tabla Seguridad:
    # "Allowlist de binarios + shell=False + shlex.split()"). La claim real
    # del código es que NUNCA se invoca una shell: 'shell=True' ausente.
    sec = [("sin shell (shell=True ausente)", "shell=True" not in registry_src), ("shlex.split", "shlex.split" in registry_src)]
    bad = [n for n, ok in sec if not ok]
    if bad:
        for b in bad:
            report.fail("consts", f"claim de seguridad de bash sin respaldo en registry.py: {b}")
    else:
        report.suite("consts", "allowlist de bash + SSRF de web_fetch verificadas por tests/test_bash_allowlist.py y tests/test_web_fetch_ssrf.py (shell=False/shlex.split presentes en registry.py)")


def _pypi_status(name: str) -> int | None:
    req = urllib.request.Request(
        PYPI_JSON.format(name=name),
        headers={"User-Agent": "bytia-kode-readme-claims-gate"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return None  # red caída: el gate falla cerrado en su propio perímetro


def check_pypi(report: Report, offline: bool) -> bool | None:
    """Existencia (y ausencia) en PyPI de los paquetes citados. Devuelve el
    resultado para 'bytia-kode' (None = no comprobado, para el enlace PyPI)."""
    bytia_kode_ok: bool | None = None
    for name in PYPI_MUST_EXIST:
        if offline:
            report.skip("pypi", f"existencia de {name} en PyPI (modo offline)")
            if name == "bytia-kode":
                bytia_kode_ok = None
            continue
        status = _pypi_status(name)
        if status == 200:
            report.ok("pypi", f"{name} existe en PyPI (200)")
            if name == "bytia-kode":
                bytia_kode_ok = True
        else:
            report.fail("pypi", f"{name} debería existir en PyPI — status={status}")
            if name == "bytia-kode":
                bytia_kode_ok = False
    for name in PYPI_MUST_ABSENT:
        if offline:
            report.skip("pypi", f"ausencia de {name} en PyPI (modo offline)")
            continue
        status = _pypi_status(name)
        if status == 404:
            report.ok("pypi", f"{name} NO está en PyPI (404) — como dice el README")
        else:
            report.fail("pypi", f"{name} debería dar 404 en PyPI (el README afirma que no está) — status={status}")
    return bytia_kode_ok


def check_stack(report: Report, text: str) -> None:
    body = section(text, "Stack técnico", 3)
    if body is None:
        report.fail("stack", "no se encontró la sección '### Stack técnico'")
        return
    proj = _pyproject()["project"]
    deps = [re.match(r"[A-Za-z0-9_.\-]+", d).group(0).lower() for d in proj.get("dependencies", [])]
    rows = table_rows(body)[1:]
    for cells in rows:
        if not cells:
            continue
        name = cell_text(cells[0])
        rule = STACK_RULES.get(name)
        if rule is None:
            report.fail("stack", f"librería nueva en la tabla Stack sin disposición en el gate: {name}")
            continue
        kind, arg = rule
        if kind == "pypi":
            if arg.lower() in deps:
                report.ok("stack", f"{name}: en PyPI (G-pypi) y en dependencies de pyproject")
            else:
                report.fail("stack", f"{name} documentada en el stack pero AUSENTE de pyproject dependencies")
        elif kind == "stdlib":
            report.ok("stack", f"{name}: {arg}")
        elif kind == "absent":
            report.ok("stack", f"{name}: {arg} (G-pypi)")
        else:
            report.declare("stack", f"{name}: {arg}")


def check_command_coverage(report: Report, text: str) -> None:
    """FAIL CERRADO sobre comandos: cada línea de los fences bash (y cada fila
    de 'Modos de ejecución') debe casar con una regla — nueva claim = error."""
    lines = bash_commands(text)
    modes_body = section(text, "Modos de ejecución", 3)
    for cells in table_rows(modes_body or "")[1:]:
        if cells and cells[0].startswith("`"):
            lines.append(cell_text(cells[0]))
    for line in lines:
        for pattern, bucket, note in COMMAND_RULES:
            if re.match(pattern, line):
                if bucket == "ok":
                    report.ok("cmd-coverage", f"`{line}` — {note}")
                elif bucket == "ci":
                    report.ci("cmd-coverage", f"`{line}` — {note}")
                else:
                    report.declare("cmd-coverage", f"`{line}` — {note}")
                break
        else:
            report.fail("cmd-coverage", f"comando del README sin cubrir (nuevo? añade regla o decláralo): `{line}`")


def check_declared(report: Report) -> None:
    for cid, cause in DECLARED_CLAIMS:
        report.declare(cid, cause)


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate de verdad ejecutable del README (AST-33)")
    parser.add_argument("--readme", type=Path, default=README_DEFAULT,
                        help="README alternativo (sólo para tests del propio gate)")
    parser.add_argument("--offline-pypi", action="store_true",
                        help="saltar los checks de PyPI (hook local / suite hermética); se declaran como saltados")
    args = parser.parse_args(argv)

    readme = args.readme if args.readme.is_absolute() else ROOT / args.readme
    text = readme.read_text(encoding="utf-8")
    version = str(_pyproject()["project"].get("version", ""))
    _, images = md_links_and_images(text)

    report = Report()
    print(f"== README claims gate (AST-33) — {readme} ==")

    pypi_ok = check_pypi(report, args.offline_pypi)
    check_cli(report, version)
    check_paths(report)
    check_links(report, text, pypi_ok)
    check_arch_tree(report, text)
    check_vendor_skills(report, text)
    check_badges(report, text, images)
    check_config_defaults(report, text)
    check_themes(report, text)
    check_tools(report, text)
    check_commands(report, text)
    check_keybindings(report, text)
    check_constants(report, text)
    check_stack(report, text)
    check_command_coverage(report, text)
    check_declared(report)

    report.dump()
    print()
    print(f"RESULTADO: {report.summary()}")
    if report.failures:
        print("GATE EN ROJO: hay claims del README que no verifican o no casan con ninguna cobertura.")
        return 1
    print("GATE EN VERDE: toda claim del README está verificada, cubierta por la suite/CI, o declarada con causa.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
