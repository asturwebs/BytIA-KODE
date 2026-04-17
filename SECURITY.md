# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.7.x   | Yes       |
| < 0.7   | No        |

BytIA KODE is in Alpha (`Development Status :: 3 - Alpha`). Security updates are applied to the latest release only.

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Email: **pedro@asturwebs.es** with subject `B-KODE Security: <brief description>`.

### What to include

- Type of issue (command injection, path traversal, token leak, etc.)
- Full steps to reproduce
- Affected version
- Any known workarounds

### Response timeline

- **Acknowledgment** within 48 hours
- **Initial assessment** within 7 days
- **Fix or mitigation** timeline communicated after assessment

### Security Model

BytIA KODE implements defense-in-depth:

- **BashTool:** allowlist of 26 binaries, `shell=False`, `shlex.split()`, shell operators blocked
- **File tools:** sandbox to CWD + trusted paths (`~/.bytia-kode/`)
- **Telegram:** fail-secure by default (denies all without `TELEGRAM_ALLOWED_USERS`)
- **Pre-commit:** `check_secrets.py` scans for leaked credentials before every commit

See `CLAUDE.md` and `docs/ARCHITECTURE.md` for full security architecture details.

## Known Security Considerations

- `safe_mode` toggle is visual-only, does not harden the backend
- Token estimation uses heuristic (`chars/3`), not a real tokenizer
- Extra binaries can be added via `EXTRA_BINARIES` env var — users are responsible for their selections
