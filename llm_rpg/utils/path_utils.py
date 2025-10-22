import os
from typing import Dict
from llm_rpg.utils.config import ConfigManager

import logging
logger = logging.getLogger(__name__)

def setup_paths(config_manager: ConfigManager) -> Dict[str, str]:
    """Setup necessary directories based on configuration"""
    path_config = config_manager.get_path_config()

    # Create all necessary directories
    for path_key, path_value in path_config.items():
        if path_key.endswith('_folder') and path_value:
            os.makedirs(path_value, exist_ok=True)
            logging.info(f"Created/verified directory: {path_value}")

    return path_config
