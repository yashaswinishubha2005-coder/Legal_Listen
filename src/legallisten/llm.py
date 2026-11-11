"""LLM client for LegalListen (Gemini by default; Anthropic / OpenAI optional; Fake for tests).

Privacy: consultation text is never cached or logged by this module; only token counts are logged
(reports/legallisten_llm_usage.jsonl, no content). Keys are read from the environment only.

    LEGALLISTEN_LLM=gemini|anthropic|openai|none   (default: gemini if GEMINI_API_KEY is set, else none)
    LEGALLISTEN_MODEL=<model id>                  (default per provider, see DEFAULT_MODELS)
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .knowledge import ROOT

PROMPTS = ROOT / "prompts"
USAGE = ROOT / "reports" / "legallisten_llm_usage.jsonl"
DEFAULT_MODELS = {"gemini": "gemini-2.5-flash", "anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini"}
LANG_NAMES = {"en": ("English", "simple Indian English"), "kn": ("Kannada", "Kannada script; common English words are fine"),
              "hi": ("Hindi", "Devanagari script; common English words are fine")}


class LLMError(RuntimeError):
    pass


class LLM:
    name = "base"

    def __init__(self, model: str, timeout: int = 60):
        self.model, self.timeout = model, timeout

    def json(self, prompt: str, tag: str, audio: tuple[bytes, str] | None = None) -> dict:
        text = self._call(prompt, audio)
        return parse_json(text)

    def _call(self, prompt: str, audio) -> str:  # pragma: no cover - network
        raise NotImplementedError

    def _log(self, tag: str, tin: int, tout: int) -> None:
        try:
            USAGE.parent.mkdir(parents=True, exist_ok=True)
            with open(USAGE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": round(time.time()), "provider": self.name, "model": self.model, "tag": tag,
                                    "input_tokens": tin, "output_tokens": tout}) + "\n")
        except OSError:
            pass


def _post(url: str, headers: dict, body: dict, timeout: int) -> dict:  # pragma: no cover - network
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            last = LLMError(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError) as e:
            last = LLMError(str(e))
        time.sleep(1.5 * (attempt + 1))
    raise last or LLMError("request failed")


class Gemini(LLM):
    name = "gemini"

    def _call(self, prompt, audio=None):  # pragma: no cover - network
        parts = [{"text": prompt}]
        if audio:
            parts.append({"inlineData": {"mimeType": audio[1], "data": base64.b64encode(audio[0]).decode()}})
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                  {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                  {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json",
                                        "maxOutputTokens": 8192}}, self.timeout)
        try:
            text = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except (KeyError, IndexError) as e:
            raise LLMError(f"unexpected Gemini response: {str(d)[:200]}") from e
        u = d.get("usageMetadata", {})
        self._log("gemini", u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0))
        return text


class Anthropic(LLM):
    name = "anthropic"

    def _call(self, prompt, audio=None):  # pragma: no cover - network
        if audio:
            raise LLMError("audio transcription is only implemented for Gemini")
        d = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                  {"model": self.model, "max_tokens": 4096, "temperature": 0.2,
                   "messages": [{"role": "user", "content": prompt}]}, self.timeout)
        u = d.get("usage", {})
        self._log("anthropic", u.get("input_tokens", 0), u.get("output_tokens", 0))
        return "".join(b.get("text", "") for b in d["content"] if b.get("type") == "text")


class OpenAI(LLM):
    name = "openai"

    def _call(self, prompt, audio=None):  # pragma: no cover - network
        if audio:
            raise LLMError("audio transcription is only implemented for Gemini")
        d = _post("https://api.openai.com/v1/chat/completions", {"authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                  {"model": self.model, "temperature": 0.2, "response_format": {"type": "json_object"},
                   "messages": [{"role": "user", "content": prompt}]}, self.timeout)
        u = d.get("usage", {})
        self._log("openai", u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        return d["choices"][0]["message"]["content"]


class Fake(LLM):
    """Scripted offline LLM for tests: pops responses (dicts or callables taking the prompt)."""

    name = "fake"

    def __init__(self, script=None, model="fake"):
        super().__init__(model)
        self.script = list(script or [])
        self.prompts: list[str] = []

    def _call(self, prompt, audio=None):
        self.prompts.append(prompt)
        if not self.script:
            raise LLMError("fake script exhausted")
        r = self.script.pop(0)
        r = r(prompt) if callable(r) else r
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("model did not return valid JSON")


def from_env() -> LLM | None:
    prov = os.environ.get("LEGALLISTEN_LLM", "").strip().lower()
    if not prov:
        prov = "gemini" if os.environ.get("GEMINI_API_KEY") else "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "none"
    if prov == "none":
        return None
    need = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
    if prov not in need:
        raise ValueError(f"unknown LEGALLISTEN_LLM={prov!r}")
    if not os.environ.get(need[prov]):
        return None
    model = os.environ.get("LEGALLISTEN_MODEL", "").strip() or DEFAULT_MODELS[prov]
    return {"gemini": Gemini, "anthropic": Anthropic, "openai": OpenAI}[prov](model)


def prompt(name: str, **kw) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8").format(**kw)


def lang_kw(lang: str) -> dict:
    n, s = LANG_NAMES.get(lang, LANG_NAMES["en"])
    return {"lang_name": n, "script_note": s}
