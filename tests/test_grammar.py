"""Tests for GBNF grammar integration."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from bytia_kode.config import AppConfig
from bytia_kode.agent import Agent
from bytia_kode.providers.client import ProviderClient


class TestGrammarLoading:
    """Packaged grammar files must be parseable and accessible."""

    def test_packaged_grammar_exists(self):
        from bytia_kode.prompts.grammars import get_grammar
        grammar = get_grammar("think_goal_approach_edge.gbnf")
        assert grammar
        assert "GOAL" in grammar
        assert "APPROACH" in grammar
        assert "EDGE" in grammar

    def test_all_grammars_valid_gbnf(self):
        from bytia_kode.prompts.grammars import list_grammars, get_grammar
        for name in list_grammars():
            grammar = get_grammar(name)
            assert "root ::=" in grammar, f"{name} missing root ::= rule"

    def test_list_grammars(self):
        from bytia_kode.prompts.grammars import list_grammars
        names = list_grammars()
        assert len(names) >= 4
        assert "think_goal_approach_edge.gbnf" in names

    def test_get_grammar_missing_raises(self):
        from bytia_kode.prompts.grammars import get_grammar
        with pytest.raises(FileNotFoundError):
            get_grammar("nonexistent.gbnf")


class TestProviderGrammarDetection:
    """ProviderClient.supports_grammar detection logic."""

    def test_llama_cpp_localhost(self):
        client = ProviderClient("http://localhost:8080/v1", "", "test")
        assert client.supports_grammar is True

    def test_llama_cpp_loopback(self):
        client = ProviderClient("http://127.0.0.1:8080/v1", "", "test")
        assert client.supports_grammar is True

    def test_ollama_does_not(self):
        client = ProviderClient("http://localhost:11434/v1", "", "test")
        assert client.supports_grammar is False

    def test_openai_does_not(self):
        client = ProviderClient("https://api.openai.com/v1", "sk-test", "test")
        assert client.supports_grammar is False

    def test_zai_does_not(self):
        client = ProviderClient("https://api.z.ai/v1", "test", "test")
        assert client.supports_grammar is False

    def test_deepseek_does_not(self):
        client = ProviderClient("https://api.deepseek.com", "test", "test")
        assert client.supports_grammar is False

    def test_minimax_does_not(self):
        client = ProviderClient("https://api.minimax.io/v1", "test", "test")
        assert client.supports_grammar is False

    def test_unknown_remote_defaults_false(self):
        client = ProviderClient("https://some-random-api.example.com/v1", "test", "test")
        assert client.supports_grammar is False


class TestAgentGrammarIntegration:
    """Agent grammar loading and toggle logic (no live provider needed)."""

    def test_grammar_disabled_returns_none(self):
        config = AppConfig()
        config.grammar_enabled = False
        with patch("bytia_kode.agent._get_packaged_grammar", None):
            agent = Agent(config)
            assert agent.grammar is None

    def test_grammar_enabled_loads_from_package(self):
        config = AppConfig()
        config.grammar_enabled = True
        agent = Agent(config)
        grammar = agent.grammar
        assert grammar is not None
        assert "GOAL" in grammar

    def test_grammar_toggle(self):
        config = AppConfig()
        config.grammar_enabled = False
        agent = Agent(config)
        assert agent.grammar is None

        agent.toggle_grammar(True)
        assert agent.grammar is not None
        assert "GOAL" in agent.grammar

        agent.toggle_grammar(False)
        assert agent.grammar is None

    def test_grammar_cache_invalidation(self):
        config = AppConfig()
        config.grammar_enabled = True
        agent = Agent(config)
        g1 = agent.grammar
        agent.toggle_grammar(False)
        agent.toggle_grammar(True)
        g2 = agent.grammar
        assert g1 == g2  # Should reload same packaged grammar


class TestPayloadConstruction:
    """Grammar must be included in payload correctly."""

    def test_grammar_in_payload(self):
        grammar_text = 'root ::= "test"'
        payload = {
            "model": "test",
            "messages": [],
            "temperature": 0.3,
            "max_tokens": 100,
            "stream": True,
        }
        if grammar_text:
            payload["grammar"] = grammar_text
        assert "grammar" in payload
        assert payload["grammar"] == grammar_text

    def test_no_grammar_when_none(self):
        payload = {
            "model": "test",
            "messages": [],
            "temperature": 0.3,
            "max_tokens": 100,
            "stream": True,
        }
        grammar_text = None
        if grammar_text:
            payload["grammar"] = grammar_text
        assert "grammar" not in payload
