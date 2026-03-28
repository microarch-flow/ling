import pytest
import tempfile
from pathlib import Path
from t.config import load_config, Config, TranslatorConfig, CLIConfig

VALID_YAML = """
translator:
  provider: openai
  api_key: sk-test
  model: gpt-4o
  base_url: https://api.example.com
  accumulate_timeout: 2.0
  request_timeout: 30
  fallback_on_timeout: true
cli:
  command: claude
  args: []
"""

MINIMAL_YAML = """
translator:
  provider: anthropic
  api_key: sk-ant-test
  model: claude-opus-4-6
cli:
  command: claude
"""

def write_config(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    f.write(content)
    f.flush()
    return Path(f.name)

def test_load_full_config():
    path = write_config(VALID_YAML)
    config = load_config(path)
    assert config.translator.provider == "openai"
    assert config.translator.api_key == "sk-test"
    assert config.translator.model == "gpt-4o"
    assert config.translator.base_url == "https://api.example.com"
    assert config.translator.accumulate_timeout == 2.0
    assert config.translator.request_timeout == 30
    assert config.translator.fallback_on_timeout is True
    assert config.cli.command == "claude"
    assert config.cli.args == []

def test_load_minimal_config_uses_defaults():
    path = write_config(MINIMAL_YAML)
    config = load_config(path)
    assert config.translator.provider == "anthropic"
    assert config.translator.base_url is None
    assert config.translator.accumulate_timeout == 2.0
    assert config.translator.request_timeout == 30
    assert config.translator.fallback_on_timeout is True
    assert config.cli.args == []

def test_invalid_provider_raises():
    yaml = VALID_YAML.replace("provider: openai", "provider: unknown")
    path = write_config(yaml)
    with pytest.raises(ValueError, match="provider"):
        load_config(path)

def test_missing_api_key_raises():
    yaml = "\n".join(l for l in VALID_YAML.splitlines() if "api_key" not in l)
    path = write_config(yaml)
    with pytest.raises(ValueError, match="api_key"):
        load_config(path)
