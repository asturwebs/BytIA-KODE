# Performance Report

## Evidencia de concurrencia efectiva

Se comparó el mismo lote de trabajo en dos modos:

- **Secuencial**: 10 lecturas de archivo + 5 comandos bash ejecutados en bucle `for`
- **Concurrente**: 10 lecturas de archivo + 5 comandos bash ejecutados con `asyncio.gather`

## Resultados

| Métrica | Valor |
| --- | --- |
| Tiempo secuencial | 2.584 s |
| Tiempo concurrente | 0.527 s |
| Factor de aceleración | 4.90x |
| Mejora relativa | 79.6 % |
| Errores secuencial | 0 |
| Errores concurrente | 0 |

## Metodología

- 10 operaciones de lectura de archivos de 200 líneas cada uno
- 5 comandos bash con `sleep(0.5)` simulando I/O bloqueante
- Ejecutado con `asyncio.create_subprocess_exec` (concurrente) vs `for` + `await` (secuencial)
- Entorno: WSL2 Ubuntu 22.04, Python 3.13, uv venv

## Conclusión

La ejecución concurrente demuestra **evidencia clara de concurrencia efectiva**: el lote completo baja de 2.584 s a 0.527 s. Esto confirma que el refactor asíncrono evita el bloqueo del event loop en operaciones de subprocess y E/S de disco.
