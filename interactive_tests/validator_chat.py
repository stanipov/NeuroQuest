#!/usr/bin/env python3
"""
Interactive InputValidator chat session.

Loads a lore file, instantiates an LLM client and InputValidator,
then runs a looped chat session logging all inputs/outputs to JSON.
"""

import json
import uuid
import sys, os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_rpg.clients.llamacpp import LocalLLMClient
from llm_rpg.engine.gateways import InputGateway
from llm_rpg.engine.memory import GameMemory
from llm_rpg.utils.config_loader import load_config


# Configuration paths
CONFIG_PATH = "/ext4/projects/NeuroQuest/configs/working_cfg.json"
LORE_PATH = "/ext4/projects/NeuroQuest/game/saved_games/80a6c5c24db443c0ad6f1f55d83d629c/lore.json"
TMP_DIR = Path("/ext4/projects/NeuroQuest/tmp")


def load_lore(lore_path: str) -> Dict[str, Any]:
    """Load lore from JSON file."""
    with open(lore_path, "r") as f:
        return json.load(f)


def create_unique_log_file(tmp_dir: Path) -> Path:
    """Create a log filename with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"validator_chat_{timestamp}.json"
    return tmp_dir / filename


def format_response(response) -> Dict[str, Any]:
    """Format validator response for logging."""
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return dict(response)


def display_session_info(lore: Dict[str, Any]) -> None:
    """Display entry point and NPC information for the session."""
    print("\n" + "=" * 60)
    print("SESSION INFORMATION")
    print("=" * 60)

    # Display Entry Point / Start Location
    if "start" in lore:
        print(f"\n📍 ENTRY POINT:")
        print(f"   {lore['start']}")
    else:
        print("\n📍 ENTRY POINT: Not defined")

    # Display NPC Companion(s)
    if "npc" in lore and lore["npc"]:
        print(f"\n👥 NPC COMPANIONS:")
        for npc_name, npc_data in lore["npc"].items():
            print(f"   • {npc_name}")
            if isinstance(npc_data, dict) and "description" in npc_data:
                desc = (
                    npc_data["description"][:60] + "..."
                    if len(str(npc_data["description"])) > 60
                    else npc_data["description"]
                )
                print(f'     "{desc}"')
    else:
        print("\n👥 NPC COMPANIONS: None assigned")

    print()


def main():
    # Ensure tmp directory exists
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Load config
    print(f"Loading config from: {CONFIG_PATH}")
    config = load_config(CONFIG_PATH)

    # Extract input_validator LLM provider config
    validator_llm_config = config["llm_providers"]["input_validator"]
    llm_props =  config["llm_providers"]["input_validator"].get('props', {})
    MODEL_NAME = validator_llm_config["model"]
    BASE_URL = validator_llm_config["base_url"]
    TEMPERATURE = validator_llm_config["props"]["temperature"]

    # Extract InputValidatorConfig
    validator_config = config.get("input_validator")

    print(f"Loading lore from: {LORE_PATH}")
    lore = load_lore(LORE_PATH)

    # Create temp database path
    temp_db_path = str(TMP_DIR / f"temp_{uuid.uuid4().hex[:8]}.db")

    print(f"Initializing LLM client (model={MODEL_NAME}, url={BASE_URL})")
    llm_client = LocalLLMClient(model_name=MODEL_NAME, base_url=BASE_URL)

    print("Creating GameMemory...")
    game_memory = GameMemory(temp_db_path, llm_client, lore)

    print("Initializing InputValidator...")
    validator = InputGateway(
        lore, llm_client, game_memory=game_memory, config=validator_config
    )

    # Create log file
    log_file = create_unique_log_file(TMP_DIR)
    print(f"Logging to: {log_file}")

    # Display session information (entry point and NPCs)
    display_session_info(lore)

    # Initialize log structure
    log_data = {
        "session_info": {
            "start_time": datetime.now().isoformat(),
            "config_path": CONFIG_PATH,
            "lore_path": LORE_PATH,
            "model_name": MODEL_NAME,
            "base_url": BASE_URL,
            "validator_config": validator_config,
        },
        "messages": [],
    }

    print("\n" + "=" * 60)
    print("InputValidator Interactive Session")
    print("=" * 60)
    print("\nEnter player actions to validate. Type 'quit' or 'exit' to end session.")
    print("Type 'context' to see current dynamic context.")
    print("Type 'clear' to reset the conversation log.\n")

    session_messages = []

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit"):
                break

            if user_input.lower() == "clear":
                session_messages.clear()
                print("Conversation log cleared.")
                continue

            if user_input.lower() == "context":
                context = validator._build_dynamic_context("")
                print("\n--- Current Dynamic Context ---")
                print(json.dumps(context, indent=2, default=str))
                print("---\n")
                continue

            # Log user input
            session_messages.append(
                {
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Write user input to memory and increment turn
            game_memory.update_game_history(
                [
                    {"role": "user_input", "message": user_input},
                    {"role": "game_action", "message": ""}
                 ]
            )

            # Validate input
            print("\nValidating...")
            response = validator.run(action=user_input,
                                     use_dynamic_context=True,
                                     **llm_props)

            # Format and display response
            response_dict = format_response(response)

            print("\n--- Validator Response ---")
            # Dynamically print all fields from the response model
            for field_name, value in response_dict.items():
                display_name = field_name.replace("_", " ").title()
                if isinstance(value, list):
                    print(f"{display_name}: {value}")
                else:
                    print(f"{display_name}: {value}")
            print("---\n")

            # Log response
            session_messages.append(
                {
                    "role": "validator",
                    "content": response_dict,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            # Save log after each turn
            log_data["messages"] = session_messages
            log_data["session_info"]["total_messages"] = len(session_messages)
            with open(log_file, "w") as f:
                json.dump(log_data, f, indent=2, default=str)

        except KeyboardInterrupt:
            print("\n\nSession interrupted.")
            break

        except Exception as e:
            print(f"\nError: {e}")
            session_messages.append(
                {
                    "role": "error",
                    "content": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )

    # Finalize log
    log_data["session_info"]["end_time"] = datetime.now().isoformat()
    log_data["session_info"]["total_messages"] = len(session_messages)
    log_data["messages"] = session_messages

    # Save log
    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2, default=str)

    print(f"\nSession logged to: {log_file}")
    print(f"Total messages exchanged: {len(session_messages)}")


if __name__ == "__main__":
    main()
