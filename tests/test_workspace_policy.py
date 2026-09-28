"""Workspace jail policy (AST-26): confined | permissive | open, conmutable.

Cubre el gate de salida de la issue:
- los 3 modos × (file_read, file_write, bash)
- trusted_paths efectiva (válvula de precisión)
- arranque sin config → permissive
- toggle en sesión
- demo funcional del escenario real tui_32e522c5 (leer ~/bytia desde un
  workspace tipo /tmp): confined bloquea TODO, permissive bloquea file_read
  pero no bash, open deja ambos.

Y el blindaje que la nueva config exige (T4): ~/.bytia-kode/config.yaml se
une al denylist de auto-escritura del agente, y `open` NO levanta ese
denylist — liberar el jail no es liberar la superficie de persistencia
propia del agente.
"""
import asyncio
from pathlib import Path

import pytest

from bytia_kode.tools import registry
from bytia_kode.tools.registry import (
    WORKSPACE_MODES,
    BashTool,
    FileReadTool,
    FileWriteTool,
    _resolve_workspace_path,
    _validate_argv_workspace,
    get_workspace_mode,
    set_trusted_paths,
    set_workspace_mode,
    set_workspace_root,
)


def _read(path, **kwargs):
    return asyncio.run(FileReadTool().execute(path=path, **kwargs))


def _write(path, content="x"):
    return asyncio.run(FileWriteTool().execute(path=path, content=content))


def _bash(command, **kwargs):
    return asyncio.run(BashTool().execute(command=command, **kwargs))


@pytest.fixture(autouse=True)
def _jail(tmp_path, monkeypatch):
    """Isolate the module-level jail: fresh root, no trusted paths, permissive.

    ws/   — the workspace root (where the agent "lives")
    home/ — pinned $HOME (Path.home() follows it; keeps denylist paths hers)
    out/  — outside the jail (created per test as needed)
    """
    saved_paths = list(registry._TRUSTED_PATHS)
    saved_root = registry._WORKSPACE_ROOT
    saved_mode = registry._workspace_mode

    ws = tmp_path / "ws"
    home = tmp_path / "home"
    ws.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    registry._TRUSTED_PATHS.clear()
    set_workspace_root(ws)
    set_workspace_mode("permissive")
    yield {"ws": ws, "home": home, "out": tmp_path / "out"}

    registry._TRUSTED_PATHS.clear()
    registry._TRUSTED_PATHS.extend(saved_paths)
    registry._WORKSPACE_ROOT = saved_root
    registry._workspace_mode = saved_mode


def _outside_target(jail) -> "object":
    """A readable file OUTSIDE the workspace, like ~/bytia in tui_32e522c5."""
    outside = jail["out"]
    outside.mkdir(exist_ok=True)
    target = outside / "notes.md"
    target.write_text("contenido fuera del workspace\n")
    return target


# --- los 3 modos × (file_read, file_write, bash) ---------------------------


class TestFileToolsAcrossModes:
    @pytest.mark.parametrize("mode", ["confined", "permissive"])
    def test_file_read_outside_denied(self, mode, _jail):
        set_workspace_mode(mode)
        target = _outside_target(_jail)
        result = _read(str(target))
        assert result.error
        assert "Security violation" in result.output
        assert f"workspace mode: {mode}" in result.output

    def test_file_read_outside_allowed_in_open(self, _jail):
        set_workspace_mode("open")
        target = _outside_target(_jail)
        result = _read(str(target))
        assert not result.error
        assert "contenido fuera del workspace" in result.output

    @pytest.mark.parametrize("mode", ["confined", "permissive"])
    def test_file_write_outside_denied(self, mode, _jail):
        set_workspace_mode(mode)
        target = _outside_target(_jail)
        result = _write(str(target), "intrusion")
        assert result.error
        assert f"workspace mode: {mode}" in result.output
        assert target.read_text() == "contenido fuera del workspace\n"  # intact

    def test_file_write_outside_allowed_in_open(self, _jail):
        set_workspace_mode("open")
        target = _outside_target(_jail)
        result = _write(str(target), "libre")
        assert not result.error
        assert target.read_text() == "libre"

    @pytest.mark.parametrize("mode", WORKSPACE_MODES)
    def test_file_tools_inside_workspace_always_allowed(self, mode, _jail):
        set_workspace_mode(mode)
        inside = _jail["ws"] / "inside.md"
        result = _write(str(inside), "hola")
        assert not result.error
        result = _read(str(inside))
        assert not result.error
        assert "hola" in result.output


