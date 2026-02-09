"""LLM 抽象層 — 支援 local Ollama、cloud gateway、claude_code（Agent SDK）"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from engine.config import load_config

if TYPE_CHECKING:
    from openai import OpenAI


_client: OpenAI | None = None


def _get_client(config: dict | None = None) -> OpenAI:
    global _client
    if _client is not None:
        return _client

    from openai import OpenAI as _OpenAI

    cfg = config or load_config()
    backend = cfg["engine"]["llm_backend"]
    llm_cfg = cfg["llm"][backend]

    if backend == "local":
        _client = _OpenAI(base_url=llm_cfg["base_url"], api_key="not-needed")
    else:
        api_key = os.environ.get(llm_cfg.get("api_key_env", ""), "")
        _client = _OpenAI(base_url=llm_cfg["gateway_url"], api_key=api_key)

    return _client


# ─── Claude Code backend (Agent SDK) ───


def _get_event_loop() -> asyncio.AbstractEventLoop:
    """取得或建立 event loop。"""
    try:
        loop = asyncio.get_running_loop()
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


async def _claude_code_query(
    prompt: str,
    system: str | None = None,
    config: dict | None = None,
    tier: str = "heavy",
) -> str:
    """用 Claude Agent SDK 的 query() 做單次 LLM 呼叫。

    tier: "light"=Haiku, "medium"=Sonnet, "heavy"=Opus。
    """
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        TextBlock,
        query,
    )

    cfg = config or load_config()
    cc_cfg = cfg.get("llm", {}).get("claude_code", {})

    # 三檔制：light=Haiku, medium=Sonnet, heavy=Opus
    if tier == "light":
        model = cc_cfg.get("model_light", "claude-haiku-4-5-20251001")
    elif tier == "medium":
        model = cc_cfg.get("model_medium", "claude-sonnet-4-5-20250929")
    else:  # heavy
        model = cc_cfg.get("model_heavy", "claude-opus-4-6")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    options = ClaudeAgentOptions(
        max_turns=1,
        permission_mode="bypassPermissions",
        system_prompt="你是一個精準的分析助手。只輸出被要求的內容，不要加額外解釋。",
    )
    if model:
        options.model = model

    result_parts: list[str] = []
    async for msg in query(prompt=full_prompt, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    result_parts.append(block.text)

    return "".join(result_parts)


async def _claude_code_batch(
    prompts: list[str],
    system: str | None = None,
    config: dict | None = None,
    max_concurrent: int = 5,
    tier: str = "heavy",
) -> list[str]:
    """用多個並行的 Agent SDK query 處理批次 prompts。

    透過 asyncio.Semaphore 控制並行數量，避免資源耗盡。
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_one(prompt: str) -> str:
        async with semaphore:
            return await _claude_code_query(prompt, system=system, config=config, tier=tier)

    tasks = [_run_one(p) for p in prompts]
    return await asyncio.gather(*tasks)


# ─── 統一介面 ───


def call_llm(
    prompt: str,
    system: str | None = None,
    config: dict | None = None,
    tier: str = "heavy",
) -> str:
    """單次 LLM 呼叫。

    tier: "light"=Haiku（分類/填表）, "medium"=Sonnet（歸納/推理）, "heavy"=Opus（最終生成）。
    """
    cfg = config or load_config()
    backend = cfg["engine"]["llm_backend"]

    if backend == "claude_code":
        loop = _get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _claude_code_query(prompt, system, cfg, tier=tier))
                return future.result()
        else:
            return loop.run_until_complete(_claude_code_query(prompt, system, cfg, tier=tier))

    # OpenAI-compatible backends (local / cloud) — tier 不影響（本地模型只有一個）
    client = _get_client(cfg)
    model = cfg["llm"][backend]["model"]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    return resp.choices[0].message.content or ""


def batch_llm(
    prompts: list[str],
    system: str | None = None,
    config: dict | None = None,
    max_concurrent: int = 5,
    tier: str = "heavy",
) -> list[str]:
    """批次 LLM 呼叫。claude_code backend 會並行處理，其他 backend 循序。"""
    cfg = config or load_config()
    backend = cfg["engine"]["llm_backend"]

    if backend == "claude_code":
        loop = _get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    _claude_code_batch(prompts, system, cfg, max_concurrent, tier=tier),
                )
                return future.result()
        else:
            return loop.run_until_complete(
                _claude_code_batch(prompts, system, cfg, max_concurrent, tier=tier)
            )

    # OpenAI-compatible backends: 循序處理
    return [call_llm(p, system=system, config=cfg, tier=tier) for p in prompts]
