# Performance Report

## Evidencia de concurrencia efectiva

Se comparó el mismo lote de trabajo en dos modos:

- **Secuencial**: 10 lecturas de archivo + 5 comandos bash ejecutados en bucle `for`
- **Concurrente**: 10 lecturas de archivo + 5 comandos bash ejecutados con `asyncio.gather`

## Resultados

| Métrica | Valor |
| --- | --- |
| Tiempo secuencial | 2.591 s |
| Tiempo concurrente | 0.517 s |
| Factor de aceleración | 5.01x |
| Mejora relativa | 80.04 % |
| Errores secuencial | 0 |
| Errores concurrente | 0 |

## Conclusión

La ejecución concurrente demuestra **evidencia clara de concurrencia efectiva**: el lote completo baja de 2.591 s a 0.517 s. Esto confirma que el refactor asíncrono de la Fase 2 evita el bloqueo del event loop en operaciones de subprocess y E/S de disco.
