"""
Classes/methods to work with memory
"""

from itertools import cycle
from typing import List, Dict, Any, Type, Tuple

from sqlalchemy import or_, and_
from sqlalchemy import create_engine, Column, String, Text, MetaData, ForeignKey, Float, Integer, Table
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from sqlalchemy.inspection import inspect
from sqlalchemy import select

# ----------------------------- Module logging -----------------------------
import logging
logger = logging.getLogger(__name__)
# ----------------------------- Module logging -----------------------------

# ----------------------------- Message history -----------------------------
class MsgHistory:
    def __init__(self, starting_point: str, roles: List[str]):
        """
        Message history. The starting role will always be the first
        in the "roles" list because ordering of messages is important
        and these messages will be used as context and memory.

        The history is organized in lists of dictionaries:
        [
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}],
            ...

            ...
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}]
        ]
        roles: ['r1', 'r2'], and ordering is important.

        The class tracks the next role and will raise value error in case of the mismatch.
        This ensures 1) correct ordering 2) new list of message groups will be created automatically
        and correctly
        """

        self.__roles = cycle(roles)
        self.__roles_set = set(roles)
        self.__num_roles = len(roles)
        self.__history = [[{'role': next(self.__roles),
                            'message': starting_point}]]
        self.__next_fld = next(self.__roles)


    def add(self, msg: str, role: str) -> None:
        """
        Adds a message to the latest list of messages. If the
        target list is full, it will append and start with this role.
        :param msg: Textual message to save
        :param role: A role attributed to the message
        :return: None
        """
        if role not in self.__roles_set:
            raise ValueError(f"Got unexpected role \"{role}\"")

        if len(self.__history[-1]) >= self.__num_roles:
            self.__history.append([])

        if role != self.__next_fld:
            raise ValueError(f"Expected \"{self.__next_fld}\", got \"{role}\"")
        else:
            self.__history[-1].append({'role': role,
                                       'message': msg})
            self.__next_fld = next(self.__roles)

    def get_last_n(self, n) -> List[List[Dict[str, str]]]:
        return self.__history[-n:]

    def get_all_history(self) -> List[List[Dict[str, str]]]:
        return self.__history

    def get_num_msgs(self) -> int:
        return len(self.__history)

    def get_nex_role(self) -> List[str]:
        return self.__next_fld

# ----------------------------- SQLAlchemy memory adapted providing basic functionality -----------------------------
class Base(DeclarativeBase):
    pass

# Mapping from Python-friendly names to SQLAlchemy types
SQL_TYPE_MAP = {
    int: Integer,
    float: Float,
    str: String,
    "text": Text  # optional: allows explicit text column
}