class TestBashAcrossModes:
    def test_confined_blocks_outside_argv_token(self, _jail):
        set_workspace_mode("confined")
        target = _outside_target(_jail)
        result = _bash(f"bat {target}")
        assert result.error
        assert "workspace mode: confined" in result.output
        assert "Blocked bash argument" in result.output

    def test_confined_blocks_tilde_argv_token(self, _jail):
        set_workspace_mode("confined")
        (_jail["home"] / "secret.txt").write_text("s")
        result = _bash("bat ~/secret.txt")
        assert result.error
        assert "workspace mode: confined" in result.output

    def test_confined_blocks_flag_value_form(self, _jail):
        set_workspace_mode("confined")
        target = _outside_target(_jail)
        result = _bash(f"ls --ignore={target}")
        assert result.error
        assert f"--ignore={target}" in result.output

    def test_confined_blocks_escaping_workdir(self, _jail):
        set_workspace_mode("confined")
        outside = _jail["out"]
        outside.mkdir(exist_ok=True)
        result = _bash("ls", workdir=str(outside))
        assert result.error
        assert "escapes the workspace" in result.output

    def test_confined_allows_inside_argv(self, _jail):
        set_workspace_mode("confined")
        inside = _jail["ws"] / "in.txt"
        inside.write_text("x")
        result = _bash(f"ls {inside}")
        assert not result.error

    def test_permissive_bash_reads_outside(self, _jail):
        set_workspace_mode("permissive")
        target = _outside_target(_jail)
        result = _bash(f"ls {target.parent}")
        assert not result.error
        assert "notes.md" in result.output

    def test_open_bash_reads_outside(self, _jail):
        set_workspace_mode("open")
        target = _outside_target(_jail)
        result = _bash(f"ls {target.parent}")
        assert not result.error
        assert "notes.md" in result.output

    def test_confined_env_var_token_is_documented_residual(self, _jail):
        # $VAR tokens travel literally (create_subprocess_exec, sin shell):
        # resuelven relativo al workdir, dentro del jail. Residual declarado
        # de la política de intención — ver _validate_argv_workspace.
        assert _validate_argv_workspace(["bat", "$HOME/secret.md"], ".") is None

    def test_symlink_hop_canonicalized(self, _jail):
        # Path.resolve() canonicaliza symlinks ANTES del chequeo: un link
        # dentro del workspace apuntando fuera no evade el jail.
        set_workspace_mode("confined")
        target = _outside_target(_jail)
        link = _jail["ws"] / "link"
        link.symlink_to(_jail["out"])
        result = _bash(f"bat {link / 'notes.md'}")
        assert result.error
        assert "workspace mode: confined" in result.output


# --- trusted_paths: la válvula de precisión --------------------------------


class TestTrustedPaths:
    def test_confined_file_read_allowed_via_trusted(self, _jail):
        set_workspace_mode("confined")
        target = _outside_target(_jail)
        set_trusted_paths([_jail["out"]])
        result = _read(str(target))
        assert not result.error

    def test_confined_bash_allowed_via_trusted(self, _jail):
        set_workspace_mode("confined")
        _outside_target(_jail)
        set_trusted_paths([_jail["out"]])
        result = _bash(f"ls {_jail['out']}")
        assert not result.error

    def test_trusted_root_itself_is_accessible(self, _jail):
        # El propio directorio declarado (t == resolved), no sólo sus hijos.
        set_workspace_mode("confined")
        _outside_target(_jail)
        set_trusted_paths([_jail["out"]])
        assert _resolve_workspace_path(str(_jail["out"])) == _jail["out"].resolve()

    def test_set_trusted_paths_is_idempotent(self, _jail):
        set_trusted_paths([_jail["out"]])
        set_trusted_paths([_jail["out"]])
        assert len(registry._TRUSTED_PATHS) == 1

    def test_error_message_names_the_exits(self, _jail):
        set_workspace_mode("confined")
        target = _outside_target(_jail)
        result = _read(str(target))
        assert "workspace.trusted_paths" in result.output
        assert "config.yaml" in result.output
        assert "/workspace" in result.output
        assert str(_jail["ws"]) in result.output


# --- toggle en sesión -------------------------------------------------------


class TestModeToggle:
    def test_switch_changes_live_behaviour(self, _jail):
        target = _outside_target(_jail)
        set_workspace_mode("confined")
        assert _bash(f"bat {target}").error

        set_workspace_mode("permissive")  # toggle en sesión, sin reinicio
        assert not _bash(f"ls {target.parent}").error

        set_workspace_mode("open")
        assert not _read(str(target)).error

    def test_unknown_mode_rejected(self):
        with pytest.raises(ValueError, match="Unknown workspace mode"):
            set_workspace_mode("fort-knox")

    def test_get_workspace_mode_roundtrip(self):
        set_workspace_mode("confined")
        assert get_workspace_mode() == "confined"

    def test_state_snapshot_for_prompt_and_tui(self, _jail):
        set_workspace_mode("open")
        state = registry.workspace_policy_state()
        assert state["mode"] == "open"
        assert state["workspace"] == str(_jail["ws"].resolve())
        assert state["trusted"] == []


