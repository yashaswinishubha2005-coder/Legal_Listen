"""Configurable LLM provider (env-driven), response cache, fixed seeds, token/cost log.

Environment (see .env.example):
    LLM_PROVIDER = gemini | anthropic | openai | fake
    GEN_MODEL    = model id used for generation (pin an exact version)
    JUDGE_PROVIDER / JUDGE_MODEL = must differ from the generator (enforced in judge.py)
    GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY

Keys are read from the environment only and never written to disk or logs.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / ".cache" / "llm"
USAGE_LOG = ROOT / "reports" / "llm_usage.jsonl"
# USD per 1M tokens (input, output). Placeholders — fill from your provider's current price sheet.
PRICES: dict[str, tuple[float, float]] = {}


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False


class Provider:
    name = "base"

    def __init__(self, model: str, temperature: float = 0.7, seed: int = 13, max_tokens: int = 2048):
        self.model, self.temperature, self.seed, self.max_tokens = model, temperature, seed, max_tokens

    def _call(self, prompt: str) -> Completion:  # pragma: no cover - network
        raise NotImplementedError

    def complete(self, prompt: str, tag: str = "") -> Completion:
        key = hashlib.sha256(json.dumps([self.name, self.model, self.temperature, self.seed, prompt]).encode()).hexdigest()
        path = CACHE / f"{key}.json"
        if path.exists():
            d = json.loads(path.read_text(encoding="utf-8"))
            return Completion(d["text"], d["input_tokens"], d["output_tokens"], cached=True)
        for attempt in range(4):
            try:
                c = self._call(prompt)
                break
            except Exception:  # noqa: BLE001
                if attempt == 3:
                    raise
                time.sleep(2 ** (attempt + 1))
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"text": c.text, "input_tokens": c.input_tokens, "output_tokens": c.output_tokens}),
                        encoding="utf-8")
        _log(self, c, tag)
        return c


def _post(url: str, headers: dict, body: dict) -> dict:  # pragma: no cover - network
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


class Gemini(Provider):
    name = "gemini"

    def _call(self, prompt: str) -> Completion:  # pragma: no cover - network
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        d = _post(url, {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                  {"contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": self.temperature, "seed": self.seed,
                                        "maxOutputTokens": self.max_tokens}})
        text = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        u = d.get("usageMetadata", {})
        return Completion(text, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))


class Anthropic(Provider):
    name = "anthropic"

    def _call(self, prompt: str) -> Completion:  # pragma: no cover - network
        d = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                  {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
                   "messages": [{"role": "user", "content": prompt}]})
        text = "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")
        u = d.get("usage", {})
        return Completion(text, u.get("input_tokens", 0), u.get("output_tokens", 0))


class OpenAI(Provider):
    name = "openai"

    def _call(self, prompt: str) -> Completion:  # pragma: no cover - network
        d = _post("https://api.openai.com/v1/chat/completions",
                  {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                  {"model": self.model, "temperature": self.temperature, "seed": self.seed,
                   "max_tokens": self.max_tokens, "messages": [{"role": "user", "content": prompt}]})
        u = d.get("usage", {})
        return Completion(d["choices"][0]["message"]["content"], u.get("prompt_tokens", 0), u.get("completion_tokens", 0))


class Fake(Provider):
    """Deterministic offline provider for tests: returns a scripted response."""

    name = "fake"
    script: list[str] = []

    def _call(self, prompt: str) -> Completion:
        return Completion(self.script.pop(0) if self.script else prompt, len(prompt) // 4, 10)


PROVIDERS = {"gemini": Gemini, "anthropic": Anthropic, "openai": OpenAI, "fake": Fake}


def from_env(role: str = "GEN", **kw) -> Provider:
    prov = os.environ.get("LLM_PROVIDER" if role == "GEN" else "JUDGE_PROVIDER", "fake").strip()
    model = os.environ.get(f"{role}_MODEL", "fake-model").strip()
    if prov not in PROVIDERS:
        raise ValueError(f"unknown provider {prov!r}")
    return PROVIDERS[prov](model, **kw)


def _log(p: Provider, c: Completion, tag: str) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    pin, pout = PRICES.get(p.model, (0.0, 0.0))
    cost = (c.input_tokens * pin + c.output_tokens * pout) / 1e6
    with open(USAGE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.time(), "provider": p.name, "model": p.model, "tag": tag,
                            "input_tokens": c.input_tokens, "output_tokens": c.output_tokens,
                            "cost_usd_estimate": round(cost, 6)}) + "\n")


def estimate_cost(n_calls: int, in_tokens: int, out_tokens: int, model: str) -> float:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    return n_calls * (in_tokens * pin + out_tokens * pout) / 1e6
