#!/usr/bin/env python3
"""
Interactive NPCAgent input gateway test session.

Loads a lore file, instantiates an LLM client and NPCAgent,
then runs a looped session testing the _input_gateway responses,
logging all inputs/outputs to JSON.
"""

import json
import uuid
import sys, os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import time


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from llm_rpg.clients.llamacpp import LocalLLMClient
from llm_rpg.engine.npc_ai import NPCAgent
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
    filename = f"npc_gateway_{timestamp}.json"
    return tmp_dir / filename


def display_session_info(lore: Dict[str, Any]) -> None:
    """Display NPC information for the session."""
    print("\n" + "=" * 60)
    print("SESSION INFORMATION")
    print("=" * 60)

    if "npc" in lore and lore["npc"]:
        print(f"\nNPCs in the game:")
        for npc_name, npc_data in lore["npc"].items():
            print(f"  - {npc_name}")
            if isinstance(npc_data, dict):
                goal = npc_data.get("goal", "Unknown")
                print(f"    Goal: {goal}")
    else:
        print("\nNo NPCs assigned")

    print()


def main():
    # Ensure tmp directory exists
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Load config
    print(f"Loading config from: {CONFIG_PATH}")
    config = load_config(CONFIG_PATH)

    # Extract npc_ai_llm provider config
    npc_llm_config = config["llm_providers"]["npc_ai_llm"]
    llm_props = npc_llm_config.get("props", {})
    MODEL_NAME = npc_llm_config["model"]
    BASE_URL = npc_llm_config["base_url"]

    # Extract npc_ai config
    npc_ai_config = config.get("npc_ai", {})

    # Load general game config for retry/temperature settings
    game_config = config.get("game", {})
    npc_ai_config.setdefault("max_generation_retries", game_config.get("max_generation_retries", 3))
    npc_ai_config.setdefault("temperature_cooldown_step", game_config.get("temperature_cooldown_step", 0.1))
    npc_ai_config.setdefault("temperature_min", game_config.get("temperature_min", 0.5))
    npc_ai_config.setdefault("temperature", npc_llm_config.get("props", {}).get("temperature", 0.7))

    print(f"Loading lore from: {LORE_PATH}")
    lore = load_lore(LORE_PATH)

    # Create temp database path
    temp_db_path = str(TMP_DIR / f"temp_{uuid.uuid4().hex[:8]}.db")

    print(f"Initializing LLM client (model={MODEL_NAME}, url={BASE_URL})")
    llm_client = LocalLLMClient(model_name=MODEL_NAME, base_url=BASE_URL)

    print("Creating GameMemory...")
    game_memory = GameMemory(temp_db_path, llm_client, lore)

    # Pick the first NPC from lore
    npc_name = list(lore["npc"].keys())[0]
    print(f"Initializing NPCAgent for: {npc_name}")
    npc_agent = NPCAgent(
        name=npc_name,
        llm_client=llm_client,
        lore=lore,
        config=npc_ai_config,
        game_memory=game_memory
    )

    # Create log file
    log_file = create_unique_log_file(TMP_DIR)
    print(f"Logging to: {log_file}")

    # Display session information
    display_session_info(lore)

    # Initialize log structure
    log_data = {
        "session_info": {
            "start_time": datetime.now().isoformat(),
            "config_path": CONFIG_PATH,
            "lore_path": LORE_PATH,
            "model_name": MODEL_NAME,
            "base_url": BASE_URL,
            "npc_name": npc_name,
            "npc_ai_config": npc_ai_config,
        },
        "messages": [],
    }

    print("\n" + "=" * 60)
    print(f"NPCAgent Input Gateway Interactive Session ({npc_name})")
    print("=" * 60)
    print(f"\nTesting _input_gateway for {npc_name}.")
    print("Enter player actions/inputs to test gateway decisions.")
    print("Type 'quit' or 'exit' to end session.")
    print("Type 'history' to see recent game history.")
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

            if user_input.lower() == "history":
                history = game_memory.get_last_n_turns(n=npc_ai_config.get("gateway_history_depth", 3))
                print("\n--- Recent Game History ---")
                if history:
                    for turn in history:
                        turn_num = turn.get("turn", "?")
                        user_action = turn.get("user_input", turn.get("human_response", "N/A"))
                        print(f"  Turn {turn_num}: {user_action}")
                else:
                    print("  No history yet.")
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

            # Write user input to memory
            game_memory.update_game_history(
                [
                    {"role": "user_input", "message": user_input},
                    {"role": "game_action", "message": ""}
                ]
            )

            # Run input gateway
            print(f"\nGateway decision for {npc_name}...")

            t_s = time.time()
            response = npc_agent._input_gateway(user_input)
            t_e = time.time()

            """
            print(f"\n--- Gateway Response ---")
            print(response)
            response_dict = response
            print("---\n")
            """

            should_act = response['should_act']
            
            response_dict = {
                "should_act": should_act,
                "reason": response['reason'],
                "npc_name": npc_name,
            }

            print(f"\n--- Gateway Response ---")
            print(f"\tshould_act: {should_act}")
            print(f"\t{'NPC WILL respond to this input' if should_act else 'NPC will NOT respond'}")
            print(f"\tReason: {response['reason']}")
            print(f"Response processed in {t_e-t_s:.2f} s")
            print("---\n")


            # Build response summary


            # Log response
            session_messages.append(
                {
                    "role": "gateway",
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
            import traceback
            print(f"\nError: {e}")
            traceback.print_exc()
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

    # Save final log
    with open(log_file, "w") as f:
        json.dump(log_data, f, indent=2, default=str)

    print(f"\nSession logged to: {log_file}")
    print(f"Total messages exchanged: {len(session_messages)}")


if __name__ == "__main__":
    main()