# --- arranque: config.yaml → jail -------------------------------------------


class TestConfigParsing:
    def _write_config(self, home, text):
        d = home / ".bytia-kode"
        d.mkdir(exist_ok=True)
        (d / "config.yaml").write_text(text)

    def test_no_config_file_means_permissive(self, _jail):
        from bytia_kode.config import load_config

        cfg = load_config()
        assert cfg.workspace.mode == "permissive"
        assert cfg.workspace.trusted_paths == []

    def test_valid_config_parsed(self, _jail):
        from bytia_kode.config import load_config

        self._write_config(
            _jail["home"],
            "workspace:\n  mode: confined\n  trusted_paths:\n    - ~/Projects\n    - /opt/data\n",
        )
        cfg = load_config()
        assert cfg.workspace.mode == "confined"
        assert cfg.workspace.trusted_paths == [
            _jail["home"] / "Projects",
            Path("/opt/data"),
        ]

    def test_unknown_mode_falls_back_to_permissive(self, _jail):
        from bytia_kode.config import load_config

        self._write_config(_jail["home"], "workspace:\n  mode: fortress\n")
        assert load_config().workspace.mode == "permissive"

    def test_malformed_yaml_falls_back(self, _jail):
        from bytia_kode.config import load_config

        self._write_config(_jail["home"], "workspace: [unclosed\n  ::::")
        cfg = load_config()
        assert cfg.workspace.mode == "permissive"
        assert cfg.workspace.trusted_paths == []

    def test_non_mapping_workspace_section_ignored(self, _jail):
        from bytia_kode.config import load_config

        self._write_config(_jail["home"], "workspace: 42\n")
        assert load_config().workspace.mode == "permissive"

    def test_scalar_trusted_path_wrapped(self, _jail):
        from bytia_kode.config import load_config

        self._write_config(
            _jail["home"], "workspace:\n  mode: open\n  trusted_paths: ~/src\n"
        )
        cfg = load_config()
        assert cfg.workspace.mode == "open"
        assert cfg.workspace.trusted_paths == [_jail["home"] / "src"]

    def test_non_string_mode_falls_back_with_warning(self, _jail, caplog):
        # AST-27 foco 1, nota menor: era el único fallback SILENCIOSO de la
        # tabla del revisor — ahora avisa como los demás.
        import logging

        from bytia_kode.config import load_config

        self._write_config(_jail["home"], "workspace:\n  mode: 5\n")
        with caplog.at_level(logging.WARNING, logger="bytia_kode.config"):
            cfg = load_config()
        assert cfg.workspace.mode == "permissive"
        assert "must be a string" in caplog.text


class TestBootWiring:
    def test_agent_boot_applies_config(self, _jail, monkeypatch):
        from bytia_kode.agent import Agent
        from bytia_kode.config import load_config

        d = _jail["home"] / ".bytia-kode"
        d.mkdir(exist_ok=True)
        (d / "config.yaml").write_text(
            "workspace:\n  mode: confined\n  trusted_paths: [~/Projects]\n"
        )
        monkeypatch.chdir(_jail["ws"])
        set_workspace_mode("open")  # si el arranque no cablea, esto seguiría open

        agent = Agent(load_config())

        assert get_workspace_mode() == "confined"
        assert (_jail["home"] / "Projects").resolve() in registry._TRUSTED_PATHS
        assert registry.workspace_policy_state()["workspace"] == str(_jail["ws"].resolve())

    def test_agent_boot_without_config_is_permissive(self, _jail, monkeypatch):
        from bytia_kode.agent import Agent
        from bytia_kode.config import load_config

        monkeypatch.chdir(_jail["ws"])
        set_workspace_mode("open")  # cualquier estado previo se pisa en el arranque

        Agent(load_config())

        assert get_workspace_mode() == "permissive"


# --- T4: config.yaml se une al denylist; `open` no lo levanta ----------------


