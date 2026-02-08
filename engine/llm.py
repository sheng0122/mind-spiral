"""LLM 抽象層 — 支援 local Ollama 和 cloud gateway（OpenAI-compatible）"""

import os
from openai import OpenAI

from engine.config import load_config


_client: OpenAI | None = None


def _get_client(config: dict | None = None) -> OpenAI:
    global _client
    if _client is not None:
        return _client

    cfg = config or load_config()
    backend = cfg["engine"]["llm_backend"]
    llm_cfg = cfg["llm"][backend]

    if backend == "local":
        _client = OpenAI(base_url=llm_cfg["base_url"], api_key="not-needed")
    else:
        api_key = os.environ.get(llm_cfg["api_key_env"], "")
        _client = OpenAI(base_url=llm_cfg["gateway_url"], api_key=api_key)

    return _client


def call_llm(prompt: str, system: str | None = None, config: dict | None = None) -> str:
    cfg = config or load_config()
    client = _get_client(cfg)
    backend = cfg["engine"]["llm_backend"]
    model = cfg["llm"][backend]["model"]

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = client.chat.completions.create(model=model, messages=messages, temperature=0.3)
    return resp.choices[0].message.content or ""
