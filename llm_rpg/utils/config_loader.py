import json
from pathlib import Path


def load_config(config_path: str) -> dict:
    """
    Load and validate config from JSON file.
    Returns a plain dict (model_dump output) for compatibility.
    """
    from llm_rpg.utils.config_models import AppConfig

    with open(config_path, "r") as f:
        data = json.load(f)
    # Validate using Pydantic (raises ValidationError on failure)
    config_model = AppConfig.model_validate(data)
    # Return plain dict for compatibility with existing code
    return config_model.model_dump()


def save_config(config: dict, config_path: str):
    """Save config to JSON file"""
    from llm_rpg.utils.config_models import AppConfig

    if isinstance(config, AppConfig):
        config = config.model_dump()
    Path(config_path).parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