class TestAgentWriteDenylist:
    @pytest.mark.parametrize("mode", WORKSPACE_MODES)
    def test_config_yaml_agent_write_denied_in_all_modes(self, mode, _jail):
        set_workspace_mode(mode)
        set_trusted_paths([_jail["home"] / ".bytia-kode"])  # como el arranque real
        target = _jail["home"] / ".bytia-kode" / "config.yaml"
        target.parent.mkdir(exist_ok=True)
        result = _write(str(target), "workspace:\n  mode: open\n")
        assert result.error
        assert "cannot write" in result.output
        assert not target.exists()

    def test_open_mode_does_not_lift_env_denylist(self, _jail):
        # `open` libera el jail del workspace, NUNCA la superficie de
        # persistencia propia del agente (AST-15 T4 sigue activo).
        set_workspace_mode("open")
        env = _jail["home"] / ".bytia-kode" / ".env"
        env.parent.mkdir(exist_ok=True)
        result = _write(str(env), "EXTRA_BINARIES=python\n")
        assert result.error
        assert not env.exists()

    def test_config_yaml_read_stays_allowed(self, _jail):
        set_workspace_mode("confined")
        set_trusted_paths([_jail["home"] / ".bytia-kode"])
        target = _jail["home"] / ".bytia-kode" / "config.yaml"
        target.parent.mkdir(exist_ok=True)
        target.write_text("workspace:\n  mode: confined\n")
        result = _read(str(target))
        assert not result.error


# --- AST-27 H1: la denylist T4 también ata el plano bash -------------------


