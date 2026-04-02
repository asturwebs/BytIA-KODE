from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

from bytia_kode.tools.registry import BashTool, FileReadTool

READ_COUNT = 10
BASH_COUNT = 5


async def _run_sequential(read_tool: FileReadTool, bash_tool: BashTool) -> tuple[float, list]:
    started = time.perf_counter()
    results = []
    for idx in range(READ_COUNT):
        results.append(await read_tool.execute(path=f"sample_{idx}.txt"))
    bash_command = f"{sys.executable} -c \"import time; time.sleep(0.5); print('ok')\""
    for _ in range(BASH_COUNT):
        results.append(await bash_tool.execute(command=bash_command))
    elapsed = time.perf_counter() - started
    return elapsed, results


async def _run_concurrent(read_tool: FileReadTool, bash_tool: BashTool) -> tuple[float, list]:
    bash_command = f"{sys.executable} -c \"import time; time.sleep(0.5); print('ok')\""
    read_tasks = [read_tool.execute(path=f"sample_{idx}.txt") for idx in range(READ_COUNT)]
    bash_tasks = [bash_tool.execute(command=bash_command) for _ in range(BASH_COUNT)]
    started = time.perf_counter()
    results = await asyncio.gather(*read_tasks, *bash_tasks)
    elapsed = time.perf_counter() - started
    return elapsed, list(results)


async def main() -> None:
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(dir=original_cwd) as temp_dir:
        workspace = Path(temp_dir)
        for idx in range(READ_COUNT):
            (workspace / f"sample_{idx}.txt").write_text(f"line {idx}\n" * 200, encoding="utf-8")

        os.chdir(workspace)
        try:
            read_tool = FileReadTool()
            bash_tool = BashTool()
            sequential_seconds, sequential_results = await _run_sequential(read_tool, bash_tool)
            concurrent_seconds, concurrent_results = await _run_concurrent(read_tool, bash_tool)
        finally:
            os.chdir(original_cwd)

    sequential_errors = sum(1 for result in sequential_results if result.error)
    concurrent_errors = sum(1 for result in concurrent_results if result.error)
    speedup = sequential_seconds / concurrent_seconds if concurrent_seconds else 0.0
    improvement = ((sequential_seconds - concurrent_seconds) / sequential_seconds * 100.0) if sequential_seconds else 0.0

    print(f"sequential_total_seconds={sequential_seconds:.3f}")
    print(f"concurrent_total_seconds={concurrent_seconds:.3f}")
    print(f"speedup_factor={speedup:.2f}")
    print(f"improvement_percent={improvement:.2f}")
    print(f"sequential_errors={sequential_errors}")
    print(f"concurrent_errors={concurrent_errors}")


if __name__ == "__main__":
    asyncio.run(main())
