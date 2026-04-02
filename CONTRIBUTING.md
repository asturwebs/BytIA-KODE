# Contribuir a BytIA KODE

Gracias por tu interes en contribuir a BytIA KODE! Todas las contribuciones son bienvenidas, desde reportes de bugs y sugerencias de nuevas caracteristicas, hasta pull requests con mejoras en el codigo o la documentacion.

## Reportar un Bug o Solicitar una Caracteristica

Si encuentras un error o tienes una idea para mejorar el proyecto, por favor abre un issue en GitHub detallando:
- Descripcion clara del problema o la caracteristica.
- Pasos para reproducir el bug (si aplica).
- Entorno (SO, version de Python, etc.).

## Desarrollo Local

1. Haz un fork del repositorio y clonalo localmente.
2. Crea una nueva rama para tu caracteristica o correccion:
   \\ash
   git checkout -b mi-nueva-caracteristica
   \3. Configura tu entorno virtual, preferiblemente usando uv:
   \\ash
   uv sync
   \4. Realiza tus cambios. Asegurate de que el codigo sigue el estilo del proyecto y anade o actualiza tests segun sea necesario.

## Ejecucion de Tests

Antes de hacer un commit, verifica que todas las pruebas pasen correctamente:
\\ash
uv run pytest -q
\
## Enviar un Pull Request

1. Haz un commit de tus cambios con mensajes descriptivos.
   \\ash
   git commit -m \
