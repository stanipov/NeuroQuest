"""
Classes/methods to work with memory
"""

from itertools import cycle
from typing import List, Dict, Any, Tuple, Callable
import re
from sqlalchemy import text

from sqlalchemy import or_, and_
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    MetaData,
    ForeignKey,
    Float,
    Integer,
    Table,
)
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
        self.__history = [[{"role": next(self.__roles), "message": starting_point}]]
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
            raise ValueError(f'Got unexpected role "{role}"')

        if len(self.__history[-1]) >= self.__num_roles:
            self.__history.append([])

        if role != self.__next_fld:
            raise ValueError(f'Expected "{self.__next_fld}", got "{role}"')
        else:
            self.__history[-1].append({"role": role, "message": msg})
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
    "text": Text,  # optional: allows explicit text column
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
            logger.info(f'Database at "{db_path}" contains no tables')
        else:
            logger.info(f'Loading tables metadata for "{db_path}" database')
            for tbl_name, tbl in self.metadata.tables.items():
                model = type(
                    f"{tbl_name.capitalize()}Model",
                    (self.Base,),
                    {
                        "__table__": tbl,
                        "__tablename__": tbl_name,
                        "__table_args__": {"extend_existing": True},
                    },
                )
                self.models[tbl_name] = model
            logger.info(
                f"Loaded {len(self.models)} existing table(s): {list(self.models.keys())}"
            )

    def create_table(
        self,
        table_name: str,
        columns: Dict[str, Any],
        primary_keys: List[str],
        index_keys=None,
        foreign_keys: Dict[str, str] = None,
    ) -> None:
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
                    sqlalchemy_columns.append(
                        Column(
                            col_name,
                            col_dtype_mapped,
                            ForeignKey(foreign_keys[col_name]),
                            primary_key=is_pk,
                            index=is_index,
                        )
                    )
                else:
                    sqlalchemy_columns.append(
                        Column(
                            col_name,
                            col_dtype_mapped,
                            primary_key=is_pk,
                            index=is_index,
                        )
                    )

            # Create table and ORM model
            table = Table(table_name, self.metadata, *sqlalchemy_columns)
            self.metadata.create_all(self.engine, tables=[table])

            # Create dynamic ORM model
            attrs = {
                "__tablename__": table_name,
                "__table__": table,
                "__table_args__": {"extend_existing": True},
            }
            model = type(f"{table_name.capitalize()}Model", (self.Base,), attrs)
            self.models[table_name] = model
        else:
            logger.error(f'Table "{table_name}" already exists!')
            raise TableExists(f'Table "{table_name}" already exists!')

    def add_row(self, table_name: str, row: Dict[str, Any], strict: bool = True):
        """
        Adds row to a table.
        :param table_name: str -- table name to add data.
        :param row: Dict[str, Any] -- data to add.
        :param strict: bool -- will enforce of primary keys in the input data. Default: True.
        :return: None
        """
        if table_name not in self.models:
            logger.warning(f'"{table_name}" is not found!')
            return

        model = self.models[table_name]

        # check the input data contains primary keys
        if strict:
            pk_columns = [key.name for key in inspect(model).primary_key]
            if not all(pk in row for pk in pk_columns):
                raise KeyError(
                    f"Missing primary key fields: expected {pk_columns}, got {list(row.keys())}"
                )

        with self.Session() as session:
            obj = model(**row)
            session.add(obj)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                raise e

    def update_row(
        self, table_name: str, row: Dict[str, Any], strict: bool = True
    ) -> None:
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
            logger.warning(f'"{table_name}" is not found!')
            return
        model = self.models[table_name]
        pk_columns = self.primary_keys(table_name)

        if strict and pk_columns and not all(pk in row for pk in pk_columns):
            raise KeyError(
                f"Missing primary key fields: expected {pk_columns}, got {list(row.keys())}"
            )

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
            logger.warning(f'"{table_name}" is not found!')
            return []
        model = self.models[table_name]

        result = []
        with self.Session() as session:
            try:
                pk_columns = self.primary_keys(table_name)
                query = (
                    session.query(model)
                    .order_by(*[getattr(model, col).desc() for col in pk_columns])
                    .limit(n)
                )
                for item in query.all():
                    result.append(
                        {
                            col.name: getattr(item, col.name)
                            for col in model.__table__.columns
                        }
                    )
            except Exception as e:
                logger.error(e)

        return result

    def remove_rows(self, table_name: str, pk_rows: List[Dict[str, Any]]):
        if table_name not in self.models:
            logger.warning(f'"{table_name}" is not found!')
            return

        model = self.models[table_name]
        pk_columns = self.primary_keys(table_name)
        # Validate that all primary keys are present in the input
        for pk_dict in pk_rows:
            if not all(pk in pk_dict for pk in pk_columns):
                raise KeyError(
                    f"Missing primary key fields: expected {pk_columns}, got {list(pk_dict.keys())}"
                )

        with self.Session() as session:
            try:
                # Build query
                obj = (
                    session.query(model)
                    .filter_by(**{pk: pk_dict[pk] for pk in pk_columns})
                    .one_or_none()
                )
                if obj:
                    session.delete(obj)
                else:
                    logger.warning(
                        f'No row found in "{table_name}" matching PK {pk_dict}'
                    )
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
            logger.warning(f'"{table_name}" is not found!')
            return []

        model = self.models[table_name]
        return [key.name for key in inspect(model).primary_key]

    def query_rows_by_keys(
        self, table_name: str, keys_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            logger.warning(f'"{table_name}" is not found!')
            return []

        model = self.models[table_name]
        results = []

        with self.Session() as session:
            try:
                # OR of all AND conditions
                all_filters = [
                    and_(*[getattr(model, k) == v for k, v in key_dict.items()])
                    for key_dict in keys_list
                ]
                query = session.query(model).filter(or_(*all_filters))
                matched_rows = query.all()
                results = [
                    {
                        col.name: getattr(row, col.name)
                        for col in model.__table__.columns
                    }
                    for row in matched_rows
                ]
            except Exception as e:
                logger.error(f'Error querying table "{table_name}": {e}')
                raise e

        return results

    def list_all_rows(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Returns all rows from a table as a list of dictionaries.

        :param table_name: str -- table name to query
        :return: List[Dict[str, Any]] -- list of all rows, each row as a dictionary
        """
        if table_name not in self.models:
            logger.warning(f'"{table_name}" is not found!')
            return []

        model = self.models[table_name]
        result = []

        with self.Session() as session:
            try:
                query = session.query(model)
                for item in query.all():
                    result.append(
                        {
                            col.name: getattr(item, col.name)
                            for col in model.__table__.columns
                        }
                    )
            except Exception as e:
                logger.error(f'Error listing all rows from table "{table_name}": {e}')

        return result


# ----------------------------- Memory for the game -----------------------------
# RAG augmented memory is planned
from llm_rpg.prompts.response_models import InventoryItemDescription


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
        self.inventory_schema = {"character": str, "item": str, "count": float}
        self.inventory_pk = ["character", "item"]
        self.inventory_tbl_name = "inventory"

        # ----------- Items table -----------
        # Use Pydantic model fields to define schema (type-safe, self-documenting)
        self.items_schema = {
            field_name: str
            for field_name in InventoryItemDescription.model_fields.keys()
        }
        self.items_pk = ["name"]
        self.items_tbl_name = "items"

        # ----------- History table -----------
        self.history_schema = {"turn": int, "ai_response": str, "human_response": str}
        if npc_names != [] or npc_names is not None:
            for npc_name in npc_names:
                self.history_schema[npc_name] = str
        self.history_pk = ["turn"]
        self.history_tbl_name = "history"

        # ----------- Location history table -----------
        self.locations_tbl_name = "location_hist"
        self.locations_tbl_shema = {
            "turn": int,
            "player": str,
            "kingdom": str,
            "town": str,
            "other": str,
            "status": str,
        }
        self.locations_tbl_pk = ["turn", "player"]

        # ----------- Player's state table -----------
        self.players_state_tbl_name = "players_state"
        self.players_state_tbl_schema = {
            "player": str,
            "alive": bool,
            "mental": str,
            "physical": str,
        }
        self.players_state_tbl_pk = ["player"]

        # ----------- Non-game responses -----------
        self.game_knowledge_tbl_name = "knowledge"
        self.game_knowledge_tbl_schema = {
            "turn": int,
            "ai_response": str,
            "human_question": str,
        }
        self.game_knowledge_tbl_pk = ["turn"]

        if self.inventory_tbl_name not in self.models:
            logger.info(f'Creating the "{self.inventory_tbl_name}" table')
            self.create_table(
                table_name=self.inventory_tbl_name,
                columns=self.inventory_schema,
                primary_keys=self.inventory_pk,
                index_keys=[],
                foreign_keys=None,
            )

        if self.items_tbl_name not in self.models:
            logger.info(f'Creating the "{self.items_tbl_name}" table')
            self.create_table(
                table_name=self.items_tbl_name,
                columns=self.items_schema,
                primary_keys=self.items_pk,
                index_keys=[],
                foreign_keys=None,
            )

        if self.history_tbl_name not in self.models:
            logger.info(f'Creating the "{self.history_tbl_name}" table')
            self.create_table(
                table_name=self.history_tbl_name,
                columns=self.history_schema,
                primary_keys=self.history_pk,
                index_keys=self.history_pk,
            )

        if self.locations_tbl_name not in self.models:
            logger.info(f'Creating the "{self.locations_tbl_name}" table')
            self.create_table(
                table_name=self.locations_tbl_name,
                columns=self.locations_tbl_shema,
                primary_keys=self.locations_tbl_pk,
            )

        if self.players_state_tbl_name not in self.models:
            logger.info(f'Creating the "{self.players_state_tbl_name}" table')
            self.create_table(
                table_name=self.players_state_tbl_name,
                columns=self.players_state_tbl_schema,
                primary_keys=self.players_state_tbl_pk,
            )

        if self.game_knowledge_tbl_name not in self.models:
            logger.info(f'Creating the "{self.game_knowledge_tbl_name}" table')
            self.create_table(
                table_name=self.game_knowledge_tbl_name,
                columns=self.game_knowledge_tbl_schema,
                primary_keys=self.game_knowledge_tbl_pk,
            )

    def add_inventory_items(
        self,
        character: str,
        items: Dict[str, int],
        items_lut: Dict[str, Dict[str, str]],
    ):
        """
        Adds items to the inventory alongside with items LUT
        :param character: character name
        :param items: Dict[str, int] -- items to add along with their count
        :param items_lut: Dict[str, Dict[str, str]] -- LUT as provided by ObjectDescriptor.describe() method.
        :return: None
        """

        for item in items:
            row = {"character": character, "item": item, "count": items[item]}
            try:
                self.add_row(self.inventory_tbl_name, row, strict=True)
            except Exception as e:
                if not "UNIQUE constraint failed" in str(e):
                    raise e
                else:
                    logger.debug(
                        f'"{item}" exists in the "{self.inventory_tbl_name}" table, skipping'
                    )
                    logger.debug(f"Full error: {item}: {e}")

        for item in items_lut:
            row = {"name": item}
            for x in self.items_schema:
                if x != "name":
                    row[x] = items_lut[item][x]
            try:
                self.add_row(self.items_tbl_name, row, strict=True)
            except Exception as e:
                if not "UNIQUE constraint failed" in str(e):
                    raise e
                else:
                    logger.debug(
                        f'"{item}" exists in the "{self.items_tbl_name}" table, skipping'
                    )
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
            rows2del_inventory.append({"character": character, "item": item})
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
            raise ValueError(
                f"Missing required fields. Expected: {required_fields}, got: {list(item.keys())}"
            )

        character = item["character"]
        item_name = item["item"]
        count_change = item["count_change"]

        # Check if the item exists in the inventory for this character
        existing_items = self.query_rows_by_keys(
            self.inventory_tbl_name, [{"character": character, "item": item_name}]
        )

        if existing_items:
            # Item exists, update the count
            current_count = existing_items[0]["count"]
            new_count = current_count + count_change

            update_data = {
                "character": character,
                "item": item_name,
                "count": new_count,
            }

            self.update_row(self.inventory_tbl_name, update_data, strict=True)
            logger.debug(
                f"Updated {item_name} for {character}: {current_count} -> {new_count}"
            )
        else:
            # Item doesn't exist, but we don't create new entries if not present
            logger.warning(
                f"Item '{item_name}' not found in inventory for character '{character}'. No update performed."
            )

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
                .where(inventory.c.count > 0)
            )
            ans = session.execute(stmt)
            for row in ans:
                result.append(dict(row._mapping))

        return result

    def list_inventory_items(self, character: str) -> List[str]:
        """Lists all inventory items for a character (no details returned)"""
        items = []
        for x in self.get_inventory_items(character):
            items.append(x["item"])
        return items

    def get_most_recent_turn(self) -> Tuple[int, bool]:
        """
        Finds the latest turn number in the self.history_tbl_name
        :return: int -- last registered turn in the self.history_tbl_name
        """
        # read the DB to find the latest turn number
        last_row = self.get_last_n_rows(self.history_tbl_name, 1)
        if last_row != []:
            turn = last_row[0]["turn"]
        else:
            logger.info(
                f'No rows found in "{self.history_tbl_name}" table. Setting "turn" to 0'
            )
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

        row = {"turn": turn}
        logger.debug(f"Game turn: {turn}")
        for msg in messages:
            if msg["role"] not in self.history_schema:
                logger.error(f"{msg['role']} is not within acceptable schema!")
                raise ValueError(f"{msg['role']} is not within acceptable schema!")

            row[msg["role"]] = msg["message"]
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
        row = {"turn": turn}

        for msg in messages:
            if msg["role"] not in self.history_schema:
                logger.error(f"{msg['role']} is not within acceptable schema!")
                raise ValueError(f"{msg['role']} is not within acceptable schema!")

            row[msg["role"]] = msg["message"]

        self.update_row(self.history_tbl_name, row, _strict)


# =============================================================================
#                        R E F A C T O R E D   G A M E   M E M O R Y
# =============================================================================
# New unified GameMemory class using raw SQL via SQLAlchemy
# Replaces SQLMemory + SQLGameMemory functionality
# =============================================================================
class GameMemory:
    """
    Unified game memory management using raw SQL via SQLAlchemy.

    Tables:
        - location: (turn, character) PK - tracks character locations per turn
        - inventory: (character, item) PK - tracks items owned by characters
        - state: (turn, name) PK - tracks character physical/mental state per turn
        - game_history: turn PK - tracks game turns with user/NPC interactions
        - rejected_input: cnt PK - tracks rejected user inputs
        - npc_names_map: sanitized_name PK - maps sanitized names to original names
    """

    # Roles that indicate end of a turn (triggers new row creation)
    _TURN_ENDING_ROLES = {"game_action", "displayed_action", "compacted_history"}

    def __init__(
        self,
        db_path: str,
        llm_client: Callable,
        game_lore: Dict[str, Any],
        config: Dict[str, Any],
    ) -> None:
        """
        Initialize GameMemory.

        Args:
            db_path: Path to SQLite database file. If empty/non-existent, creates new DB.
            llm_client: LLM client callable from llm_rpg.templates.base_client
            game_lore: Generated game lore dictionary
            config: Game configuration dictionary
        """
        self.db_path = db_path
        self.llm_client = llm_client
        self.config = config

        # Initialize engine
        if db_path == "":
            self.engine = create_engine("sqlite:///:memory:")
        else:
            self.engine = create_engine(f"sqlite:///{db_path}")

        # NPC name mapping: sanitized -> original
        self._npc_mapping: Dict[str, str] = {}
        # NPC name mappings: original -> sanitized
        self._inverse_npc_mapping: Dict[str, str] = {}

        # Track if this is a new database
        self._is_new_db = False

        # Initialize database
        if db_path == "" or not self._table_exists("game_history"):
            self._is_new_db = True
            self._create_tables(game_lore)
            self._populate_initial_data(game_lore)
        else:
            self._load_npc_mapping()
            logger.info(f'Loaded existing database from "{db_path}"')

    # -------------------------------------------------------------------------
    #                           NPC NAME SANITIZATION
    # -------------------------------------------------------------------------

    def _sanitize_name_internal(self, name: str) -> str:
        """Convert 'Arin Darkhaven' → 'arin_darkhaven'"""
        sanitized = re.sub(r"[^a-zA-Z0-9]", "_", name).lower()
        sanitized = re.sub(r"_+", "_", sanitized)
        return sanitized.strip("_") or "npc"

    def sanitize_npc_name(self, name: str) -> str:
        """
        Convert original NPC name to sanitized column-safe name.
        Handles collisions by appending _1, _2, etc.

        Args:
            name: Original NPC name (e.g., 'Arin Darkhaven')

        Returns:
            Sanitized name (e.g., 'arin_darkhaven')
        """
        base_sanitized = self._sanitize_name_internal(name)

        # Check for collision and disambiguate
        if (
            base_sanitized in self._npc_mapping
            and self._npc_mapping[base_sanitized] != name
        ):
            counter = 1
            while f"{base_sanitized}_{counter}" in self._npc_mapping:
                counter += 1
            return f"{base_sanitized}_{counter}"
        return base_sanitized

    def restore_npc_name(self, sanitized: str) -> str:
        """
        Convert sanitized name back to original NPC name via DB lookup.

        Args:
            sanitized: Sanitized name (e.g., 'arin_darkhaven')

        Returns:
            Original name (e.g., 'Arin Darkhaven') or sanitized if not found
        """
        return self._npc_mapping.get(sanitized, sanitized)

    def get_npc_mapping(self) -> Dict[str, str]:
        """Return {sanitized: original} mapping"""
        return self._npc_mapping.copy()

    # -------------------------------------------------------------------------
    #                           INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        with self.engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
                ),
                {"name": table_name},
            )
            return result.first() is not None

    def _get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a table"""
        with self.engine.connect() as conn:
            result = conn.execute(text(f'PRAGMA table_info("{table_name}")'))
            return [row[1] for row in result]  # Column name is at index 1

    # -------------------------------------------------------------------------
    #                           TABLE CREATION
    # -------------------------------------------------------------------------

    def _create_tables(self, game_lore: Dict[str, Any]) -> None:
        """
        Orchestrates table creation process.

        Args:
            game_lore: Game lore dictionary containing NPC definitions
        """
        # Build NPC mappings first
        self._build_npc_mappings(game_lore)

        # Get NPC columns SQL for game_history
        npc_cols_sql = self._get_npc_columns_sql()

        # Define creation order (matters for dependencies)
        tables_to_create = [
            ("npc_names_map", self._build_npc_names_map_schema()),
            ("location", self._build_location_schema()),
            ("inventory", self._build_inventory_schema()),
            ("state", self._build_state_schema()),
            ("game_history", self._build_game_history_schema(npc_cols_sql)),
            ("rejected_input", self._build_rejected_input_schema()),
        ]

        # Create each table individually
        for table_name, schema_sql in tables_to_create:
            self._execute_table_creation(table_name, schema_sql)

    def _build_npc_mappings(self, game_lore: Dict[str, Any]) -> None:
        """
        Build and populate NPC name mappings from game lore.

        Populates self._npc_mapping and self._inverse_npc_mapping
        with sanitized ↔ original name pairs.

        Args:
            game_lore: Game lore dictionary containing 'npc' key
        """
        npc_names = list(game_lore.get("npc", {}).keys())

        for npc_name in npc_names:
            sanitized = self.sanitize_npc_name(npc_name)
            self._npc_mapping[sanitized] = npc_name
            self._inverse_npc_mapping[npc_name] = sanitized

        logger.info(f"Built NPC mappings for {len(npc_names)} NPCs")

    def _get_npc_columns_sql(self) -> str:
        """
        Generate NPC column definitions from existing mappings.

        Returns:
            String like: '"arin_darkhaven" TEXT, "dark_lord_malakor" TEXT'
            Or empty string if no NPCs
        """
        if not self._npc_mapping:
            return ""

        columns = [f'"{sanitized}" TEXT' for sanitized in self._npc_mapping.keys()]
        return ", ".join(columns)

    def _execute_table_creation(self, table_name: str, schema_sql: str) -> None:
        """
        Create a single table and optionally insert NPC mappings.

        Args:
            table_name: Name of table to create
            schema_sql: CREATE TABLE statement as string

        Special handling:
            If table_name == 'npc_names_map', also inserts NPC name mappings
            after table creation.
        """
        with self.engine.connect() as conn:
            # Create the table
            conn.execute(text(schema_sql))

            # Special case: populate npc_names_map right after creation
            if table_name == "npc_names_map" and self._inverse_npc_mapping:
                insert_stmt = text(
                    "INSERT INTO npc_names_map (sanitized_name, original_name) VALUES (:sanitized, :original)"
                )
                for npc_name in self._inverse_npc_mapping:
                    sanitized = self._inverse_npc_mapping[npc_name]
                    conn.execute(
                        insert_stmt, {"sanitized": sanitized, "original": npc_name}
                    )

            conn.commit()

        logger.info(f"Created table: {table_name}")

    def _build_npc_names_map_schema(self) -> str:
        """Return CREATE TABLE statement for npc_names_map"""
        return """CREATE TABLE npc_names_map (
            sanitized_name TEXT PRIMARY KEY,
            original_name TEXT NOT NULL UNIQUE
        )"""

    def _build_location_schema(self) -> str:
        """Return CREATE TABLE statement for location"""
        return """CREATE TABLE location (
            turn INTEGER NOT NULL,
            character TEXT NOT NULL,
            kingdom TEXT,
            town TEXT,
            details TEXT,
            PRIMARY KEY (turn, character)
        )"""

    def _build_inventory_schema(self) -> str:
        """Return CREATE TABLE statement for inventory"""
        return """CREATE TABLE inventory (
            character TEXT NOT NULL,
            item TEXT NOT NULL,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (character, item)
        )"""

    def _build_state_schema(self) -> str:
        """Return CREATE TABLE statement for state"""
        return """CREATE TABLE state (
            turn INTEGER NOT NULL,
            name TEXT NOT NULL,
            physical TEXT,
            mental TEXT,
            PRIMARY KEY (turn, name)
        )"""

    def _build_game_history_schema(self, npc_cols_sql: str) -> str:
        """
        Return CREATE TABLE statement for game_history.

        Args:
            npc_cols_sql: NPC column definitions (e.g., '"col1" TEXT, "col2" TEXT')
        """
        return f"""CREATE TABLE game_history (
            turn INTEGER PRIMARY KEY,
            user_input TEXT,
            game_action TEXT,
            displayed_action TEXT,
            compacted_history TEXT
            {f", {npc_cols_sql}" if npc_cols_sql else ""}
        )"""

    def _build_rejected_input_schema(self) -> str:
        """Return CREATE TABLE statement for rejected_input"""
        return """CREATE TABLE rejected_input (
            cnt INTEGER PRIMARY KEY AUTOINCREMENT,
            user_input TEXT NOT NULL,
            comment TEXT
        )"""

    # -------------------------------------------------------------------------
    #                           DATA POPULATION
    # -------------------------------------------------------------------------

    def _populate_initial_data(self, game_lore: Dict[str, Any]) -> None:
        """
        Orchestrates initial data population.

        Args:
            game_lore: Game lore dictionary containing initial data
        """
        self._insert_initial_game_history(game_lore)
        self._insert_initial_locations(game_lore)
        self._insert_initial_inventories(game_lore)
        logger.info("Initial data population complete")

    def _insert_initial_game_history(self, game_lore: Dict[str, Any]) -> None:
        """
        Insert initial game_history row (turn 0).

        Args:
            game_lore: Game lore dictionary containing 'start' key
        """
        start_message = game_lore.get("start", "")

        with self.engine.connect() as conn:
            conn.execute(
                text("""INSERT INTO game_history (turn, displayed_action, compacted_history) 
                       VALUES (0, :displayed_action, '')"""),
                {"displayed_action": start_message},
            )

            conn.commit()

        logger.info("Inserted initial game_history row")

    def _insert_initial_locations(self, game_lore: Dict[str, Any]) -> None:
        """
        Insert initial location data for human player and all NPCs.

        Args:
            game_lore: Game lore dictionary containing 'start_location' key
        """
        start_location = game_lore.get("start_location", {})

        with self.engine.connect() as conn:
            # Human player location
            human_loc = start_location.get("human", {})
            if human_loc:
                conn.execute(
                    text("""INSERT INTO location (turn, character, kingdom, town, details) 
                           VALUES (0, 'user', :kingdom, :town, '')"""),
                    {
                        "kingdom": human_loc.get("kingdom", ""),
                        "town": human_loc.get("town", ""),
                    },
                )

            # NPC locations
            npc_locations = start_location.get("npc", {})
            for npc_name, loc_data in npc_locations.items():
                conn.execute(
                    text("""INSERT INTO location (turn, character, kingdom, town, details) 
                           VALUES (0, :character, :kingdom, :town, '')"""),
                    {
                        "character": npc_name,
                        "kingdom": loc_data.get("kingdom", ""),
                        "town": loc_data.get("town", ""),
                    },
                )

            conn.commit()

        logger.info("Inserted initial location data")

    def _insert_initial_inventories(self, game_lore: Dict[str, Any]) -> None:
        """
        Insert initial inventory items for human player and all NPCs.

        Args:
            game_lore: Game lore dictionary containing 'human_player' and 'npc' keys
        """
        with self.engine.connect() as conn:
            # Human player inventory
            human_player = game_lore.get("human_player", {})
            human_inventory = human_player.get("inventory", [])
            for item in human_inventory:
                conn.execute(
                    text("""INSERT INTO inventory (character, item, count) 
                           VALUES ('user', :item, 1)"""),
                    {"item": item},
                )

            # Human player money
            human_money = human_player.get("money", 0)
            conn.execute(
                text("""INSERT INTO inventory (character, item, count) 
                       VALUES ('user', 'money', :count)"""),
                {"count": human_money},
            )

            # NPC inventories
            npc_data = game_lore.get("npc", {})
            for npc_name, npc_info in npc_data.items():
                npc_inv = npc_info.get("inventory", [])
                for item in npc_inv:
                    conn.execute(
                        text("""INSERT INTO inventory (character, item, count) 
                               VALUES (:character, :item, 1)"""),
                        {"character": npc_name, "item": item},
                    )

                # NPC money
                npc_money = npc_info.get("money", 0)
                conn.execute(
                    text("""INSERT INTO inventory (character, item, count) 
                           VALUES (:character, 'money', :count)"""),
                    {"character": npc_name, "count": npc_money},
                )

            conn.commit()

        logger.info("Inserted initial inventory data")

    def _load_npc_mapping(self) -> None:
        """Load NPC name mapping from existing database"""
        with self.engine.connect() as conn:
            if self._table_exists("npc_names_map"):
                result = conn.execute(
                    text("SELECT sanitized_name, original_name FROM npc_names_map")
                )
                for row in result:
                    self._npc_mapping[row[0]] = row[1]
                    self._inverse_npc_mapping[row[1]] = row[0]
                logger.info(f"Loaded {len(self._npc_mapping)} NPC name mappings")
            else:
                logger.warning(
                    "npc_names_map table not found, NPC mapping will be empty"
                )

    # -------------------------------------------------------------------------
    #                           PUBLIC METHODS
    # -------------------------------------------------------------------------

    def update_game_history(self, messages: List[Dict[str, Any]]) -> None:
        """
        Update the latest row in game_history table.

        Args:
            messages: List of dicts with 'role' and 'message' keys.
                     Roles map to columns: 'user_input', 'game_action', 'displayed_action',
                     'compacted_history', or NPC names.

        If any role is in {'game_action', 'displayed_action', 'compacted_history'},
        updates the latest row and creates a new empty row.
        """
        if not messages:
            return

        # Build update data from messages
        update_data = {}
        turn_ending = False

        for msg in messages:
            role = msg.get("role", "")
            message_content = msg.get("message", "")

            # Map role to column name
            if role == "user_input":
                col_name = "user_input"
            elif role in self._TURN_ENDING_ROLES:
                col_name = role
                turn_ending = True
            else:
                # Could be NPC name
                sanitized = self._inverse_npc_mapping.get(role)
                # Check if this sanitized name exists in our mapping
                if sanitized is not None and sanitized in self._npc_mapping:
                    col_name = sanitized
                else:
                    logger.warning(f'Unknown role "{role}" ignored')
                    continue

            update_data[col_name] = message_content

        with self.engine.connect() as conn:
            # Find max turn
            result = conn.execute(text("SELECT MAX(turn) FROM game_history"))
            max_turn = result.scalar() or 0

            # Build UPDATE statement dynamically
            if update_data:
                set_clause = ", ".join(f'"{k}" = :val_{k}' for k in update_data.keys())
                params = {"val_" + k: v for k, v in update_data.items()}
                params["turn"] = max_turn

                update_sql = f"UPDATE game_history SET {set_clause} WHERE turn = :turn"
                conn.execute(text(update_sql), params)

            # If turn ending, create new row
            if turn_ending:
                new_turn = max_turn + 1
                insert_sql = "INSERT INTO game_history (turn, compacted_history) VALUES (:turn, '')"
                conn.execute(text(insert_sql), {"turn": new_turn})

            conn.commit()

    def update_inventory_items(self, character: str, items: Dict[str, int]) -> None:
        """
        Update inventory items for a character.

        Args:
            character: Character name ('user' or NPC name)
            items: Dict of {item_name: count_change}
                  Positive = add, negative = remove
                  Creates entry if not exists (starts from 0)
        """
        with self.engine.connect() as conn:
            for item_name, count_change in items.items():
                # Use INSERT OR REPLACE with COALESCE to handle both cases
                conn.execute(
                    text("""INSERT INTO inventory (character, item, count) 
                           VALUES (:character, :item, 
                                   COALESCE((SELECT count FROM inventory 
                                            WHERE character = :character2 AND item = :item2), 0) + :change)
                           ON CONFLICT(character, item) DO UPDATE SET 
                               count = excluded.count"""),
                    {
                        "character": character,
                        "item": item_name,
                        "character2": character,
                        "item2": item_name,
                        "change": count_change,
                    },
                )
            conn.commit()

    def get_inventory_items(self, character: str) -> Dict[str, int]:
        """
        Get all inventory items for a character.

        Args:
            character: Character name ('user' or NPC name)

        Returns:
            Dict of {item_name: count} for items with count >= 0
            Empty dict if no items found
        """
        with self.engine.connect() as conn:
            result = conn.execute(
                text("""SELECT item, count FROM inventory 
                       WHERE character = :character AND count >= 0"""),
                {"character": character},
            )
            return {row[0]: row[1] for row in result}

    def get_last_n_turns(self, n: int, character: str = "") -> List[Dict[str, Any]]:
        """
        Get last N rows from game_history where compacted_history is empty.

        Args:
            n: Number of rows to return
            character: If non-empty, filters for interactions with this NPC
                      (filters where NPC column != '' and returns only those turns)

        Returns:
            List of dicts, each dict represents a row
        """
        with self.engine.connect() as conn:
            if character:
                # Check if the requested character is available
                sanitized = self._inverse_npc_mapping.get(character)
                all_cols = self._get_table_columns("game_history")
                if sanitized is not None and sanitized in all_cols:
                    query = text(f'''
                        SELECT * FROM game_history 
                        WHERE compacted_history = '' AND "{sanitized}" != ''
                        ORDER BY turn DESC LIMIT :limit
                    ''')
                else:
                    # requested column does not exist
                    return []
            else:
                query = text("""
                    SELECT * FROM game_history 
                    WHERE compacted_history = ''
                    ORDER BY turn DESC LIMIT :limit
                """)

            result = conn.execute(query, {"limit": n})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result]

    def get_additional_context(self, messages: List[Dict[str, Any]]) -> str:
        """
        Placeholder for additional context (RAG, knowledge graphs, etc.).

        Args:
            messages: List of message dicts (unused currently)

        Returns:
            Empty string
        """
        return ""
