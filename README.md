# BytIA KODE - Agentic Coding Assistant

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**BytIA KODE** es un asistente de coding agéntico con interfaz de terminal (TUI) y bot de Telegram, totalmente compatible con cualquier endpoint de la API de OpenAI. Está diseñado para ayudarte en tus tareas de programación mediante un bucle autónomo (\	hink -> act -> observe -> repeat\).

## 🌟 Características Principales

- **Arquitectura Agéntica**: Bucle de conversación autónomo que le permite al modelo utilizar herramientas para leer, escribir archivos y ejecutar comandos.
- **Interfaz TUI Avanzada**: Basada en Textual, ofrece un entorno visual en la terminal con entrada de texto, historial de chat, barra de estado y visualización de comandos en tiempo real.
- **Integración con Telegram**: Incluye un bot de Telegram con control de acceso basado en listas blancas para operar el asistente desde cualquier lugar.
- **Soporte Multi-Proveedor**: Compatible de forma nativa con Z.AI, OpenRouter, MiniMax, Ollama, llama.cpp y cualquier endpoint compatible con OpenAI.
- **Extensible**: Sistema de carga de *Skills* (habilidades) y *Tools* (herramientas) como \ash\, \ile_read\, \ile_write\.
- **Memoria Persistente**: Mantiene el contexto a través de la sesión del agente.

## 📋 Requisitos Previos

- **Python**: Versión \>=3.11- **Gestor de paquetes**: Se recomienda encarecidamente usar [uv](https://github.com/astral-sh/uv) para una instalación y gestión de entornos ultrarrápida.

## 🚀 Instalación y Configuración

1. **Clonar el repositorio:**
   \\ash
   git clone https://github.com/asturwebs/BytIA-KODE.git
   cd BytIA-KODE
   \
2. **Configurar el entorno:**
   Copia el archivo de ejemplo y configura tus variables de entorno.
   \\ash
   cp .env.example .env
   \   Edita \.env\ y añade tu clave API y la URL base de tu proveedor preferido:
   \\nv
   PROVIDER_BASE_URL=https://api.openai.com/v1
   PROVIDER_API_KEY=tu_api_key_aqui
   PROVIDER_MODEL=gpt-4o
   \
3. **Instalar dependencias:**
   \\ash
   uv sync
   \
## 💻 Uso

### Interfaz de Terminal (TUI)
Para iniciar la interfaz de terminal, simplemente ejecuta:
\\ash
uv run bytia-kode
\
### Bot de Telegram
Para iniciar el bot de Telegram (asegúrate de haber configurado \TELEGRAM_BOT_TOKEN\ y \TELEGRAM_ALLOWED_USERS\ en tu \.env\):
\\ash
uv run python -m bytia_kode.telegram.bot
\
## 🛠️ Comandos de la TUI

Puedes usar los siguientes comandos escribiéndolos en la barra inferior:

- \/help\ - Muestra la ayuda
- \/reset\ - Reinicia la conversación
- \/clear\ - Limpia la pantalla
- \/model\ - Muestra la configuración actual del proveedor
- \/tools\ - Lista las herramientas cargadas
- \/skills\ - Lista las habilidades cargadas
- \/cwd\ - Muestra el directorio de trabajo actual
- \/safe\ - Alterna el modo seguro

**Atajos de teclado:**
- \Ctrl+Q\ - Salir
- \Ctrl+R\ - Reiniciar
- \Ctrl+L\ - Limpiar
- \Ctrl+M\ - Ver Modelo
- \Ctrl+T\ - Ver Tools
- \Ctrl+S\ - Ver Skills
- \Ctrl+E\ - Modo Seguro
- \Ctrl+X\ - Copiar último bloque de código

## 🌐 Proveedores Compatibles (Ejemplos)

| Proveedor | URL Base (BASE_URL) |
|-----------|---------------------|
| OpenAI | \https://api.openai.com/v1\ |
| OpenRouter | \https://openrouter.ai/api/v1\ |
| Z.AI | \https://api.z.ai/api/coding/paas/v4\ |
| MiniMax | \https://api.minimax.chat/v1\ |
| Ollama (Local) | \http://localhost:11434/v1\ |

## 🧪 Pruebas y Calidad

Para ejecutar la suite de tests:
\\ash
uv run pytest -q
\Para verificar que el código compila correctamente:
\\ash
uv run python -m compileall -q src/bytia_kode
\
## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor, lee el archivo [CONTRIBUTING.md](CONTRIBUTING.md) para obtener detalles sobre nuestro código de conducta y el proceso para enviarnos pull requests.

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo \LICENSE\ (si está disponible) o el campo \license\ en \pyproject.toml\ para más detalles.
