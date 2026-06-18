"""
Thin wrapper around the LLM.

We use the official OpenAI Python library but point it at Cerebras's endpoint.
Cerebras is OpenAI-API-compatible, so the ONLY things that change are the
base_url and the api_key -- prompts, parsing, everything else is identical.
That's why swapping LLM providers later is a one-line change.
"""
import json
import re
from openai import OpenAI
import config

_client = None  # built once, then reused (cheaper than rebuilding each call)


def _get_client():
    global _client
    if _client is None:
        if not config.CEREBRAS_API_KEY:
            raise RuntimeError("CEREBRAS_API_KEY is missing in .env")
        _client = OpenAI(
            base_url=config.CEREBRAS_BASE_URL,
            api_key=config.CEREBRAS_API_KEY,
        )
    return _client


def chat(prompt, system=None, temperature=0.2):
    """Send a prompt, get back the model's text answer."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _get_client().chat.completions.create(
        model=config.CEREBRAS_MODEL,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content


def _clean_json_text(text):
    """LLMs sometimes wrap JSON in reasoning tags or ``` fences. Strip those
    and grab the first {...} block so json.loads() doesn't choke."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # reasoning
    text = re.sub(r"```(?:json)?", "", text).replace("```", "")       # fences
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return match.group(0) if match else text.strip()


def extract_json(prompt, system=None):
    """Ask the model for JSON and return it as a Python dict."""
    raw = chat(prompt, system=system, temperature=0)
    cleaned = _clean_json_text(raw)
    return json.loads(cleaned)
