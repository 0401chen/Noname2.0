from __future__ import annotations

import asyncio
import json

from .config import get_settings
from .llm import LLMClient


async def run_check() -> int:
    settings = get_settings()
    result = await LLMClient(settings).check_connection()
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))

    if result.ok:
        print(
            f"Noname助手模型接口可用：{result.model} @ {result.endpoint_host}，"
            f"模式={result.completion_mode}，耗时={result.latency_ms:.0f}ms"
        )
        return 0

    print(f"Noname助手模型接口检查失败：{result.error or '未知错误'}")
    return 1


def main() -> None:
    raise SystemExit(asyncio.run(run_check()))


if __name__ == "__main__":
    main()