class TableExists(Exception):
    """Exception raised for custom error scenarios.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class SQLMemory:
    def __init__(self, db_path: str):
        self.Base = type("Base", (DeclarativeBase,), {})
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.Session = sessionmaker(bind=self.engine)
        self.models: Dict[str, Any] = {}

        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

        if not self.metadata.tables:
            logger.info(f"Database at \"{db_path}\" contains no tables")
        else:
            logger.info(f"Loading tables metadata for \"{db_path}\" database")
            for tbl_name, tbl in self.metadata.tables.items():
                model = type(f"{tbl_name.capitalize()}Model",
                             (self.Base,),
                             {
                                 "__table__": tbl,
                                 "__tablename__": tbl_name,
                                 "__table_args__": {"extend_existing": True}
                             }
                             )
                self.models[tbl_name] = model
            logger.info(f"Loaded {len(self.models)} existing table(s): {list(self.models.keys())}")

    def create_table(self,
                     table_name: str,
                     columns: Dict[str, Any],
                     primary_keys: List[str],
                     index_keys=None,
                     foreign_keys: Dict[str, str] = None) -> None:
        """
        Creates a dynamic ORM model for a table and registers it with the database.
        :param table_name: str -- table name
        :param columns: Dict[str, str] -- dictionary containing column names and their datatypes
        :param primary_keys: List[srt] -- list of primary keys
        :param index_keys: List[str] -- list of index columns, optional
        :param foreign_keys: Dict[str, str] -- dictionary of foreign keys (names and their data types)
        :return: None
        """
        if index_keys is None:
            index_keys = []
        if table_name not in self.models:
            sqlalchemy_columns = []

            for col_name, col_dtype in columns.items():
                col_dtype_mapped = SQL_TYPE_MAP.get(col_dtype, String)
                is_pk = col_name in primary_keys
                is_index = col_name in index_keys

                if foreign_keys and col_name in foreign_keys:
                    sqlalchemy_columns.append(Column(col_name, col_dtype_mapped,
                                                     ForeignKey(foreign_keys[col_name]),
                                                     primary_key=is_pk, index=is_index))
                else:
                    sqlalchemy_columns.append(Column(col_name, col_dtype_mapped,
                                                     primary_key=is_pk,
                                                     index=is_index))

            # Create table and ORM model
            table = Table(table_name, self.metadata, *sqlalchemy_columns)
            self.metadata.create_all(self.engine, tables=[table])

            # Create dynamic ORM model
            attrs = {'__tablename__': table_name, '__table__': table, "__table_args__": {"extend_existing": True}}
            model = type(f"{table_name.capitalize()}Model", (self.Base,), attrs)
            self.models[table_name] = model
        else:
            logger.error(f"Table \"{table_name}\" already exists!")
            raise TableExists(f"Table \"{table_name}\" already exists!")


    def add_row(self, table_name: str, row: Dict[str, Any], strict: bool=True):
        """
        Adds row to a table.
        :param table_name: str -- table name to add data.
        :param row: Dict[str, Any] -- data to add.
        :param strict: bool -- will enforce of primary keys in the input data. Default: True.
        :return: None
        """
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return

        model = self.models[table_name]

        # check the input data contains primary keys
        if strict:
            pk_columns = [key.name for key in inspect(model).primary_key]
            if not all(pk in row for pk in pk_columns):
                raise KeyError(f"Missing primary key fields: expected {pk_columns}, got {list(row.keys())}")

        with self.Session() as session:
            obj = model(**row)
            session.add(obj)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                raise e


    def update_row(self, table_name: str,
                   row: Dict[str, Any],
                   strict: bool=True) -> None:
        """
        Updates an entry in the table. Strict mode is recommended.

        :param table_name: str -- table name.
        :param row: Dict[str, Any] -- row to update. If strict==True, the row[] must contain all primary keys.
                                      The row can contain only the column to update (but must contain the primary keys
                                      in strict mode)
        :param strict: bool -- will enforce of primary keys in the input data. Default: True.
        :return: None
        """
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return
        model = self.models[table_name]
        pk_columns = self.primary_keys(table_name)

        if strict and pk_columns and not all(pk in row for pk in pk_columns):
            raise KeyError(f"Missing primary key fields: expected {pk_columns}, got {list(row.keys())}")

        with self.Session() as session:
            try:
                if pk_columns:
                    # Use PK to find the row
                    pk_filter = {pk: row[pk] for pk in pk_columns}
                    obj = session.query(model).filter_by(**pk_filter).one_or_none()
                else:
                    # No PKs: use first row that matches all fields in `row`
                    filter_fields = {k: v for k, v in row.items()}
                    obj = session.query(model).filter_by(**filter_fields).first()

                # Update the fields
                for key, value in row.items():
                    if key not in pk_columns:
                        setattr(obj, key, value)
                session.commit()

            except Exception as e:
                session.rollback()
                raise e


    def get_last_n_rows(self, table_name: str, n: int) -> List[Dict[str, Any]]:
        """
        Returns last N entries from a table.
        :param table_name: str -- table name to query.
        :param n: int -- last N rows to return.
        :return: List[Dict[str, Any]].
        """

        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return []
        model = self.models[table_name]

        result = []
        with self.Session() as session:
            try:
                pk_columns = self.primary_keys(table_name)
                query = session.query(model).order_by(*[getattr(model, col).desc() for col in pk_columns]).limit(n)
                for item in query.all():
                    result.append({col.name: getattr(item, col.name) for col in model.__table__.columns})
            except Exception as e:
                logger.error(e)

        return result


    def remove_rows(self, table_name: str, pk_rows: List[Dict[str, Any]]):
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return

        model = self.models[table_name]
        pk_columns = self.primary_keys(table_name)
        # Validate that all primary keys are present in the input
        for pk_dict in pk_rows:
            if not all(pk in pk_dict for pk in pk_columns):
                raise KeyError(f"Missing primary key fields: expected {pk_columns}, got {list(pk_dict.keys())}")

        with self.Session() as session:
            try:
                # Build query
                obj = session.query(model).filter_by(**{pk: pk_dict[pk] for pk in pk_columns}).one_or_none()
                if obj:
                    session.delete(obj)
                else:
                    logger.warning(f"No row found in \"{table_name}\" matching PK {pk_dict}")
                session.commit()
            except Exception as e:
                session.rollback()
                raise e


    def primary_keys(self, table_name) -> List[str]:
        """
        Returns list of primary keys in a table
        :param table_name: str -- table name
        :return: List[str] -- list of primary keys for a table if table exists
        """

        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return []

        model = self.models[table_name]
        return [key.name for key in inspect(model).primary_key]


    def query_rows_by_keys(self,
                           table_name: str,
                           keys_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Queries a table over columns and their values. Expected input
        [
            {"key_1": val_1_1,...,"key_N": val_N_1},
            ...
            {"key_1": val_1_K,...,"key_N": val_N_K}
        ]
        Where N -- number of values, K - number of different queries. This is equivalent to
            SELECT
                key_1,
                ...,
                key_N
            FROM
                table
            WHERE
                (key_1 = val_1_1
                AND
                ...
                key_N = val_N_1)
                OR
                ...
                OR
                (key_1 = val_1_K
                AND
                ...
                key_N = val_N_K)
        Example usage:
        [
            {"turn": 10},
            {"turn": 11},
        ]

        :param table_name: str -- table name
        :param keys_list: List[Dict[str, Any]] -- columns and their values to query
        :return:
        """
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return []

        model = self.models[table_name]
        results = []

        with self.Session() as session:
            try:
                # OR of all AND conditions
                all_filters = [
                    and_(*[getattr(model, k) == v for k, v in key_dict.items()])
                    for key_dict in keys_list]
                query = session.query(model).filter(or_(*all_filters))
                matched_rows = query.all()
                results = [{col.name: getattr(row, col.name) for col in model.__table__.columns}
                           for row in matched_rows]
            except Exception as e:
                logger.error(f"Error querying table \"{table_name}\": {e}")
                raise e

        return results

    def list_all_rows(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Returns all rows from a table as a list of dictionaries.

        :param table_name: str -- table name to query
        :return: List[Dict[str, Any]] -- list of all rows, each row as a dictionary
        """
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return []

        model = self.models[table_name]
        result = []

        with self.Session() as session:
            try:
                query = session.query(model)
                for item in query.all():
                    result.append({col.name: getattr(item, col.name) for col in model.__table__.columns})
            except Exception as e:
                logger.error(f"Error listing all rows from table \"{table_name}\": {e}")

        return result

# ----------------------------- Memory for the game -----------------------------
# RAG augmented memory is planned
from llm_rpg.prompts.lore_generation import OBJECT_DESC
class SQLGameMemory(SQLMemory):
    def __init__(self, db_path, npc_names: List[str] = []):
        """
        Inits/loads all relevant tables. Below is a complete list of tables used in the game.

        Inventory:
            character: str: Player/NPC name
            item: str: item name, e.g. "axe", etc.
            count: int: count of the items
            -- primary keys: character, item

        Items:
            item: str: name of the item
            description: str: item description
            type: str: type of item, e.g. weapon/armor/...
            action: str: how the item works
            strength: str: effect of the item
            -- primary key: item

        History:
            turn: int -- game turn, always starts from AI response
            ai_response: str -- game response on joint actions of a human and npcs, i.e. it follows all these
            human_response: str -- human response;  it is assumed that the response is valid, i.e. you must validate it before
            <npc_1 name> -- utterance/actions of the NPC_1, will be always name of the NPC character
            ...
            <npc_N name> --utterance/actions of the NPC_N, will be always name of the NPC character

        Location history:
            The table tracks current locations along with destinations. Players can be in a current Loc 1 and decide on
            the same turn to relocate to Loc 2. While they do it, they might fail. Capturing the current location and the
            intended location will help the game logic to track locations correctly

            "turn": int  -- game turn, always starts from AI response
            "player": str -- player's name (human or NPC names)
            "kingdom": str -- Kindgom name
            "town": str -- town name
            "other": str -- any additional clarifications, e.g. townhall, swamp, etc.
            "status": str -- current or planned location.

        Player state:
            "player": str -- player name (human or NPC name)
            "alive": bool -- alive or dead
            "mental": str -- mental state (e.g. depressed, alert, etc.)
            "physical": str -- physical state (e.g. fresh, wounded, etc.)

        :return: None
        """
        super().__init__(db_path)

        # ----------- Inventory table -----------
        self.inventory_schema = {
            "character": str,
            "item": str,
            "count": float
        }
        self.inventory_pk = ["character", "item"]
        self.inventory_tbl_name = "inventory"

        # ----------- Items table -----------
        self.items_schema = {
            "name": str,
        }
        for x in OBJECT_DESC.keys():
            self.items_schema[x] = str
        self.items_pk = ['name']
        self.items_tbl_name = "items"

        # ----------- History table -----------
        self.history_schema = {"turn": int,
                               "ai_response": str,
                               "human_response": str}
        if npc_names != [] or npc_names is not None:
            for npc_name in npc_names:
                self.history_schema[npc_name] = str
        self.history_pk = ['turn']
        self.history_tbl_name = 'history'

        # ----------- Location history table -----------
        self.locations_tbl_name = "location_hist"
        self.locations_tbl_shema = {
            "turn": int,
            "player": str,
            "kingdom": str,
            "town": str,
            "other": str,
            "status": str
        }
        self.locations_tbl_pk = ["turn", "player"]

        # ----------- Player's state table -----------
        self.players_state_tbl_name = "players_state"
        self.players_state_tbl_schema = {
            "player": str,
            "alive": bool,
            "mental": str,
            "physical": str
        }
        self.players_state_tbl_pk = ["player"]

        if self.inventory_tbl_name not in self.models:
            logger.info(f"Creating the \"{self.inventory_tbl_name}\" table")
            self.create_table(table_name=self.inventory_tbl_name,
                              columns=self.inventory_schema,
                              primary_keys=self.inventory_pk,
                              index_keys=[],
                              foreign_keys=None)

        if self.items_tbl_name not in self.models:
            logger.info(f"Creating the \"{self.items_tbl_name}\" table")
            self.create_table(table_name=self.items_tbl_name,
                              columns=self.items_schema,
                              primary_keys=self.items_pk,
                              index_keys=[],
                              foreign_keys=None)

        if self.history_tbl_name not in self.models:
            logger.info(f"Creating the \"{self.history_tbl_name}\" table")
            self.create_table(table_name=self.history_tbl_name,
                              columns=self.history_schema,
                              primary_keys=self.history_pk,
                              index_keys=self.history_pk)

        if self.locations_tbl_name not in self.models:
            logger.info(f"Creating the \"{self.locations_tbl_name}\" table")
            self.create_table(table_name=self.locations_tbl_name,
                              columns=self.locations_tbl_shema,
                              primary_keys=self.locations_tbl_pk)

        if self.players_state_tbl_name not in self.models:
            logger.info(f"Creating the \"{self.players_state_tbl_name}\" table")
            self.create_table(table_name=self.players_state_tbl_name,
                              columns=self.players_state_tbl_schema,
                              primary_keys=self.players_state_tbl_pk)


    def add_inventory_items(self, character: str,
                            items: Dict[str, int],
                            items_lut: Dict[str, Dict[str, str]]):
        """
        Adds items to the inventory alongside with items LUT
        :param character: character name
        :param items: Dict[str, int] -- items to add along with their count
        :param items_lut: Dict[str, Dict[str, str]] -- LUT as provided by ObjectDescriptor.describe() method.
        :return: None
        """

        for item in items:
            row = {
                "character": character,
                "item": item,
                "count": items[item]
            }
            try:
                self.add_row(self.inventory_tbl_name, row, strict=True)
            except Exception as e:
                if not "UNIQUE constraint failed" in str(e):
                    raise e
                else:
                    logger.debug(f"{item} exists in the \"{self.inventory_tbl_name}\" table, skipping")
                    logger.debug(f"Full error: {item}: {e}")

        for item in items_lut:
            row = {
                "name": item
            }
            for x in self.items_schema:
                if x != 'name':
                    row[x] = items_lut[item][x]
            try:
                self.add_row(self.items_tbl_name, row, strict=True)
            except Exception as e:
                if not "UNIQUE constraint failed" in str(e):
                    raise e
                else:
                    logger.debug(f"{item} exists in the \"{self.items_tbl_name}\" table, skipping")
                    logger.debug(f"Full error: {item}: {e}")


    def remove_inventory_items(self, character: str, items: List[str]):
        """
        Removes inventory items in the inventory and the items tables

        :param character: character to remove items for
        :param items: list of items to remove
        :return:
        """
        rows2del_inventory = []
        rows2del_items = []
        # Yes, this is hardcoded
        for item in items:
            rows2del_inventory.append({
                "character": character,
                "item": item})
            rows2del_items.append({"name": item})

        # 1. inventory table
        self.remove_rows(self.inventory_tbl_name, rows2del_inventory)
        # 2. items table
        self.remove_rows(self.items_tbl_name, rows2del_items)


    def update_inventory_item(self, item: Dict[str, Any]):
        """
        Updates the count of an inventory item for a specific character.

        :param item: Dict[str, Any] -- {
            "item": item name,
            "count_change": change in count (can be positive or negative),
            "character": character name
        }
        :return: None
        """
        # Validate required fields
        required_fields = ["item", "count_change", "character"]
        if not all(field in item for field in required_fields):
            raise ValueError(f"Missing required fields. Expected: {required_fields}, got: {list(item.keys())}")

        character = item["character"]
        item_name = item["item"]
        count_change = item["count_change"]

        # Check if the item exists in the inventory for this character
        existing_items = self.query_rows_by_keys(
            self.inventory_tbl_name,
            [{"character": character, "item": item_name}]
        )

        if existing_items:
            # Item exists, update the count
            current_count = existing_items[0]["count"]
            new_count = current_count + count_change

            update_data = {
                "character": character,
                "item": item_name,
                "count": new_count
            }

            self.update_row(self.inventory_tbl_name, update_data, strict=True)
            logger.debug(f"Updated {item_name} for {character}: {current_count} -> {new_count}")
        else:
            # Item doesn't exist, but we don't create new entries if not present
            logger.warning(
                f"Item '{item_name}' not found in inventory for character '{character}'. No update performed.")


    def get_inventory_items(self, character: str) -> List[Dict[str, Any]]:
        """Returns all inventory items along with their description"""
        result = []
        inventory = self.models[self.inventory_tbl_name].__table__
        items = self.models[self.items_tbl_name].__table__
        with self.Session() as session:
            inv_columns = [inventory.c[col.name] for col in inventory.columns]
            item_columns = [col for col in items.columns if col.name != "name"]
            stmt = (
                select(*inv_columns, *item_columns)
                .join(items, inventory.c.item == items.c.name)
                .where(inventory.c.character == character)
                .where(inventory.c.count>0)
            )
            ans = session.execute(stmt)
            for row in ans:
                result.append(dict(row._mapping))

        return result


    def list_inventory_items(self, character: str) -> List[str]:
        """Lists all inventory items for a character (no details returned)"""
        items = []
        for x in self.get_inventory_items(character):
            items.append(x['item'])
        return items


    def get_most_recent_turn(self) -> Tuple[int, bool]:
        """
        Finds the latest turn number in the self.history_tbl_name
        :return: int -- last registered turn in the self.history_tbl_name
        """
        # read the DB to find the latest turn number
        last_row = self.get_last_n_rows(self.history_tbl_name, 1)
        if last_row != []:
            turn = last_row[0]['turn']
        else:
            logger.info(f"No rows found in \"{self.history_tbl_name}\" table. Setting \"turn\" to 0")
            turn = 0
        return turn, last_row != []


    def add_new_turn(self, messages: List[Dict[str, Any]], turn: int = -1):
        """
        Adds a new message to the "messages" table. If turn is not provided, it will be inferred from the DB.
        Messages must follow standard OpenAI-type:
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}]
        Here:
            - 'role' either 'ai_response', 'human_response', or <actual NPC name>
            - 'message' -- role's utterance

        :param messages:
        :param turn:
        :return:
        """
        # "turn" is a primary key for the messages table
        if turn == -1:
            turn, last_row_not_empty = self.get_most_recent_turn()
            if last_row_not_empty != []:
                turn += 1

        row = {'turn': turn}
        logger.debug(f"Game turn: {turn}")
        for msg in messages:
            if msg['role'] not in self.history_schema:
                logger.error(f"{msg['role']} is not within acceptable schema!")
                raise ValueError(f"{msg['role']} is not within acceptable schema!")

            row[msg['role']] = msg['message']
        self.add_row(self.history_tbl_name, row, True)


    def update_turn(self, messages: List[Dict[str, Any]], turn: int = -1):
        """
        Updates the turn. If turn is not provided, it will be inferred from the DB.
        Messages must follow standard OpenAI-type:
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}]
        Here:
            - 'role' either 'ai_response', 'human_response', or <actual NPC name>
            - 'message' -- 'role' utterance

        :param message:
        :param turn:
        :return:
        """

        # "turn" is a primary key for the messages table
        if turn == -1:
            # read the DB to find the latest turn number
            turn, _ = self.get_most_recent_turn()

        _strict = True
        row = {
            'turn': turn
        }

        for msg in messages:
            if msg['role'] not in self.history_schema:
                logger.error(f"{msg['role']} is not within acceptable schema!")
                raise ValueError(f"{msg['role']} is not within acceptable schema!")

            row[msg['role']] = msg['message']

        self.update_row(self.history_tbl_name, row, _strict)