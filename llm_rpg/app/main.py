import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
import logging
sys.path.append(os.getcwd())

from llm_rpg.utils.path_utils import setup_paths
from llm_rpg.engine.io import IO
from llm_rpg.gui.console_manager import ConsoleManager
from llm_rpg.gui.game_menu import GameMenu
from llm_rpg.gui.chat import RPGChatInterface
from llm_rpg.utils.mock_functions import user_input_process_mock, ai_response_mock

from llm_rpg.app.lore_generator import GenerateLore
from llm_rpg.app.set_memory import init_memory_lore

from llm_rpg.utils.config import ConfigManager, setup_llms, get_lore_generation_params
from llm_rpg.utils.logger import set_logger

# ----- Some testing flags -----
TEST_CHAT_UI = True

if __name__ == "__main__":
    # ----- Configuration Setup -----
    config_path = os.path.join(os.getcwd(), "configs", "working_cfg.json")
    config_manager = ConfigManager(config_path)

    # ----- Setup Paths -----
    path_config = setup_paths(config_manager)
    cwd = path_config.get('game_folder', os.path.join(os.getcwd(), "game"))
    log_folder = path_config.get('log_folder', os.path.join(cwd, "logs"))
    game_folder = path_config.get('saved_games_folder', os.path.join(cwd, "saved_games"))

    # ----- Current date -----
    dt_now = datetime.now().strftime("%Y-%m-%d")

    # ----- Set up the log stream into a file -----
    log_stream_file = os.path.join(log_folder, f"game-log_{dt_now}.log")
    logger = set_logger(level=logging.INFO, output=log_stream_file)
    logger.info(f"{'-' * 10} Starting new game /{dt_now}/ {'-' * 10}")

    # ----- Load environment variables -----
    dotenv_path = config_manager.config.get('dotenv_path', '/ext4/proj/2025/gen-ai_game/.env')
    load_dotenv(dotenv_path=dotenv_path)
    logger.info(f"Loaded dotenv file from {dotenv_path}")

    # ----- Setup LLMs -----
    llm_clients = setup_llms(config_manager)
    lore_llm = llm_clients['lore_llm']
    npc_ai_llm = llm_clients['npc_ai_llm']
    game_ai_llm = llm_clients['game_ai_llm']
    input_validator_llm = llm_clients.get('input_validator', None)

    # ----- Get LLM-specific parameters -----
    lore_llm_kw = config_manager.get_llm_config('lore_llm').get("props", None)
    npc_llm_kw = config_manager.get_llm_config('npc_ai_llm').get("props", None)
    game_ai_llm_kw = config_manager.get_llm_config('game_ai_llm').get("props", None)
    input_validator_kw = config_manager.get_llm_config('input_validator').get("props", None)
    llms_kwargs = {
        "lore_llm": lore_llm_kw,
        "npc_ai_llm": npc_llm_kw,
        "game_ai_llm": game_ai_llm_kw,
        "input_validator": input_validator_kw
    }

    # ----- Game IO ----
    game_io = IO(game_folder)

    # ----- UI -----
    console_manager = ConsoleManager()


    if not TEST_CHAT_UI:
        # ----- Main menu -----
        main_menu = GameMenu(console_manager, game_io)
        result = main_menu.main_menu()
        game_lore = {}

        if result['new_game']:
            logger.info(f"Generating new game")
            console_manager.console.print(f"{'=' * 15} Generating the new game {'=' * 15}")
            _ = game_io.add_new_game()
            game_id = game_io.id
            game_folder = game_io.dst
            memory_db_path = os.path.join(game_folder, "memory.sql")
            logger.info(f"Game folder: {game_folder}")
            logger.info(f"Game memory db will be located at {memory_db_path}")

            # Get lore generation parameters from config and user input
            lore_config = get_lore_generation_params(config_manager, result['new_game_params'])

            game_lore_raw = GenerateLore(lore_llm, lore_config, game_folder, console_manager, **lore_llm_kw)

            # add description to the game
            cond = game_io.games['id'] == game_id
            game_io.games.loc[
                cond, 'description'] = f"{game_lore_raw['world']['name']} -- {game_lore_raw['world']['description']}"
            game_io.save_games()

            # populating the memory
            enable_memory = config_manager.get_game_config().get('enable_memory', True)
            game_lore, memory = init_memory_lore(game_lore_raw, memory_db_path, not enable_memory)
            console_manager.console.print(f"{'=' * 15} Ready! {'=' * 15}")

        if not result['new_game'] and result['load_game'] >= 0:
            logger.info(f"Loading the game")
            row_num = result['load_game']
            _row = game_io.games.iloc[row_num]
            game_id = _row['id']
            game_folder = _row['folder']
            memory_db_path = os.path.join(game_folder, "memory.sql")

            with open(os.path.join(game_folder, "lore.json"), 'r') as f:
                game_lore_raw = json.load(f)

            game_lore, memory = init_memory_lore(game_lore_raw, memory_db_path, True)

        console_manager.console.print(game_lore)

    if TEST_CHAT_UI:

        # TODO: Continue with chat interface setup...
        chat_interface = RPGChatInterface(console_manager)
        chat_interface.register_command_hooks(stack="user_input",
                                              handler=user_input_process_mock,
                                              command="process_input")

        chat_interface.register_command_hooks(stack="user_input",
                                              handler=ai_response_mock,
                                              command="ai_response")

        chat_interface.register_command_hooks(stack="post_processing",
                                              handler=lambda x: x,
                                              command="exit")


        #chat_interface.user_input_process_mock = custom_input_processor
        #chat_interface.generate_response = custom_response_generator

        chat_interface.start()

        #console_manager.console.clear()
