"""Gate CI: toda cita SHA de `reports/` resuelve, está anotada, o rojo (AST-35).

Semilla: el incidente del addendum de AST-34 — cuatro versiones de un mismo
número porque el método (regex sobre hex) no clasificaba, y lo que evitó
publicar el defecto fue el juicio de un agente parándose antes del push.
Ese ahorro de suerte era cronología, no diseño: aquí pasa a ser comprobación.

Contrato (AST-35, **2 criterios**). Toda cita con forma de SHA en
`reports/*.md` debe:

1. **resolver** en el repo (`git cat-file --batch-check <token>^{commit}`), **o**
2. estar **anotada explícitamente**: sufijo de anotación justo después del
   token (`@ws` / `@bundle` / `@nocommit`), o entrada en `DECLARED_CITATIONS`
   con clase y causa — la convención para citas dentro de salida de git
   copiada literal, donde el sufijo falsearía la cita que se está
   transcribiendo.

Si no cumple ninguna → **FALLO**, con `fichero:línea` y token. Fail cerrado.

**Por qué 2 y no 3 criterios** (nota de diseño de la terminal PI en AST-35;
llamada del implementador): el criterio intermedio de "whitelist de
no-commits por patrón" (id decimal junto a `MagicMock`, token pegado a un
guion) clasifica **sin preguntarle a git**, y la forma no clasifica — es el
mismo método roto que produjo el "32" de AST-34 (`5537803` es decimal y sí
es un commit; `d284fe7c` tiene letras y no lo es). Un `revert-768d3ff` pegaría
un commit real a un guion y saldría inventariado como "fragmento de UUID": la
clase mentiría en silencio. Aquí toda clasificación es o bien **verificada
por git** o bien **anotada a mano con causa registrada** — nada se infiere de
la forma del token.

Convención de anotación (definida en AST-35):

    `2341a78@ws`       hash del workspace de Paperclip — `git am` recrea
                       hashes propios, nunca fue commit de main
                       (gotcha #9 de la skill paperclip)
    `768d3ff@bundle`   commit de la historia pre-reescritura: solo resuelve en
                       el bundle pre-rewrite / en el main anterior al rewrite
    `deadbee@nocommit` el token no identifica ningún commit (id de mock,
                       fragmento de UUID de agente/run/issue)

Un token puede estar declarado de las dos formas; el sufijo manda en la línea
donde aparece y `DECLARED_CITATIONS` cubre el resto.

Método (regla de AST-34, ya en el addendum): el inventario se imprime **por
clase**, con los tokens y dónde se citan — jamás un conteo global de "hex
encontrados". El titular de este gate es el veredicto, no un número.

Todo run de 7..40 hex es cita, **también si es puramente decimal**: `5537803`
es un commit real y con un filtro de "decimales cortos" este gate lo habría
ignorado en silencio en su primera corrida. Una fecha compacta tipo
`20991231` cae igual — fail cerrado — y se anota (`20991231@nocommit` o, si
es un literal citado donde el sufijo falsearía el texto —p.ej. la fecha
dentro del nombre del bundle del rewrite—, registro en `DECLARED_CITATIONS`
con causa).

Corpus de diseño (AST-35): `reports/CTO-addendum-rewrite-20261003.md` — la
tabla de 3 clases y las 19 traducciones patch-id del rewrite. Sobre él el
gate distingue lo que resuelve (gemelos post-rewrite), lo anotado (12 ws +
7 bundle + no-commits) y el residual (stamps de release pre-rewrite y la
fecha del bundle, registrados con causa en `DECLARED_CITATIONS`): 0 FALLOS.

Uso:
    python scripts/check_report_citations.py
    python scripts/check_report_citations.py --repo DIR --reports-dir DIR
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 7..40 hex sin hex adyacente: un run más largo no es una cita, es otra cosa.
SHA_RE = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{7,40})(?![0-9a-fA-F])")
SUFFIX_RE = re.compile(r"@(ws|bundle|nocommit)\b")
OID_RE = re.compile(r"^[0-9a-f]{40}$")

CAUSE_WS = (
    "hash del workspace de Paperclip: `git am` recrea hashes propios, nunca "
    "fue commit de main (gotcha #9 de la skill paperclip)"
)
CAUSE_BUNDLE = (
    "commit de la historia pre-reescritura: solo resuelve en el bundle "
    "pre-rewrite / en el main anterior al rewrite (tabla de 3 clases, AST-34)"
)

# --------------------------------------------------------------------------
# Declaraciones explícitas: token -> (clase, causa)
# Las 12 + 8 de la tabla de 3 clases de AST-34, verificadas a mano contra el
# repo: las de la clase "workspace" NO son ancestro de `main`; las de "bundle"
# SÍ lo son en la historia pre-reescritura. Los no-commits que en la v1 de
# este gate se clasificaban por patrón (ids de mock y fragmentos de UUID) se
# declaran aquí con causa — la misma decisión, registrada en vez de inferida
# de la forma (nota de la PI: 2 criterios). Y el residual del corpus
# (addendum AST-34): stamps de release pre-rewrite y la fecha compacta del
# nombre del bundle — literales citados donde el sufijo falsearía el texto.
# Verificado con git cat-file en este clon: ninguno de los stamps resuelve ni
# es ancestro de main. El que añada una aquí añade su causa.
# --------------------------------------------------------------------------
CAUSE_MOCK_ID = (
    "id decimal de objeto MagicMock en tabla de salida de test (QA/DEVOPS) — "
    "no es un commit"
)
CAUSE_UUID_FRAG = (
    "fragmento del UUID de una pasada/run de DevOps "
    "(reports/DEVOPS-devops-annex-de57bd59.md) — no es un commit"
)
CAUSE_STAMP = (
    "stamp de release pre-rewrite (≤ v0.8.6): solo visible vía refs del "
    "servidor, gemelo con el mismo mensaje/fecha en la historia nueva "
    "(7ee7b88↔0417e76, addendum AST-34 §Nota API/PyPI) — sin resolución en "
    "clón (git cat-file verificado, AST-35)"
)
CAUSE_DATE_BUNDLE = (
    "fecha compacta AAAAMMDD (2026-10-03, día del rewrite) embebida en el "
    "nombre literal del bundle pre-rewrite — el literal citado no es un "
    "commit (addendum AST-34)"
)

DECLARED_CITATIONS: dict[str, tuple[str, str]] = {
    **{t: ("ws", CAUSE_WS) for t in (
        "2341a78", "28d89e6", "3505b7b", "38f2053", "5537803", "594098d",
        "6541aba", "68cf37a", "a2cb332", "a4f9da1", "edff66d", "f6143f9",
    )},
    **{t: ("bundle", CAUSE_BUNDLE) for t in (
        "768d3ff", "ab6554b", "cf66bec", "4b12ca7", "5fe9c1f", "3a1b9ee",
        "16407a0", "3576cb4",
    )},
    "d284fe7c": ("nocommit",
                 "fragmento de 8 hex del UUID del agente Researcher (AST-9) — "
                 "no es un commit"),
    "de57bd59": ("nocommit",
                 "fragmento del run/anexo de DevOps (reports/DEVOPS-devops-"
                 "annex-de57bd59.md) — no es un commit"),
    "41962dab": ("nocommit",
                 "fragmento del UUID de run de AST-8 — no es un commit"),
    "36f9356fee36": ("nocommit", CAUSE_UUID_FRAG),
    "6666f530b1eb": ("nocommit", CAUSE_UUID_FRAG),
    **{t: ("nocommit", CAUSE_MOCK_ID) for t in (
        "126287905920672", "126287906441936", "126287907513280",
        "128888842159840", "128888842172944", "128888860609904",
        "129919280584016", "138477721213584", "138477721214256",
        "138477722887104",
    )},
    # Residual del corpus de diseño (addendum AST-34, §Nota API/PyPI): stamps
    # de release pre-rewrite y la fecha en el nombre del bundle — literales
    # citados, pre-registrados para que el gate pase cuando el addendum entre
    # en reports/ sin falsear el documento con sufijos.
    **{t: ("bundle", CAUSE_STAMP) for t in (
        "2521890", "91fb426", "64ce5c9", "7ee7b88",
    )},
    "20261003": ("nocommit", CAUSE_DATE_BUNDLE),
}


def label_for(klass: str) -> str:
    return {"ws": "@ws", "bundle": "@bundle", "nocommit": "@nocommit"}.get(klass, klass)


class Report:
    """Espejo del Report del gate del README (AST-33) — misma salida, mismo tono."""

    def __init__(self) -> None:
        self.declared: list[str] = []
        self.resolved: list[str] = []
        self.failures: list[str] = []

    def declare(self, detail: str) -> None:
        self.declared.append(detail)

    def ok(self, detail: str) -> None:
        self.resolved.append(detail)

    def fail(self, detail: str) -> None:
        self.failures.append(detail)

    def summary(self) -> str:
        return (
            f"{len(self.resolved)} citas resuelven sin anotar · "
            f"{len(self.declared)} declaradas (clase/causa) · "
            f"{len(self.failures)} FALLOS"
        )


def resolve_commits(repo: Path, tokens: list[str]) -> tuple[set[str], str | None]:
    """Tokens que son commit/tag en `repo`. Devuelve (resueltos, error_o_None)."""
    if not tokens:
        return set(), None
    payload = "".join(f"{t}^{{commit}}\n" for t in tokens)
    proc = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch-check"],
        input=payload, capture_output=True, text=True,
    )
    if proc.returncode != 0 or "fatal:" in proc.stderr:
        return set(), (proc.stderr.strip() or proc.stdout.strip()
                       or "git cat-file no pudo leer el repo")

    resolved: set[str] = set()
    lines = proc.stdout.splitlines()
    for token, line in zip(tokens, lines):
        parts = line.split()
        if len(parts) >= 2 and OID_RE.match(parts[0]) and parts[1] in {"commit", "tag"}:
            resolved.add(token)

    # Prefijo ambiguo (>=2 objetos con el mismo prefijo): lo desambigua git,
    # no lo decidimos nosotros.
    for token in tokens:
        if token in resolved:
            continue
        dis = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", f"--disambiguate={token}"],
            capture_output=True, text=True,
        )
        for oid in dis.stdout.split():
            chk = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-t", oid],
                capture_output=True, text=True,
            )
            if chk.returncode == 0 and chk.stdout.strip() in {"commit", "tag"}:
                resolved.add(token)
                break
    return resolved, None


def is_shallow(repo: Path) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True,
    )
    return proc.stdout.strip() == "true"


def scan_reports(reports_dir: Path) -> list[tuple[str, int, str, int, str]]:
    """(fichero, línea, token, offset, línea_completa) por cada token con forma de SHA."""
    hits: list[tuple[str, int, str, int, str]] = []
    for path in sorted(reports_dir.glob("*.md")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in SHA_RE.finditer(line):
                hits.append((path.name, lineno, m.group(1), m.start(1), line))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate de citas SHA en reports/ (AST-35)")
    parser.add_argument("--repo", type=Path, default=ROOT,
                        help="repo contra el que se resuelve (por defecto, el del script)")
    parser.add_argument("--reports-dir", type=Path, default=None,
                        help="directorio de reports (por defecto <repo>/reports)")
    args = parser.parse_args(argv)

    repo: Path = args.repo
    reports_dir: Path = args.reports_dir or (repo / "reports")
    if not reports_dir.is_dir():
        print(f"GATE EN ROJO: no existe el directorio de reports: {reports_dir}")
        return 1

    hits = scan_reports(reports_dir)
    md_files = list(reports_dir.glob("*.md"))
    shallow = is_shallow(repo)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip() or "?"

    print(f"== Gate de citas SHA en reports/ (AST-35) — {reports_dir} ==")
    print(f"repo: {repo} · HEAD {head} · somero: {'SÍ' if shallow else 'no'} · "
          f"ficheros: {len(md_files)}")

    report = Report()
    inventory: dict[str, dict[str, set[str]]] = {
        "resuelve": {}, "@ws": {}, "@bundle": {}, "@nocommit": {},
    }
    # Causa por token dentro de la clase cuya causa no la da la clase misma
    # (@nocommit mezcla orígenes distintos).
    causes: dict[str, dict[str, str]] = {"@nocommit": {}}
    pending: dict[str, set[str]] = {}  # token sin declarar -> dónde se cita

    for fname, lineno, token, start, line in hits:
        where = f"{fname}:{lineno}"
        suffix = SUFFIX_RE.match(line, start + len(token))
        if suffix is not None:
            klass = suffix.group(1)
            label = {"ws": "@ws", "bundle": "@bundle", "nocommit": "@nocommit"}[klass]
            report.declare(f"{where} `{token}` → {label} (sufijo en la línea)")
            inventory[label].setdefault(token, set()).add(where)
            causes.setdefault(label, {}).setdefault(token, "sufijo en la línea")
            continue

        if token in DECLARED_CITATIONS:
            klass, cause = DECLARED_CITATIONS[token]
            label = label_for(klass)
            report.declare(f"{where} `{token}` → {label}: {cause}")
            inventory[label].setdefault(token, set()).add(where)
            causes.setdefault(label, {}).setdefault(token, cause)
            continue

        pending.setdefault(token, set()).add(where)

    # Se resuelve SIEMPRE, también sobre los tokens declarados: si git no puede
    # leer el repo, el gate se pone en rojo aunque todo esté anotado (nunca
    # finge verificar) y además deja constancia de qué resuelve aquí.
    all_tokens = sorted({h[2] for h in hits})
    resolved, git_error = resolve_commits(repo, all_tokens)
    if git_error is not None:
        report.fail(f"git no pudo verificar {repo}: {git_error}")
    else:
        print(f"git cat-file: {len(resolved)}/{len(all_tokens)} tokens existen "
              f"como commit en este repo (los declarados no dependen de eso)")

    for token in sorted(pending):
        wheres = sorted(pending[token])
        if token in resolved:
            report.ok(f"`{token}` resuelve — {', '.join(wheres)}")
            inventory["resuelve"][token] = set(wheres)
            continue
        note = (" [repo SOMERO: el objeto puede existir fuera del alcance — "
                "fetch-depth 0, AST-35]") if shallow else ""
        for where in wheres:
            report.fail(
                f"{where} `{token}` — no resuelve en el repo y sin anotar "
                f"(sufija {token}@ws / {token}@bundle / {token}@nocommit, o "
                f"decláralo en DECLARED_CITATIONS con causa){note}"
            )

    print()
    print("[INVENTARIO POR CLASE — tokens, dónde se citan y por qué (nunca un conteo de hex)]")
    marks = {"resuelve": "✔", "@ws": "✋", "@bundle": "✋", "@nocommit": "✋"}
    # La causa de cada clase se imprime una vez; cuando un token tiene una
    # causa propia (distinta de la clase) va además junto al token.
    class_note = {
        "resuelve": "commit real en este repo (git cat-file)",
        "@ws": CAUSE_WS,
        "@bundle": CAUSE_BUNDLE,
        "@nocommit": "el token no identifica ningún commit",
    }
    distinct = 0
    for label in ("resuelve", "@ws", "@bundle", "@nocommit"):
        entries = inventory[label]
        distinct += len(entries)
        note = f" — {class_note[label]}" if entries else ""
        print(f"  {marks[label]} {label}: {len(entries)} tokens{note}")
        per_token = causes.get(label, {})
        for token in sorted(entries):
            cause = per_token.get(token)
            # Causa junto al token cuando NO es la de la clase (orígenes
            # distintos dentro de @nocommit, o un @bundle excepcional como
            # los stamps de release); la causa de la clase ya está arriba.
            extra = f"  · {cause}" if cause and cause != class_note[label] else ""
            print(f"      {token}  →  {', '.join(sorted(entries[token]))}{extra}")
    if not distinct:
        print("  (sin citas con forma de SHA en reports/)")

    print()
    if report.failures:
        print("[FALLOS — citas que no resuelven y no están anotadas]")
        for line in report.failures:
            print(f"  ✘ {line}")
        print()
    print(f"RESULTADO: {report.summary()}")
    if report.failures:
        print("GATE EN ROJO: hay citas SHA que no resuelven y no están anotadas "
              "como workspace/bundle ni declaradas con causa.")
        return 1
    print("GATE EN VERDE: toda cita SHA de reports/ resuelve en el repo o está "
          "anotada (@ws/@bundle/@nocommit, sufijo o DECLARED_CITATIONS con causa).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