class TestBashPlaneAgentWriteDenylist:
    """H1: `cp payload ~/.bytia-kode/config.yaml` ejecutaba en TODOS los
    modos porque _check_agent_write_allowed sólo vivía en file_write/
    file_edit. Ahora los binarios de familia escritura la consultan SIEMPRE
    (readings con binarios no-escritura quedan intactos).
    """

    def _boot_like_agent(self, jail):
        # como el arranque real: el data dir es trusted, así el jail de
        # confined no puede falsear el veredicto T4 (que es mode-INDEPENDENT)
        set_trusted_paths([jail["home"] / ".bytia-kode"])

    def _config_surface(self, jail, name="config.yaml", content="workspace:\n  mode: confined\n"):
        target = jail["home"] / ".bytia-kode" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    @pytest.mark.parametrize("mode", WORKSPACE_MODES)
    def test_bash_cp_to_config_yaml_denied_in_all_modes(self, mode, _jail):
        set_workspace_mode(mode)
        self._boot_like_agent(_jail)
        cfg = self._config_surface(_jail)
        payload = _jail["ws"] / "payload.yaml"
        payload.write_text("workspace:\n  mode: open\n")
        result = _bash(f"cp {payload} {cfg}")
        assert result.error
        assert "cannot write" in result.output
        assert "Blocked bash argument" in result.output
        assert cfg.read_text() == "workspace:\n  mode: confined\n"  # intacto

    def test_bash_cp_to_env_denied_even_in_open(self, _jail):
        # `open` libera el jail, NUNCA la superficie T4 — tampoco vía bash.
        set_workspace_mode("open")
        self._boot_like_agent(_jail)
        self._config_surface(_jail, name="config.yaml")
        env = self._config_surface(_jail, name=".env", content="EXTRA_BINARIES=python\n")
        payload = _jail["ws"] / "payload.env"
        payload.write_text("EXTRA_BINARIES=python\n")
        result = _bash(f"cp {payload} {env}")
        assert result.error
        assert "cannot write" in result.output
        assert env.read_text() == "EXTRA_BINARIES=python\n"  # intacto

    def test_bash_rm_and_mv_to_config_yaml_denied(self, _jail):
        set_workspace_mode("permissive")  # sin jail: sólo la T4 puede bloquear
        self._boot_like_agent(_jail)
        cfg = self._config_surface(_jail)
        r1 = _bash(f"rm {cfg}")
        assert r1.error and "cannot write" in r1.output
        assert cfg.exists()  # intacto
        r2 = _bash(f"mv {cfg} {_jail['ws'] / 'stolen.yaml'}")
        assert r2.error and "cannot write" in r2.output
        assert cfg.exists()  # mv destruye el origen: también es escritura T4

    def test_bash_glued_flag_to_skills_dir_denied(self, _jail):
        # H2 ∩ H1: valor PEGADO al flag corto apuntando a la superficie T4
        set_workspace_mode("permissive")
        self._boot_like_agent(_jail)
        skills = self._config_surface(_jail, name="skills/x.md", content=" planted\n").parent
        payload = _jail["ws"] / "SKILL.md"
        payload.write_text(" planted\n")
        result = _bash(f"cp -t{skills} {payload}")
        assert result.error
        assert "cannot write" in result.output
        assert "Blocked bash argument: '-t" in result.output
        assert not (skills / "SKILL.md").exists()

    def test_bash_touch_config_yaml_denied(self, _jail):
        set_workspace_mode("permissive")
        self._boot_like_agent(_jail)
        cfg = self._config_surface(_jail)
        result = _bash(f"touch {cfg}")
        assert result.error and "cannot write" in result.output

    def test_write_family_sweep_membership(self, _jail):
        # barrido caso-por-caso de la allowlist (docstring de
        # _is_write_family_command). Los belt-members no-allowlisted
        # (install/tee/ln/sed/truncate) no son testeables end-to-end — la
        # allowlist T1 los rechaza antes — así que se fija el predicado.
        from bytia_kode.tools.registry import _is_write_family_command

        for b in ("cp", "mv", "rm", "touch", "mkdir", "rmdir", "chmod"):
            assert _is_write_family_command(b, [b, "x"]), b
        for b in ("install", "tee", "ln", "sed", "truncate"):  # belt EXTRA_BINARIES
            assert _is_write_family_command(b, [b, "x"]), b
        # find: escritor SÓLO con flags destructivos
        assert _is_write_family_command("find", ["find", ".", "-delete"])
        assert _is_write_family_command("find", ["find", ".", "-fprint", "/x"])
        assert not _is_write_family_command("find", ["find", ".", "-name", "x"])
        # find R3/H4: -fls ESCRIBE el listing en FILE; -ok/-okdir entran por
        # política explícita (hoy los mata el gate de string del ';', pero
        # por accidente de sintaxis de find, no por decisión nuestra)
        assert _is_write_family_command("find", ["find", ".", "-fls", "/x"])
        assert _is_write_family_command("find", ["find", ".", "-ok", "rm", "{}", ";"])
        assert _is_write_family_command("find", ["find", ".", "-okdir", "rm", "{}", ";"])
        # git R3: SÓLO `config -f FILE` es familia (destino por argv);
        # `apply` va por el gate de flags de _validate_argv_safety (H3),
        # no por familia — el resto de subcomandos queda fuera
        assert _is_write_family_command("git", ["git", "config", "-f", "/x/.env", "a.b", "c"])
        assert _is_write_family_command("git", ["git", "config", "--file", "/x", "a.b", "c"])
        assert _is_write_family_command("git", ["git", "-C", "/w", "config", "-f", "/x"])
        assert not _is_write_family_command("git", ["git", "config", "user.name", "x"])
        assert not _is_write_family_command("git", ["git", "apply", "p.diff"])
        # lectores/reporteros y echo (sin shell, `>` es literal): fuera
        for b in ("ls", "head", "tail", "grep", "rg", "bat", "wc", "git",
                  "echo", "date", "df", "du", "pwd", "eza", "tokei", "shellcheck"):
            assert not _is_write_family_command(b, [b, "x"]), b

    def test_bash_find_delete_on_skills_denied(self, _jail):
        # find SÓLO es familia-escritura con flags destructivos; sin ellos,
        # caminar la superficie T4 es lectura legítima
        set_workspace_mode("permissive")
        self._boot_like_agent(_jail)
        skills = self._config_surface(_jail, name="skills/x.md").parent
        result = _bash(f"find {skills} -name x.md -delete")
        assert result.error and "cannot write" in result.output
        assert (skills / "x.md").exists()  # intacto
        walk = _bash(f"find {skills} -name x.md")
        assert not walk.error  # sin flag destructivo: lectura normal
        assert "x.md" in walk.output

    @pytest.mark.parametrize("mode", WORKSPACE_MODES)
    def test_bash_read_of_config_yaml_still_allowed(self, mode, _jail):
        # lecturas de la superficie T4 siguen legítimas en cualquier modo
        set_workspace_mode(mode)
        self._boot_like_agent(_jail)
        cfg = self._config_surface(_jail)
        result = _bash(f"head {cfg}")
        assert not result.error
        assert "mode: confined" in result.output

    def test_bash_write_family_inside_workspace_unaffected(self, _jail):
        set_workspace_mode("confined")
        src = _jail["ws"] / "a.txt"
        src.write_text("hola\n")
        result = _bash(f"cp {src} {_jail['ws'] / 'b.txt'}")
        assert not result.error
        assert (_jail["ws"] / "b.txt").read_text() == "hola\n"

    def test_bash_cp_to_ordinary_data_path_allowed(self, _jail):
        # la T4 es denylist, no manta sobre ~/.bytia-kode: una ruta de datos
        # ordinaria (no denylisted) sigue siendo escribible por bash
        set_workspace_mode("permissive")
        self._boot_like_agent(_jail)
        cfg_dir = _jail["home"] / ".bytia-kode"
        cfg_dir.mkdir(exist_ok=True)
        src = _jail["ws"] / "note.txt"
        src.write_text("sesion\n")
        target = cfg_dir / "session-note.txt"
        result = _bash(f"cp {src} {target}")
        assert not result.error
        assert target.read_text() == "sesion\n"


