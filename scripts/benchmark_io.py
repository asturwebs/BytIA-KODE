from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

from bytia_kode.tools.registry import BashTool, FileReadTool


async def main() -> None:
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory(dir=original_cwd) as temp_dir:
        workspace = Path(temp_dir)
        for idx in range(10):
            (workspace / f"sample_{idx}.txt").write_text(f"line {idx}\n" * 200, encoding="utf-8")

        os.chdir(workspace)
        try:
            read_tool = FileReadTool()
            bash_tool = BashTool()

            read_tasks = [read_tool.execute(path=f"sample_{idx}.txt") for idx in range(10)]
            bash_command = f'{sys.executable} -c "import time; time.sleep(0.5); print(\'ok\')"'
            bash_tasks = [bash_tool.execute(command=bash_command) for _ in range(5)]

            started = time.perf_counter()
            results = await asyncio.gather(*read_tasks, *bash_tasks)
            elapsed = time.perf_counter() - started
        finally:
            os.chdir(original_cwd)

    read_errors = sum(1 for result in results[:10] if result.error)
    bash_errors = sum(1 for result in results[10:] if result.error)
    print(f"benchmark_total_seconds={elapsed:.3f}")
    print(f"read_ops=10 read_errors={read_errors}")
    print(f"bash_ops=5 bash_errors={bash_errors}")


if __name__ == "__main__":
    asyncio.run(main())
