from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

VALID_PROVIDERS = {"openai", "anthropic"}

@dataclass
class TranslatorConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None
    accumulate_timeout: float = 2.0
    request_timeout: int = 30
    fallback_on_timeout: bool = True

@dataclass
class CLIConfig:
    command: str = "claude"
    args: list[str] = field(default_factory=list)

@dataclass
class Config:
    translator: TranslatorConfig
    cli: CLIConfig

def load_config(path: Path) -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    t = raw.get("translator", {})
    if "api_key" not in t:
        raise ValueError("translator.api_key is required")
    provider = t.get("provider", "openai")
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"translator.provider must be one of {VALID_PROVIDERS}, got '{provider}'")

    translator = TranslatorConfig(
        provider=provider,
        api_key=t["api_key"],
        model=t["model"],
        base_url=t.get("base_url"),
        accumulate_timeout=float(t.get("accumulate_timeout", 2.0)),
        request_timeout=int(t.get("request_timeout", 30)),
        fallback_on_timeout=bool(t.get("fallback_on_timeout", True)),
    )

    c = raw.get("cli", {})
    cli = CLIConfig(
        command=c.get("command", "claude"),
        args=c.get("args") or [],
    )

    return Config(translator=translator, cli=cli)

def default_config_path() -> Path:
    return Path.home() / ".ling" / "config.yaml"
