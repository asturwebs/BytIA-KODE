# Changelog

Todas las versiones notables y cambios de este proyecto se documentaran en este archivo.

El formato esta basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto se adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [0.1.0] - 2026-04-02
### Anadido
- Interfaz de usuario de terminal (TUI) basada en Textual.
- Bot de Telegram con control de acceso por lista blanca de usuarios.
- Arquitectura agentica base con bucle de pensamiento y accion (think -> act -> observe).
- Sistema extensible de herramientas (Tools) base (\ash\, \ile_read\, \ile_write\).
- Soporte para multiples proveedores de LLM compatibles con OpenAI (Z.AI, OpenRouter, MiniMax, Ollama, llama.cpp).
- Atajo \Ctrl+X\ para copiar facilmente el ultimo bloque de codigo generado.

### Modificado
- Mejorado el manejo de errores en el \ToolRegistry\ agregando logging detallado para fallos de comandos y lectura de archivos.
- Ajustada la logica del agente para lidiar robustamente con argumentos JSON malformados.
- Expancion segura de rutas usando \os.path.expanduser\ en la presentacion de la TUI.
- Actualizacion de la documentacion principal (\README.md\).

### Arreglado
- Correccion de redundancia de \isinstance\ y excepciones de JSON al interpretar argumentos de las herramientas.
- Tipado estricto en la firma de herramientas para evitar posibles vulnerabilidades.
