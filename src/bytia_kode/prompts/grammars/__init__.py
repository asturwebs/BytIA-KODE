"""Packaged GBNF grammars for Structured Chain-of-Thought.

Provides programmatic access to grammar files bundled with bytia_kode.
Grammars are loaded via importlib.resources (same pattern as YAML prompts).

Available grammars:
    think_goal_approach_edge.gbnf  — Compact 3-field plan (GOAL/APPROACH/EDGE)
    think_goal_state_algo_edge_verify.gbnf — Richer 5-field plan for harder tasks
    p22_capability_assessment.gbnf — BytIA P22 self-assessment protocol
    p20_error_propagation.gbnf     — BytIA P20 structured error reporting
"""

from importlib import resources as _resources

_GRAMMAR_PACKAGE = __name__


def get_grammar(name: str = "think_goal_approach_edge.gbnf") -> str:
    """Load a packaged GBNF grammar by filename."""
    try:
        resource = _resources.files(_GRAMMAR_PACKAGE).joinpath(name)
        with resource.open("r", encoding="utf-8") as fh:
            return fh.read().strip()
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise FileNotFoundError(f"Grammar not found: {name}") from exc


def list_grammars() -> list[str]:
    """List available GBNF grammar filenames."""
    try:
        resource = _resources.files(_GRAMMAR_PACKAGE)
        return sorted(
            f.name for f in resource.iterdir() if f.name.endswith(".gbnf")
        )
    except ModuleNotFoundError:
        return []