# --- AST-27 H2: valores PEGADOS a flags cortos no escapan al jail ----------


class TestGluedShortFlagValues:
    """H2: `cp -tDIR src` / `touch -rFILE dst` ejecutaban FUERA del jail en
    confined porque el validador saltaba todo token con '-' salvo --flag=.
    Ahora el valor pegado se extrae y pasa por el mismo resolver.
    """

    def _src(self, _jail, name="secret.md", content="secreto\n"):
        src = _jail["ws"] / name
        src.write_text(content)
        return src

    def test_confined_blocks_glued_cp_target_directory(self, _jail):
        set_workspace_mode("confined")
        outside = _jail["out"]
        outside.mkdir(exist_ok=True)
        src = self._src(_jail)
        result = _bash(f"cp -t{outside} {src}")
        assert result.error
        assert "workspace mode: confined" in result.output
        assert "Blocked bash argument: '-t" in result.output
        assert not (outside / "secret.md").exists()  # nada salió del jail

    def test_confined_blocks_glued_touch_reference(self, _jail):
        set_workspace_mode("confined")
        outside = _jail["out"]
        outside.mkdir(exist_ok=True)
        ref = outside / "notes.md"
        ref.write_text("fuera\n")
        dst = _jail["ws"] / "dst.md"
        result = _bash(f"touch -r{ref} {dst}")
        assert result.error
        assert "workspace mode: confined" in result.output
        assert not dst.exists()

    def test_separated_flag_value_still_blocked_control(self, _jail):
        # control B2 del revisor: la forma separada ya se bloqueaba
        set_workspace_mode("confined")
        outside = _jail["out"]
        outside.mkdir(exist_ok=True)
        src = self._src(_jail)
        result = _bash(f"cp -t {outside} {src}")
        assert result.error
        assert not (outside / "secret.md").exists()

    def test_glued_flag_with_inside_value_allowed(self, _jail):
        # sin falso positivo: valor pegado DENTRO del jail ejecuta normal
        set_workspace_mode("confined")
        out_dir = _jail["ws"] / "out"
        out_dir.mkdir()
        src = self._src(_jail, name="a.txt", content="hola\n")
        result = _bash(f"cp -t{out_dir} {src}")
        assert not result.error
        assert (out_dir / "a.txt").read_text() == "hola\n"

    def test_glued_relative_dotted_value_extracted(self, _jail):
        # `-t./sub` extrae `./sub` (no `/sub`): relativo al workdir efectivo
        set_workspace_mode("confined")
        sub = _jail["ws"] / "sub"
        sub.mkdir()
        src = self._src(_jail, name="a.txt", content="hola\n")
        result = _bash(f"cp -t./sub {src}")
        assert not result.error
        assert (sub / "a.txt").read_text() == "hola\n"


# --- AST-27 R3/H3: el path puede viajar en el CONTENIDO del parche ---------


