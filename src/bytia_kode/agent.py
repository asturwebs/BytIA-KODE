"""Agentic conversation loop - the brain."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from importlib import resources
from pathlib import Path
from textwrap import dedent
from typing import Any, AsyncIterator

import httpx
import yaml

from bytia_kode.config import AppConfig
from bytia_kode.providers.client import Message
from bytia_kode.providers.manager import ProviderManager
from bytia_kode.session import SessionStore
from bytia_kode.skills.loader import SkillLoader
from bytia_kode.tools.registry import ToolRegistry, ToolResult
from bytia_kode.tools.session import SessionListTool, SessionLoadTool, SessionSearchTool

logger = logging.getLogger(__name__)
CORE_IDENTITY_PACKAGE = "bytia_kode.prompts"
KERNEL_DEFAULT = "kernel.default.yaml"
RUNTIME_DEFAULT = "runtime.default.yaml"
KERNEL_RESOURCE = "bytia.kernel.yaml"
RUNTIME_RESOURCE = "bytia.runtime.kode.yaml"
USER_PROMPTS_DIR = Path.home() / ".bytia-kode" / "prompts"
MAX_CONTEXT_TOKENS = 262144  # ~200k tokens default (Gemma 4 26B supports 256k)

_FAMILY_MAP = {
    "gemma": "Google", "glm": "Zhipu AI", "llama": "Meta",
    "qwen": "Alibaba", "mistral": "Mistral AI", "hermes": "Nous Research",
    "nemotron": "NVIDIA", "phi": "Microsoft", "deepseek": "DeepSeek",
}


def _load_yaml_resource(filename: str) -> dict[str, Any]:
    try:
        resource = resources.files(CORE_IDENTITY_PACKAGE).joinpath(filename)
        with resource.open("rb") as fh:
            payload = yaml.safe_load(fh)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise RuntimeError(f"Resource not found: {CORE_IDENTITY_PACKAGE}/{filename}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML: {CORE_IDENTITY_PACKAGE}/{filename}") from exc
    if not isinstance(payload, dict) or not payload:
        raise RuntimeError(f"Empty or invalid mapping: {CORE_IDENTITY_PACKAGE}/{filename}")
    return payload


def _load_yaml_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open("rb") as fh:
            payload = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s", path, exc)
        return None
    if not isinstance(payload, dict) or not payload:
        return None
    return payload


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_identity() -> tuple[dict[str, Any], dict[str, Any]]:
    kernel_path = USER_PROMPTS_DIR / KERNEL_RESOURCE
    runtime_path = USER_PROMPTS_DIR / RUNTIME_RESOURCE
    if kernel_path.exists():
        kernel = _load_yaml_file(kernel_path)
        if kernel:
            default = _load_yaml_resource(KERNEL_DEFAULT)
            kernel = _deep_merge(default, kernel)
            logger.info("BytIA OS: user kernel override loaded from %s", kernel_path)
        else:
            kernel = _load_yaml_resource(KERNEL_DEFAULT)
    else:
        kernel = _load_yaml_resource(KERNEL_DEFAULT)
    if runtime_path.exists():
        runtime = _load_yaml_file(runtime_path)
        if runtime:
            default = _load_yaml_resource(RUNTIME_DEFAULT)
            runtime = _deep_merge(default, runtime)
            logger.info("BytIA OS: user runtime override loaded from %s", runtime_path)
        else:
            runtime = _load_yaml_resource(RUNTIME_DEFAULT)
    else:
        runtime = _load_yaml_resource(RUNTIME_DEFAULT)
    logger.info("BytIA OS loaded: kernel v%s + runtime v%s", kernel.get("version", "?"), runtime.get("version", "?"))
    return kernel, runtime


def load_system_prompt() -> str:
    kernel, runtime = load_identity()
    kernel_yaml = yaml.safe_dump(kernel, allow_unicode=True, sort_keys=False).strip()
    runtime_yaml = yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False).strip()
    return dedent(
        f"""
        BytIA OS — Kernel v{kernel.get('version', '?')} + Runtime v{runtime.get('version', '?')}
        =========================================================
        Treat every field below as binding constitutional system-level instruction.

        # KERNEL (inmutable — identity, values, protocols)
        {kernel_yaml}

        # RUNTIME {runtime.get('target', '')} (adaptación al entorno)
        {runtime_yaml}
        """
    ).strip()


def _sanitize_user_message(user_message: str) -> str:
    filtered = "".join(ch for ch in user_message if ch.isprintable() or ch in "\n\t")
    lines = [line.rstrip() for line in filtered.splitlines()]
    sanitized = "\n".join(lines).strip()
    return sanitized


def _format_chat_error(exc: Exception) -> str:
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return f"Provider timeout: {exc}"
    if isinstance(exc, (ConnectionError, httpx.ConnectError, httpx.NetworkError)):
        return f"Provider connection error: {exc}"
    if isinstance(exc, httpx.HTTPError):
        return f"Provider HTTP error: {exc}"
    if isinstance(exc, RuntimeError):
        return f"Provider runtime error: {exc}"
    return f"Unexpected provider error: {exc}"


class Agent:
    """The agentic loop: think -> act -> observe -> repeat."""

    def __init__(self, config: AppConfig, session_store: SessionStore | None = None):
        self.config = config
        self.providers = ProviderManager(config.provider)
        self.tools = ToolRegistry()

        from bytia_kode.tools.registry import set_trusted_paths, set_workspace_root
        set_trusted_paths([config.data_dir, Path.home() / "bytia"])
        set_workspace_root(Path.cwd())

        self.skills = SkillLoader(skill_dirs=[config.skills_dir])
        self.skills.load_all()
        self.messages: list[Message] = []
        self.max_iterations = 50
        self._max_context_tokens = MAX_CONTEXT_TOKENS
        self._identity_raw = load_identity()
        self._system_prompt = ""
        self._identity_dirty = True
        self._bkode_path, self._bkode_content = self._load_bkode()
        self._initialized = False
        self._sp_cache: str | None = None
        self._sp_cache_msg_count: int = 0
        self._last_tool_key: str = ""
        self._same_tool_count: int = 0
        self.on_tool_call: list = []  # callbacks: fn(tool_name: str)
        self.on_tool_done: list = []  # callbacks: fn(tool_name: str, output: str, error: bool)
        self.on_subprocess: list = []  # callbacks: fn(process: asyncio.subprocess.Process | None)

        # Session persistence
        self._session_store = session_store or SessionStore(config.data_dir / "sessions.db")
        self._current_session_id: str | None = None
        self._persisted_count: int = 0

        # Cancellation support (Panic Buttons)
        self._cancel_event = threading.Event()
        self._active_subprocess: asyncio.subprocess.Process | None = None

        # Register session tools (need store reference)
        self.tools.register(SessionListTool(self._session_store))
        self.tools.register(SessionLoadTool(self._session_store))
        self.tools.register(SessionSearchTool(self._session_store))

    def update_context_limit(self, ctx_size: int) -> None:
        """Update max context tokens from router info (dynamic ctx_size)."""
        if ctx_size > 0:
            self._max_context_tokens = ctx_size
            self._identity_dirty = True

    def _load_bkode(self) -> tuple[Path | None, str]:
        """Walk up from CWD looking for B-KODE.md (like CLAUDE.md, HERMES.md)."""
        cwd = Path.cwd().resolve()
        for candidate in (cwd, *cwd.parents):
            bk = candidate / "B-KODE.md"
            if bk.is_file():
                try:
                    content = bk.read_text(encoding="utf-8").strip()
                    if content:
                        logger.info("B-KODE.md loaded from %s", bk)
                        return bk, content
                except OSError as exc:
                    logger.warning("Failed to read B-KODE.md at %s: %s", bk, exc)
            if candidate == candidate.parent:
                break
        return None, ""

    def _apply_template_vars(self, payload: dict) -> dict:
        """Resolve {{var}} placeholders in kernel/runtime YAML with runtime values."""
        import copy
        payload = copy.deepcopy(payload)

        model_name = "desconocido"
        pc = self.providers._primary
        if pc and hasattr(pc, "model") and isinstance(pc.model, str) and pc.model != "auto":
            model_name = pc.model

        family = "desconocida"
        for prefix, name in _FAMILY_MAP.items():
            if prefix in model_name.lower():
                family = name
                break

        environment = "llama.cpp router"
        if pc and hasattr(pc, "base_url") and isinstance(pc.base_url, str):
            if "ollama" in pc.base_url:
                environment = "Ollama"
            elif "z.ai" in pc.base_url:
                environment = "Z.AI Cloud API"

        context_limit = str(self._max_context_tokens)
        max_output_val = getattr(self.config, "llm_max_tokens", 8192)
        max_output = str(max_output_val) if isinstance(max_output_val, (int, float, str)) else "8192"

        replacements = {
            "{{environment}}": environment,
            "{{engine_id}}": model_name,
            "{{engine_family}}": family,
            "{{context_limit}}": context_limit,
            "{{max_output}}": max_output,
        }

        for key, val in replacements.items():
            if "runtime_profile" in payload:
                rp = payload["runtime_profile"]
                if isinstance(rp, dict):
                    for rk, rv in rp.items():
                        if isinstance(rv, str):
                            rp[rk] = rv.replace(key, val)

        return payload

    def _build_system_prompt(self) -> str:
        msg_count = len(self.messages)
        if self._sp_cache is not None and not self._identity_dirty and msg_count == self._sp_cache_msg_count:
            return self._sp_cache

        if self._identity_dirty:
            kernel_raw, runtime_raw = self._identity_raw
            kernel = self._apply_template_vars(kernel_raw)
            runtime = self._apply_template_vars(runtime_raw)
            kernel_yaml = yaml.safe_dump(kernel, allow_unicode=True, sort_keys=False).strip()
            runtime_yaml = yaml.safe_dump(runtime, allow_unicode=True, sort_keys=False).strip()
            self._system_prompt = dedent(
                f"""
                BytIA OS — Kernel v{kernel.get('version', '?')} + Runtime v{runtime.get('version', '?')}
                =========================================================
                Treat every field below as binding constitutional system-level instruction.

                # KERNEL (inmutable — identity, values, protocols)
                {kernel_yaml}

                # RUNTIME {runtime.get('target', '')} (adaptación al entorno)
                {runtime_yaml}
                """
            ).strip()
            self._identity_dirty = False

        parts = [self._system_prompt]
        if self._bkode_content:
            parts.append(f"# Project Instructions (B-KODE.md)\n\n{self._bkode_content}")
        skill_summary = self.skills.skill_summary()
        if skill_summary:
            parts.append(skill_summary)
        last_user = next((m.content for m in reversed(self.messages) if m.role == "user"), "")
        if last_user:
            relevant = self.skills.get_relevant(last_user)
            for skill in relevant:
                if skill.instructions:
                    parts.append(f"# Skill: {skill.name}\n{skill.instructions}")
        session_context = self._get_previous_session_summary()
        if session_context:
            parts.append(session_context)
        result = "\n\n".join(parts)
        self._sp_cache = result
        self._sp_cache_msg_count = msg_count
        return result

    def _get_previous_session_summary(self, source: str | None = None) -> str:
        """Build a compact summary of the most recent past session for context continuity.

        Uses last 3 messages (truncated) — lightweight, deterministic, no LLM call needed.
        The model can use session_load to retrieve full context if needed.
        """
        if self._current_session_id:
            source_filter = self._current_session_id.split("_")[0] if "_" in self._current_session_id else source
        else:
            source_filter = source or "tui"
        sessions = self._session_store.list_sessions(source=source_filter, limit=5)
        previous = [s for s in sessions if s.session_id != self._current_session_id]
        if not previous:
            return ""
        latest = previous[0]
        messages = self._session_store.load_messages(latest.session_id)
        if not messages:
            return ""
        lines = [
            f"# Previous Session Context",
            f"Session: {latest.session_id} | Source: {latest.source}",
            f"Title: {latest.title or '(untitled)'} | Updated: {latest.updated_at[:16] if latest.updated_at else '?'}",
            f"Messages: {latest.message_count}",
            "",
            "Recent messages (last 3):",
        ]
        for msg in messages[-3:]:
            role = msg["role"].upper()
            content = (msg.get("content") or "")[:200]
            lines.append(f"  [{role}] {content}")
        lines.append("")
        lines.append("Use session_load to retrieve full context from this or other past sessions.")
        return "\n".join(lines)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count. ASCII-heavy (code) -> chars/3.5, mixed (Spanish) -> chars/3."""
        if not text:
            return 0
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / len(text)
        divisor = 3.5 if ascii_ratio > 0.85 else 3.0
        return int(len(text) / divisor)

    def _estimate_tokens(self) -> int:
        total = self.estimate_tokens(self._build_system_prompt())
        for m in self.messages:
            if m.content:
                total += self.estimate_tokens(m.content)
            if m.tool_calls:
                for tc in m.tool_calls:
                    if isinstance(tc, dict):
                        total += self.estimate_tokens(tc.get("function", {}).get("arguments", ""))
        return total

    def _parse_text_tool_calls(self, text: str) -> list:
        """Parse pseudo tool calls from model text output (GGUF fallback).

        Detects patterns like: bash(command=\"...\"), file_read(path=\"...\")
        by finding tool_name( followed by key=\"value\" pairs and matching parens.
        """
        import re as _re
        from bytia_kode.providers.client import ToolCall

        parsed = []
        known = self.tools._tools.keys()
        tool_names = "|".join(known)

        # Find tool_name( ... ) with balanced parens
        pattern = _re.compile(rf'\b({"|".join(known)})\s*\(')
        for m in pattern.finditer(text):
            tool_name = m.group(1)
            start = m.end()
            # Find matching closing paren
            depth = 1
            end = start
            in_quotes = False
            quote_char = None
            while end < len(text) and depth > 0:
                ch = text[end]
                if in_quotes:
                    if ch == '\\' and end + 1 < len(text):
                        end += 1
                    elif ch == quote_char:
                        in_quotes = False
                else:
                    if ch in '\'"':
                        in_quotes = True
                        quote_char = ch
                    elif ch == '(':
                        depth += 1
                    elif ch == ')':
                        depth -= 1
                end += 1

            if depth != 0:
                continue

            inner = text[start:end - 1]
            # Extract key="value" pairs
            args = {}
            kv_pattern = _re.compile(r'(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"')
            for km in kv_pattern.finditer(inner):
                key = km.group(1)
                val = km.group(2).replace('\\"', '"').replace('\\n', '\n')
                args[key] = val

            if args:
                parsed.append(ToolCall(
                    id=f"txt_{len(parsed)}",
                    function={"name": tool_name, "arguments": json.dumps(args)},
                ))

        return parsed

    async def _manage_context(self, provider_client) -> None:
        """Compress old messages when context exceeds 75% of max.

        Strategy:
        1. Keep last 4 non-system messages intact (recent context).
        2. Batch-compress older messages 5 at a time.
        3. Truncate very old messages without LLM; use LLM only for recent context.
        """
        threshold = int(self._max_context_tokens * 0.75)
        max_iters = 10

        for _ in range(max_iters):
            if self._estimate_tokens() <= threshold or len(self.messages) <= 4:
                break

            # Keep last 4 non-system messages untouched
            non_system = [(i, m) for i, m in enumerate(self.messages) if m.role != "system"]
            if len(non_system) <= 4:
                break

            # Compress oldest batch (before last 4 non-system messages)
            batch_indices = [i for i, _ in non_system[:-4][:5]]
            if not batch_indices:
                break

            batch = [self.messages[i] for i in batch_indices]
            msg_pos = max(batch_indices)

            if msg_pos < len(self.messages) // 2:
                snippet = "; ".join(
                    (m.content or "")[:60] for m in batch
                )
                summary = f"[historial antiguo: {snippet}...]"
            else:
                summary = await self._summarize_messages(batch, provider_client)

            summary_msg = Message(
                role="system",
                content=f"[Conversación resumida] {summary}",
            )

            for idx in sorted(batch_indices, reverse=True):
                self.messages.pop(idx)

            self.messages.insert(0, summary_msg)

    async def _summarize_messages(self, messages: list[Message], provider_client) -> str:
        """Ask the model to summarize a list of messages. Fallback to truncation."""
        conversation_text = "\n".join(
            f"{m.role}: {m.content}" for m in messages if m.content
        )
        prompt = (
            "Resume el siguiente fragmento de conversación en 2-3 frases. "
            "Preserva hechos clave, decisiones y contexto importante. "
            "Responde SOLO con el resumen, nada más.\n\n"
            f"{conversation_text}"
        )
        try:
            response = await provider_client.chat(
                messages=[Message(role="user", content=prompt)],
                temperature=0.0,
                max_tokens=256,
            )
            if response.content:
                return response.content.strip()
        except Exception as exc:
            logger.warning("Summarization failed, falling back to truncation: %s", exc)

        fallback = " | ".join(
            f"{m.role[:3].upper()}: {m.content[:80]}..." for m in messages if m.content
        )
        return fallback

    async def _handle_tool_calls(self, tool_calls) -> None:
        for tool_call in tool_calls:
            fn = tool_call.function if isinstance(tool_call.function, dict) else {}
            tool_name = fn.get("name")
            raw_arguments = fn.get("arguments", {})
            arguments = raw_arguments
            if isinstance(raw_arguments, str):
                try:
                    arguments = json.loads(raw_arguments)
                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON arguments for %s: %s", tool_name, raw_arguments[:200])
                    self.messages.append(Message(
                        role="tool",
                        content=f"Error: malformed JSON arguments for {tool_name}. Raw: {raw_arguments[:500]}",
                        tool_call_id=tool_call.id,
                        name=tool_name,
                    ))
                    continue

            if not isinstance(arguments, dict):
                arguments = {}

            if not tool_name:
                self.messages.append(Message(
                    role="tool",
                    content="Invalid tool call: missing function name",
                    tool_call_id=tool_call.id,
                    name="invalid_tool",
                ))
                continue

            logger.info("Tool call: %s(%s)", tool_name, arguments)
            for cb in self.on_tool_call:
                cb(tool_name)
            result: ToolResult = await self.tools.execute(
                tool_name, arguments,
                on_subprocess=lambda p: [cb(p) for cb in self.on_subprocess],
            )
            for cb in self.on_tool_done:
                cb(tool_name, result.output, result.error)
            self.messages.append(Message(
                role="tool",
                content=result.output,
                tool_call_id=tool_call.id,
                name=tool_name,
            ))
            # Auto-save tool results
            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id,
                    role="tool", content=result.output or "",
                    tool_call_id=tool_call.id, name=tool_name,
                )

    async def chat(self, user_message: str, provider: str = "primary") -> AsyncIterator[str | tuple[str, str]]:
        """Process a user message through the agentic loop, streaming text and reasoning chunks.

        Yields:
          str               — text content chunk
          ("reasoning", str) — reasoning/thinking chunk
        """
        if not self._initialized:
            detected = await self.providers.auto_detect_model()
            self._initialized = True
            if not detected:
                primary_cb = self.providers._circuits.get("primary")
                if primary_cb:
                    primary_cb.force_open()
                for _name in self.providers._priority_order:
                    if _name != "primary" and self.providers._circuits.get(_name) and self.providers._circuits[_name].is_available:
                        provider = _name
                        break

        sanitized_message = _sanitize_user_message(user_message)
        if not sanitized_message:
            yield "Input discarded: empty or non-printable message."
            return

        self.messages.append(Message(role="user", content=sanitized_message))
        if self._current_session_id:
            self._session_store.append_message(
                self._current_session_id,
                role="user", content=sanitized_message,
            )
        client, used_provider = self.providers.get_healthy(provider)
        provider = used_provider
        provider_client = client
        yield ("provider_used", used_provider)
        tool_defs = self.tools.get_tool_defs()
        await self._manage_context(provider_client)

        for _iteration in range(self.max_iterations):
            self._cancel_event.clear()
            all_messages = [Message(role="system", content=self._build_system_prompt())] + self.messages
            response_text = ""
            reasoning_text = ""
            tool_calls_accum: list = []

            try:
                async for chunk_type, data in provider_client.chat_stream(
                    messages=all_messages,
                    tools=tool_defs if tool_defs else None,
                    temperature=self.config.llm_temperature,
                    max_tokens=self.config.llm_max_tokens,
                ):
                    if self._cancel_event.is_set():
                        yield "\n[interrupted]"
                        break
                    if chunk_type == "text" and isinstance(data, str) and data:
                        response_text += data
                        yield data
                    elif chunk_type == "reasoning" and isinstance(data, str):
                        reasoning_text += data
                        yield ("reasoning", data)
                    elif chunk_type == "tool_calls" and isinstance(data, list):
                        tool_calls_accum = data
            except (TimeoutError, ConnectionError, RuntimeError, httpx.HTTPError) as exc:
                error_message = _format_chat_error(exc)
                logger.error("Agent chat failure on '%s': %s", provider, error_message)
                self.providers.report_failure(provider)
                if self.providers.pinned:
                    self.messages.append(Message(role="assistant", content=f"[Error: {error_message}]"))
                    if self._current_session_id:
                        self._session_store.append_message(
                            self._current_session_id, role="assistant", content=f"[Error: {error_message}]",
                        )
                    yield ("error", error_message)
                    return
                remaining = [n for n in self.providers._priority_order
                             if n != provider
                             and self.providers._circuits.get(n)
                             and self.providers._circuits[n].is_available]
                if remaining:
                    provider = remaining[0]
                    provider_client = self.providers.get(provider)
                    yield ("provider_used", provider)
                    continue
                self.messages.append(Message(role="assistant", content=f"[Error: {error_message}]"))
                if self._current_session_id:
                    self._session_store.append_message(
                        self._current_session_id, role="assistant", content=f"[Error: {error_message}]",
                    )
                yield ("error", error_message)
                return

            if self._cancel_event.is_set():
                if response_text or reasoning_text:
                    stored_cancel = response_text or "(respuesta cancelada)"
                    self.messages.append(Message(role="assistant", content=stored_cancel))
                    if self._current_session_id:
                        self._session_store.append_message(
                            self._current_session_id, role="assistant", content=stored_cancel,
                        )
                break

            msg_count_before = len(self.messages)
            reasoning_to_store = reasoning_text if reasoning_text else None

            if tool_calls_accum:
                stored_content = "[procesando herramientas...]"
            elif response_text:
                stored_content = response_text
            else:
                stored_content = reasoning_text[:200] if reasoning_text else "(sin respuesta de texto)"

            self.messages.append(Message(
                role="assistant",
                content=stored_content,
                tool_calls=[tc.model_dump() for tc in tool_calls_accum] if tool_calls_accum else None,
                reasoning_content=reasoning_to_store,
            ))

            if self._current_session_id:
                self._session_store.append_message(
                    self._current_session_id,
                    role="assistant", content=stored_content,
                    tool_calls=[tc.model_dump() for tc in tool_calls_accum] if tool_calls_accum else None,
                    reasoning_content=reasoning_to_store,
                )
                if msg_count_before == 0 and sanitized_message:
                    self._session_store.update_title(
                        self._current_session_id, sanitized_message[:80],
                    )

            # ── Fallback: parse pseudo tool calls from text (GGUF models) ──
            if not tool_calls_accum and response_text:
                parsed = self._parse_text_tool_calls(response_text)
                if parsed:
                    tool_calls_accum = parsed

            if not tool_calls_accum:
                self.providers.report_success(provider)
                break

            if self._cancel_event.is_set():
                break

            # ── Loop detection: same tool + same args 3× in a row ──
            tool_key = json.dumps(
                [(tc.function.get("name"), tc.function.get("arguments"))
                 for tc in tool_calls_accum],
                sort_keys=True,
            )
            if tool_key == self._last_tool_key:
                self._same_tool_count += 1
            else:
                self._last_tool_key = tool_key
                self._same_tool_count = 1

            if self._same_tool_count >= 3:
                self.messages.append(Message(
                    role="system",
                    content=(
                        "Has repetido la misma herramienta 3 veces sin progreso. "
                        "Resume lo que sabes AHORA y responde al usuario. "
                        "NO llames más herramientas."
                    ),
                ))
                yield "\n[loop detectado — forzando respuesta]"
                continue

            await self._handle_tool_calls(tool_calls_accum)
        else:
            yield "\n[Max iterations reached]"

    def set_session(self, source: str = "tui", source_ref: str = "") -> str:
        """Set the current session. Creates or resumes if exists."""
        session_id = f"{source}_{source_ref}" if source_ref else self._session_store.create_session(source, source_ref)
        if self._session_store.get_metadata(session_id):
            self.messages = self._load_messages_from_store(session_id)
        else:
            session_id = self._session_store.create_session(source, source_ref)
        self._current_session_id = session_id
        self._persisted_count = len(self.messages)
        logger.info("Session set: %s", session_id)
        return session_id

    def load_session_by_id(self, session_id: str) -> bool:
        """Load a specific session by ID, replacing current messages."""
        messages = self._load_messages_from_store(session_id)
        if not messages:
            logger.warning("Session not found: %s", session_id)
            return False
        self._current_session_id = session_id
        self.messages = messages
        self._persisted_count = len(self.messages)
        logger.info("Session loaded: %s (%d messages)", session_id, len(messages))
        return True

    def save_current_session(self) -> bool:
        """Save unsaved messages to the active session. Only appends new messages."""
        if not self._current_session_id:
            return False
        unsaved = self.messages[self._persisted_count:]
        for msg in unsaved:
            self._session_store.append_message(
                self._current_session_id,
                msg.role, msg.content,
                msg.tool_calls, msg.tool_call_id, msg.name,
            )
        self._persisted_count = len(self.messages)
        logger.debug("Session saved: %s (%d new messages)", self._current_session_id, len(unsaved))
        return True

    def list_sessions(self, source: str | None = None, limit: int = 20) -> list[dict]:
        """List available sessions, optionally filtered by source."""
        metas = self._session_store.list_sessions(source=source, limit=limit)
        return [m.to_dict() for m in metas]

    def get_session_context(self, session_id: str, max_messages: int = 20) -> str:
        """Get formatted context from another session for model consumption."""
        return self._session_store.get_session_context(session_id, max_messages)

    def _load_messages_from_store(self, session_id: str) -> list[Message]:
        """Convert stored dicts back to Message objects."""
        rows = self._session_store.load_messages(session_id)
        messages = []
        for row in rows:
            messages.append(Message(
                role=row["role"],
                content=row.get("content"),
                tool_calls=row.get("tool_calls"),
                tool_call_id=row.get("tool_call_id"),
                name=row.get("name"),
                reasoning_content=row.get("reasoning_content"),
            ))
        return messages

    def reset(self):
        """Clear conversation history. Note: does NOT delete the session from disk."""
        self.messages.clear()
        self._current_session_id = None

    def interrupt(self) -> None:
        """Signal the agentic loop to stop after current chunk."""
        self._cancel_event.set()

    async def kill(self) -> None:
        """Nuclear cancel: interrupt + kill subprocess + reset state."""
        self._cancel_event.set()
        if self._active_subprocess and self._active_subprocess.returncode is None:
            try:
                self._active_subprocess.terminate()
                await asyncio.wait_for(self._active_subprocess.wait(), timeout=2.0)
            except (ProcessLookupError, asyncio.TimeoutError):
                try:
                    self._active_subprocess.kill()
                except ProcessLookupError:
                    pass
            self._active_subprocess = None
        self._cancel_event.clear()

    async def close(self):
        await self.providers.close_all()
