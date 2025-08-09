"""
Classes to address I/O operations

This class keeps track of all games and folders for each session.
Each subfolder is intended to keep
- lore
- game state database
- anything deemed necessary in future developments
"""

import os, pickle, json
import pandas as pd
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import logging
logger = logging.getLogger(__name__)

class IO:
    """
    Error codes:
        0 : success
        1: id not found (when setting/searching for an id)
        2: saving has failed
    """
    def __init__(self, workdir):
        if not os.path.exists(workdir):
            logger.warning(f"\"{workdir}\" does not exist")
            os.makedirs(workdir, exist_ok=True)
        # folder for all games
        self.workdir = workdir
        # current game id
        self.id = ""
        # current saving destination (full path)
        self.dst = ""

        # reading/setting up games tracker
        # it tracks all game sessions
        # and where the respective game files are saved
        if os.path.exists(os.path.join(self.workdir, "games.json")):
            logger.info(f"Found saved games, reading")
            self.games = pd.read_json(os.path.join(self.workdir, "games.json"))
            self.games['datetime_utc'] = pd.to_datetime(self.games['datetime_utc'], unit='ms', utc=True)
            logger.info(f"Done. Setting current game to the latest")
            _t = self.games.sort_values(by='datetime_utc', ascending=False)
            self.id = _t.iloc[0]['id']
            self.dst = _t.iloc[0]['folder']
            logger.info(f"Setting the current game id to {self.id}")
            logger.info(f"Save destination: {self.dst}")
        else:
            logger.warning(f"No previous games were found, starting a new one.")
            self.games = self.__new_game()
            _id = self.games['id'].values.tolist()[0]
            _ = self.set_game_id(_id)
            os.makedirs(self.dst, exist_ok=True)
            self.games.to_json(os.path.join(self.workdir, "games.json"), indent=4)


    def __save_games(self) -> int:
        """
        Saves the games tracker self.games
        :return: int (error code)
        """
        try:
            _fname = os.path.join(self.workdir, "games.json")
            self.games.to_json(_fname, indent=4)
            logger.info(f"Saved the game sessions tracker to \"{_fname}\"")
            return 1
        except Exception as e:
            logger.error(f"When saving the game tracker to \"{_fname}\" encountered error: \"{e}\"")
            return 2


    def __new_game(self) -> pd.DataFrame:
        """
        Creates a new game DataFrame
        :return: pd.DataFrame
        """
        _id = uuid4().hex
        _dst = os.path.join(self.workdir, _id)
        return pd.DataFrame([{
                'id': _id,
                'datetime_utc': datetime.now(tz=timezone.utc),
                'description': "",
                'folder': _dst
            }])


    def add_new_game(self):
        """
        Adds a new game session to the tracker.
        It will also create the corresponding folder
        and set the self.id and self.folder to the new values
        :return:
        """
        _new_game = self.__new_game()
        _id = self.games['id'].values.tolist()[0]
        _dst = _new_game['folder'].values[0]
        _ = self.set_game_id(_id)
        os.makedirs(self.dst, exist_ok=True)
        self.games = pd.concat([self.games, _new_game], axis=0, ignore_index=True)
        _response = self.__save_games()


    def get_all_games(self):
        return self.games


    def set_game_id(self, id:str) -> int:
        ids = self.games['id'].values.tolist()
        if id in ids:
            _df_idx = self.games['id'] == id
            self.id = id
            self.dst = self.games[_df_idx]['folder'].values[0]
            logger.info(f"Setting the game id to {self.id}")
            logger.info(f"Save destination: {self.dst}")
            return 0
        else:
            logger.warning(f"\"{id}\" is not found within valid game ids. Skipping")
            return 1 # invalid game id