class TestGitApplyPatchContentEscape:
    """H3 (alta): `git apply -p0 --unsafe-paths` plantaba `mode: open` en
    ~/.bytia-kode/config.yaml en TODOS los modos — ningún token de argv es
    path-like, así que ni el jail confined ni la T4 del plano bash tenían
    nada que inspeccionar: el destino viaja en el CONTENIDO del parche.
    Ahora _validate_argv_safety rechaza los flags --unsafe* de git apply.
    Semántica 2×2 (verificada en shell plano): `-p0` solo → git mismo
    rechaza '../'; `--unsafe-paths` solo → el strip -p1 por defecto desarma
    la ruta; el escape necesita AMBOS — matar el habilitador basta, y `-p0`
    queda permitido (es la forma normal de aplicar `diff -u` plano).
    """

    def _boot_like_agent(self, jail):
        set_trusted_paths([jail["home"] / ".bytia-kode"])  # como el arranque real

    def _config_surface(
        self, jail, name="config.yaml", content="workspace:\n  mode: confined\n"
    ):
        target = jail["home"] / ".bytia-kode" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return target

    def _escape_patch(self, jail):
        # unified diff cuyos headers apuntan FUERA vía ../ (PoC del revisor):
        # file_write del parche es legítimo (dentro del ws, no denegado)
        cfg = self._config_surface(jail)
        rel = "../home/.bytia-kode/config.yaml"
        patch = jail["ws"] / "p.diff"
        patch.write_text(
            f"--- {rel}\n+++ {rel}\n@@ -1,2 +1,2 @@\n workspace:\n"
            "-  mode: confined\n+  mode: open\n"
        )
        return cfg, patch

    @pytest.mark.parametrize("mode", WORKSPACE_MODES)
    def test_git_apply_unsafe_paths_denied_in_all_modes(self, mode, _jail):
        set_workspace_mode(mode)
        self._boot_like_agent(_jail)
        cfg, _patch = self._escape_patch(_jail)
        result = _bash("git apply -p0 --unsafe-paths p.diff", workdir=str(_jail["ws"]))
        assert result.error
        assert "git apply" in result.output
        assert "--unsafe" in result.output
        assert cfg.read_text() == "workspace:\n  mode: confined\n"  # intacta

    def test_git_apply_unsafe_abbreviation_denied(self, _jail):
        # git acepta prefijos únicos de opciones largas: `--unsafe` cuenta
        # como --unsafe-paths (verificado); el gate cubre el prefijo
        set_workspace_mode("permissive")
        self._boot_like_agent(_jail)
        cfg, _patch = self._escape_patch(_jail)
        result = _bash("git apply -p0 --unsafe p.diff", workdir=str(_jail["ws"]))
        assert result.error and "--unsafe" in result.output
        assert cfg.read_text() == "workspace:\n  mode: confined\n"

    def test_git_apply_plain_patch_inside_workspace_allowed(self, _jail):
        # sin falso positivo: parche normal (destino relativo dentro del ws,
        # sin --unsafe) aplica igual que antes, confined incluido
        set_workspace_mode("confined")
        patch = _jail["ws"] / "create.diff"
        patch.write_text("--- /dev/null\n+++ notes.md\n@@ -0,0 +1 @@\n+hola\n")
        result = _bash("git apply -p0 create.diff", workdir=str(_jail["ws"]))
        assert not result.error
        assert (_jail["ws"] / "notes.md").read_text() == "hola\n"


# --- AST-27 R3/H4: `-fls` falta en _FIND_WRITE_FLAGS -----------------------


class TestFindFlsWritesDeniedPath:
    """H4: `find <ws> -fls ~/.bytia-kode/mcp_servers.json` ejecutaba y
    ESCRIBÍA el listing dentro del path denegado (corrupción de la
    superficie T4 — JSON roto → parse falla → cae cerrado — no escalación,
    pero rompe la invariante "T4 activo en TODOS los modos"). `-fls` se une
    a _FIND_WRITE_FLAGS; `-ok`/`-okdir` también (por política, no por
    accidente de sintaxis del ';' — ver el barrido del predicado).
    """

    def test_bash_find_fls_on_denied_path_denied(self, _jail):
        set_workspace_mode("permissive")  # sin jail: sólo la T4 puede bloquear
        set_trusted_paths([_jail["home"] / ".bytia-kode"])  # como el arranque real
        target = _jail["home"] / ".bytia-kode" / "mcp_servers.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        src = _jail["ws"] / "a.txt"
        src.write_text("x\n")
        result = _bash(f"find {_jail['ws']} -fls {target}")
        assert result.error and "cannot write" in result.output
        assert not target.exists()  # nada se plantó

    def test_bash_find_fls_inside_workspace_allowed(self, _jail):
        # control: el listing a un fichero ordinario dentro del ws sigue ok
        set_workspace_mode("confined")
        listing = _jail["ws"] / "listing.txt"
        src = _jail["ws"] / "a.txt"
        src.write_text("x\n")
        result = _bash(f"find {_jail['ws']} -fls {listing}")
        assert not result.error
        assert listing.exists()


# --- AST-27 R3/nota: `git config -f` escribe FILE por argv ------------------


class TestGitConfigFileFlag:
    """Nota (baja) del veredicto R3, cerrada de paso: `git config -f FILE`
    sobre un denegado AUSENTE lo crea en INI y dotenv tolera la línea de
    sección (verificado: planta saltándose `[agent]`). El único freno era la
    gramática de claves de git (defensa prestada), no nuestra política.
    Ahora `git config` con -f/--file es familia-escritura: el destino viaja
    en argv y enfrenta la denylist T4 en todos los modos.
    """

    def test_git_config_f_env_denied_even_in_open(self, _jail):
        set_workspace_mode("open")
        set_trusted_paths([_jail["home"] / ".bytia-kode"])  # como el arranque real
        env = _jail["home"] / ".bytia-kode" / ".env"
        env.parent.mkdir(parents=True, exist_ok=True)
        result = _bash(f"git config -f {env} agent.planted yes")
        assert result.error and "cannot write" in result.output
        assert not env.exists()

    def test_git_config_f_ordinary_file_allowed(self, _jail):
        # control: fichero ordinario dentro del ws sigue ejecutando
        set_workspace_mode("confined")
        ini = _jail["ws"] / "local.ini"
        result = _bash(
            f"git config -f {ini} user.email x@y", workdir=str(_jail["ws"])
        )
        assert not result.error
        assert ini.exists()


