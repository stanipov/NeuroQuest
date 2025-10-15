import json
import os
import sys
sys.path.append(os.getcwd())

from llm_rpg.engine.io import IO
from llm_rpg.gui.console_manager import ConsoleManager
from llm_rpg.gui.game_menu import GameMenu
from llm_rpg.gui.chat import RPGChatInterface, process_input_placeholder, placeholder_generate_response

from llm_rpg.app.lore_generator import GenerateLore
from llm_rpg.app.set_memory import init_memory_lore

from llm_rpg.clients.ollama import OllamaW
from llm_rpg.clients.deepseek import DeepSeekW_requests, DeepSeekW_OAI
from llm_rpg.clients.groq import GroqW

from  llm_rpg.utils.helpers import set_logger

from datetime import datetime
from dotenv import load_dotenv
import logging



# https://github.com/qnixsynapse/rich-chat/blob/main/source/rich-chat.py
if __name__ == "__main__":
    # ----- Load game parameters -----
    # ----- for testing purposes -----

    # ------------------------------------
    # CWD must be from the config
    cwd = os.path.join(os.getcwd(), "game")
    # ------------------------------------
    # These do not need to change:
    log_folder = os.path.join(cwd, "logs")
    game_folder = os.path.join(cwd, "saved_games")

    # ----- Create the log folder -----
    for fld in [game_folder, log_folder]:
        os.makedirs(fld, exist_ok=True)

    # ----- Current date -----
    dt_now = datetime.now().strftime("%Y-%m-%d")

    # ----- Set up the log stream into a file -----
    log_stream_file = os.path.join(log_folder, f"game-log_{dt_now}.log")
    logger = set_logger(level=logging.INFO, output=log_stream_file)
    logger.info(f"{'-' * 10} Starting new game /{dt_now}/ {'-' * 10}")

    # ----- Load dontenv file -----
    load_dotenv(dotenv_path="/ext4/proj/2025/gen-ai_game/.env")
    logger.info(f"Loaded dotenv file")

    # ----- LLM API keys -----
    # to be replaced by a config reading, see # ----- LLMs -----
    deepseek_api = os.environ.get("DEEP_SEEK_API_KEY")
    groq_api = os.environ.get("GROQ_API_KEY", '')

    # ----- Set up the components -----

    # ---------------------------------------------------
    # This also has to be configurable:
    # ----- LLMs -----
    deepseek_model = "deepseek-chat"
    groq_model = "openai/gpt-oss-120b"
    # lore_llm -- shall be controlled in a config via "lore_llm_provider" -- deepseek, grow, local
    # same goes for npc_ai_llm and game_ai_llm -- the idea that a user will be able to set different LLMs for different tasks
    # user also specifies api keys in the same place, e.g.
    # "lore_llm_provider" : {"model": ...., "api_key": ....} -- these must be properly parsed and instantiated
    # the same thing shall be done for npc_ai_llm and game_ai_llm
    # depending on what is lore_llm_provider, npc_ai_llm_provider, game_ai_llm_provider
    # you instantiate proper instance, like it is done below
    lore_llm = DeepSeekW_OAI(deepseek_model, deepseek_api)
    npc_ai_llm = GroqW(groq_model, groq_api, temperature=0.5)
    game_ai_llm = GroqW(groq_model, groq_api, temperature=0.5)
    # ---------------------------------------------------

    # ---------------------------------------------------
    # llm configs: must be read from the config also
    lore_llm_kw = {"temperature": 1.0}
    npc_llm_kw = {}
    game_ai_llm_kw = {}
    # ---------------------------------------------------

    # ----- Game IO ----
    game_io = IO(game_folder)

    # ----- UI -----
    console_manager = ConsoleManager()

    # ----- Dummy LLM -----
    from llm_rpg.clients.dummy_llm import DummyLLM
    llm_client = DummyLLM()

    # ----- Main menu -----
    main_menu = GameMenu(console_manager, game_io)
    result = main_menu.main_menu()
    game_lore = {}

    if result['new_game']:
        logger.info(f"Generating new game")
        console_manager.console.print(f"{'='*15} Generating the new game {'='*15}")
        _ = game_io.add_new_game()
        game_id = game_io.id
        game_folder = game_io.dst
        memory_db_path = os.path.join(game_folder, "memory.sql")
        logger.info(f"Game folder: {game_folder}")
        logger.info(f"Game memory db will be located at {memory_db_path}")
        lore_config = result['new_game_params']

        # -----------------------------------------
        # these must be defined into a config:
        lore_config['num_npc_rules'] = 10
        lore_config['sleep_sec'] = 0
        lore_config['api_delay'] = 0
        lore_config['num_world_rules'] = 10
        # ----------------------------------------

        game_lore_raw = GenerateLore(lore_llm, lore_config, game_folder, console_manager, **lore_llm_kw)

        # add description to the game
        cond = game_io.games['id'] == game_id
        game_io.games.loc[cond, 'description'] = f"{game_lore_raw['world']['name']} -- {game_lore_raw['world']['description']}"
        game_io.save_games()

        # populating the memory
        game_lore, memory = init_memory_lore(game_lore_raw, memory_db_path, False)
        console_manager.console.print(f"{'=' * 15} Ready! {'=' * 15}")

    if not result['new_game'] and result['load_game']>=0:
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






    # TODO: 1) new game creation -- DONE
    # TODO: 2) save the new game and proceed with the main events
    # TODO: 3) load the game and proceed with the main events
    # TODO: 4) instantiate the game ai class and pass its methods as relevant hooks for the chat_interface
    # TODO: The game ai class handles interactions with the user, memory, files, etc. Its components are called
    # as hooks from the UI. It also instantiates all needed classes: from memory to AI parts.
    # ? -- shall I make a dumb version of NPC for small and/or slow models?

    chat_interface = RPGChatInterface(console_manager)
    chat_interface.register_command_hooks(stack="user_input",
                                          handler=process_input_placeholder,
                                          command="process_input")

    chat_interface.register_command_hooks(stack="user_input",
                                          handler=placeholder_generate_response,
                                          command="ai_response")

    chat_interface.register_command_hooks(stack="post_processing",
                                          handler=lambda x: x,
                                          command="exit")


    # Customize processing if needed
    def custom_input_processor(input_text):
        return f"Processed: {input_text}"


    def custom_response_generator(processed_text):
        # Could use a different LLM wrapper here
        return DummyLLM().stream(processed_text)


    #chat_interface.process_input_placeholder = custom_input_processor
    #chat_interface.generate_response = custom_response_generator

    #chat_interface.start()

    #console_manager.console.clear()
