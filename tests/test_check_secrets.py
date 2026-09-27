"""Regression tests for scripts/check_secrets.py itself.

Incidente (2026-09-27, main `60bac33`): la primera CI full-tree en GitHub fue
ROJA por un falso positivo — tests/test_telegram_wiring.py:21 usa el token de
EJEMPLO de la doc oficial de Telegram (público por definición) y el escaneo de
entropía lo marcó. El fix añadió KNOWN_PLACEHOLDER_TOKENS. Estos tests fijan
ambas direcciones para que el caso no vuelva a romper la CI:

1. El placeholder documentado NO se marca (regresión del falso positivo).
2. Los secretos reales SÍ se siguen marcando (el escáner no se debilitó):
   sk-*, entropía alta, y un token casi idéntico al placeholder pero mutado.
3. La invocación exacta de CI (`--all`) pasa sobre el árbol actual.

Los tokens falsos se construyen por concatenación para que el escáner no
marque su propio archivo de tests al escanear el árbol completo.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCANNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_secrets.py"
_spec = importlib.util.spec_from_file_location("check_secrets_under_test", _SCANNER_PATH)
check_secrets = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("check_secrets_under_test", check_secrets)
_spec.loader.exec_module(check_secrets)

# El token de EJEMPLO de la doc oficial de Telegram, verbatim (público).
DOC_PLACEHOLDER = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
# Igual pero con el último carácter mutado: ya NO es el placeholder público;
# un token real con esa pinta debe seguir cazándose.
_MUTATED = "123456:ABC-DEF1234ghIkl-zyx" + "57W2v1u123ew12"
_SK = "sk-" + "AbCdEfGhIjK12345"
_ENTROPY = "qW7xZ2mN9bV4cL8kJ5hG" + "3fD6sA1pO0tR"


class TestPlaceholderNotFlagged:
    def test_telegram_doc_fixture_line_not_flagged(self):
        # Espejo exacto de tests/test_telegram_wiring.py:21 (la línea que rompió la CI).
        line = f'cfg.telegram.bot_token = "{DOC_PLACEHOLDER}"'
        assert not check_secrets.is_suspicious_line(line)

    def test_bare_assignment_not_flagged(self):
        assert not check_secrets.is_suspicious_line(f'token = "{DOC_PLACEHOLDER}"')


class TestRealSecretsStillCaught:
    def test_sk_token_flagged(self):
        assert check_secrets.is_suspicious_line(f'api_key = "{_SK}"')

    def test_high_entropy_random_token_flagged(self):
        assert check_secrets.is_suspicious_line(f'token = "{_ENTROPY}"')

    def test_mutated_placeholder_still_flagged(self):
        # Control negativo del fix: parecido al placeholder, pero NO es el
        # valor público — debe seguir cazándose.
        assert check_secrets.is_suspicious_line(f'token = "{_MUTATED}"')


class TestNonSecretsNotFlagged:
    def test_hex_sha_not_flagged(self):
        assert not check_secrets.is_suspicious_line(
            "commit = a1b2c3d4e5f60718293a4b5c6d7e8f9011223344"
        )

    def test_url_not_flagged(self):
        assert not check_secrets.is_suspicious_line(
            "docs: https://example.com/a/very/long/documentation/url"
        )


class TestCiInvocations:
    def test_full_tree_scan_passes_on_current_repo(self, capsys):
        # Anti-verde-vacuo: `git ls-files` no ve ficheros untracked, así que un
        # escaneo pre-commit no incluye ESTE fichero y el test pasaría sin
        # probar nada (así se coló el verde falso del commit fa9ce29). Exigimos
        # que el test esté trackeado para que el escaneo lo cubra de verdad.
        tracked = {
            str(p.relative_to(check_secrets.ROOT))
            for p in check_secrets.tracked_files()
        }
        assert "tests/test_check_secrets.py" in tracked, (
            "tests/test_check_secrets.py no está trackeado: el escaneo "
            "full-tree no lo incluiría y este test pasaría en vacío"
        )
        # La invocación exacta que fue ROJA en GitHub el 2026-09-27.
        check_secrets.main(["--all"])
        out = capsys.readouterr().out
        assert "secret scan OK (full tree" in out

    def test_staged_mode_exits_nonzero_on_secret(self, monkeypatch, tmp_path):
        leak = tmp_path / "leak.txt"
        leak.write_text(f'api_key = "{_SK}"\n')
        monkeypatch.setattr(check_secrets, "staged_files", lambda: [leak])
        # main() reporta rutas relativas a ROOT; el fixture vive en tmp_path.
        monkeypatch.setattr(check_secrets, "ROOT", tmp_path)
        with pytest.raises(SystemExit, match="leak.txt"):
            check_secrets.main([])