# --- demo funcional: escenario real tui_32e522c5 ----------------------------


class TestDemoTui32e522c5:
    """Sesión real: workspace en /tmp, objetivo ~/bytia.

    confined bloquea TODO; permissive bloquea file_read pero no bash;
    open deja ambos. Este es el matrix exacto que pedía el gate.
    """

    def _scenario(self, _jail):
        bytia = _jail["home"] / "bytia"
        bytia.mkdir(exist_ok=True)
        notes = bytia / "daily.md"
        notes.write_text("bitácora de bytia\n")
        return notes

    def test_confined_blocks_everything(self, _jail):
        notes = self._scenario(_jail)
        set_workspace_mode("confined")
        read = _read(str(notes))
        bash = _bash(f"bat {notes}")
        assert read.error and bash.error
        assert "workspace mode: confined" in read.output
        assert "workspace mode: confined" in bash.output

    def test_permissive_blocks_file_read_not_bash(self, _jail):
        notes = self._scenario(_jail)
        set_workspace_mode("permissive")
        read = _read(str(notes))
        bash = _bash(f"ls {notes.parent}")
        assert read.error  # file tools jailed…
        assert "workspace mode: permissive" in read.output
        assert not bash.error  # …bash libre: la asimetría de tui_32e522c5
        assert "daily.md" in bash.output

    def test_open_allows_both(self, _jail):
        notes = self._scenario(_jail)
        set_workspace_mode("open")
        read = _read(str(notes))
        bash = _bash(f"ls {notes.parent}")
        assert not read.error
        assert "bitácora de bytia" in read.output
        assert not bash.error


# --- TUI: /workspace, Ctrl+P, barra de estado -------------------------------


class _FakeAgent:
    """Agent de mentira (patrón de test_tui_interruption): sin providers."""

    def __init__(self):
        self.config = None
        self.on_tool_call = []
        self.on_tool_done = []
        self.on_subprocess = []
        self._bkode_path = None
        self.providers = None  # los workers de arranque prueban providers y fallan blandos

    def set_session(self, source="tui", source_ref=""):
        return "test_session"


class TestWorkspaceTUI:
    @pytest.mark.asyncio
    async def test_status_bar_shows_mode_on_boot(self, _jail):
        from bytia_kode.tui import ActivityIndicator, BytIAKODEApp

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            await pilot.pause()
            bar = app.query_one(ActivityIndicator)
            assert "ws:permissive" in str(bar.content)

    @pytest.mark.asyncio
    async def test_workspace_command_shows_policy(self, _jail):
        from bytia_kode.tui import BytIAKODEApp, ChatMessage

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            app._handle_command("/workspace")
            await pilot.pause()
            texts = [
                m.msg_content for m in app.query(ChatMessage) if m.role == "system"
            ]
            assert any("/workspace <confined|permissive|open>" in t for t in texts)
            assert any("config.yaml" in t for t in texts)

    @pytest.mark.asyncio
    async def test_workspace_toggle_requires_confirmation(self, _jail):
        from bytia_kode.tui import BytIAKODEApp, ConfirmScreen

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            app._handle_command("/workspace confined")
            await pilot.pause()
            # Sin confirmar: el modo NO cambia todavía
            assert isinstance(app.screen, ConfirmScreen)
            assert get_workspace_mode() == "permissive"

            await pilot.press("y")
            await pilot.pause()
            assert get_workspace_mode() == "confined"
            assert "ws:confined" in str(app.query_one("#activity-indicator").content)

    @pytest.mark.asyncio
    async def test_workspace_toggle_cancel_keeps_mode(self, _jail):
        from bytia_kode.tui import BytIAKODEApp

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            app._handle_command("/workspace open")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert get_workspace_mode() == "permissive"

    @pytest.mark.asyncio
    async def test_ctrlp_entry_cycles_with_confirmation(self, _jail):
        from bytia_kode.tui import BytIAKODEApp

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            # permissive → open → confined → permissive (ciclo de la issue)
            app.action_cycle_workspace_mode()
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert get_workspace_mode() == "open"

            app.action_cycle_workspace_mode()
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert get_workspace_mode() == "confined"

    @pytest.mark.asyncio
    async def test_unknown_mode_argument_rejected(self, _jail):
        from bytia_kode.tui import BytIAKODEApp

        app = BytIAKODEApp(agent=_FakeAgent())
        async with app.run_test() as pilot:
            app._handle_command("/workspace fortress")
            await pilot.pause()
            assert get_workspace_mode() == "permissive"
