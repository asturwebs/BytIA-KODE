# Security Policy

## Versiones soportadas

Solo la **última versión publicada en PyPI** recibe correcciones de seguridad.

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usa uno de estos canales privados:

1. **GitHub Private Vulnerability Reporting**: pestaña *Security* → *Advisories* → *Report a vulnerability*.
2. **Email**: `pedro@asturwebs.es` con `SECURITY` en el asunto.

Incluye: versión afectada, pasos para reproducir, impacto y, si es posible, una propuesta de mitigación.

**Plazos**: acuse de recibo en ≤72 h; fix o mitigación en ≤90 días desde la confirmación.

## Alcance

Interesan especialmente:

- **Bypasses del perímetro de tools**: jail de workspace (`confined`/`permissive`/`open`), allowlist de binarios, validación de argv, SSRF de `web_fetch`.
- **Escrituras fuera del workspace** vía tools o vía el worker del orquestador (`scratch/`).
- **Fugas de secretos** en logs o en el repositorio (el publish usa OIDC: no hay tokens en el repo).
- **Prompt injection** que consiga ejecutar tools no autorizadas o exfiltrar datos.

## Fuera de alcance

- El agente **ejecuta comandos en tu máquina por diseño**: un binario permitido que lea configuración global (p. ej. `~/.gitconfig`) está documentado como límite de la política de intención (`README` → *Política de workspace*).
- Vulnerabilidades en dependencias sin impacto demostrable en el paquete: repórtalas upstream (Dependabot ya las vigila).
