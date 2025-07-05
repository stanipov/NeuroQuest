"""
Classes/methods to work with memory
"""

from itertools import cycle
from typing import List, Dict, Any, Type

from sqlalchemy import create_engine, Column, String, Text, MetaData, ForeignKey, Float, Integer, Table
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
from sqlalchemy.inspection import inspect

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
                rows = query.all()
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

# ----------------------------- Memory for the game -----------------------------

# RAG augmented memory is planned

class GameMemorySimple(SQLMemory):
    def __init__(self, db_path):
        super().__init__(db_path)

    def create_inventory(self, items_tbl: Dict[str, Any], inventory_tbl: Dict[str, Any]):
        """
        Build inventory and items tables.
        Inventory:
            character: str: Player/NPC name
            item: str: item name, e.g. "axe", etc.
            money: int: funds of the character
            -- primary keys: character, item
        Items:
            item: str: name of the item
            description: str: item description
            type: str: type of item, e.g. weapon/armor/...
            action: str: how the item works
            strength: str: effect of the item
            -- primary key: item

        :param items_tbl: Dict[str, Any] -- a nested dictionary with all parameters for "items" table.
                These are packed parameters for SQLMemory.create_table()
                items_tbl['columns'] -->  columns: Dict[str, str] -- dictionary containing column names and their datatypes
                items_tbl['primary_keys'] --> primary_keys: List[str] -- list of primary keys
                items_tbl['index_keys']: List[str] --> index_keys: List[str] -- list of index columns, optional
                items_tbl['foreign_keys']: Dict[str, str] --> foreign_keys: Dict[str, str] -- dictionary of foreign keys (names and their data types)
        :param inventory_tbl: Dict[str, Any] -- a nested dictionary with all parameters for "inventory" table. Same structure is expected.
        :return:
        """
        # First create items table (because inventory depends on it)
        logger.info("Creating the \"items\" table")
        self.create_table(table_name="items",
                          columns=items_tbl['columns'],
                          primary_keys=items_tbl['primary_keys'],
                          index_keys=items_tbl.get('index_keys', []),
                          foreign_keys=items_tbl.get('foreign_keys', None))

        # Now create inventory table
        logger.info("Creating the \"inventory\" table")
        self.create_table(table_name="inventory",
                          columns=inventory_tbl['columns'],
                          primary_keys=inventory_tbl['primary_keys'],
                          index_keys=inventory_tbl.get('index_keys', []),
                          foreign_keys=inventory_tbl.get('foreign_keys', None))

        logger.info(f"Relating the tables")

        if not hasattr(self.models["items"], "inventory_entries"):
            self.models["items"].inventory_entries = relationship(
                self.models["inventory"],
                back_populates="item_ref",  # NOTE: changed from 'item' to 'item_ref'
                cascade="all, delete",
                passive_deletes=True
            )

        if not hasattr(self.models["inventory"], "item_ref"):
            self.models["inventory"].item_ref = relationship(
                self.models["items"],
                back_populates="inventory_entries"
            )


    def create_messages(self, npc_names:List[str] = []):
        _schema = {"turn": int,
                   "ai_response": str,
                   "human_response": str}
        if npc_names != []:
            for npc_name in npc_names:
                _schema[npc_name] = str
        logger.info('Creating \"messages\" table')
        self.create_table(table_name="messages",
                          columns=_schema,
                          primary_keys=["turn"],
                          index_keys=["turn"])
        self.messages_shema = _schema


    def update_inventory(self, character: str, inventory: List[str], items: Dict[str, Dict[str, str]]):
        items_model = self.models["items"]
        inventory_model = self.models["inventory"]

        with self.Session() as session:
            # Step 1: Insert/Skip items
            for item_name, item_data in items.items():
                try:
                    self.add_row("items", {"item": item_name, **item_data})
                except ValueError as e:
                    if "already exists" not in str(e):
                        raise

            # Step 2: Existing inventory entries for this character
            existing_entries = session.query(inventory_model).filter(inventory_model.character == character).all()
            existing_item_names = {entry.item for entry in existing_entries}

            # Step 3: Add new inventory items
            for item_name in inventory:
                if item_name not in existing_item_names:
                    try:
                        self.add_row("inventory", {
                            "character": character,
                            "item": item_name
                        })
                    except ValueError as e:
                        if "already exists" not in str(e):
                            raise

            # Step 4: Remove items that are no longer in inventory
            to_remove = [entry for entry in existing_entries if entry.item not in inventory]
            for entry in to_remove:
                session.delete(entry)

            session.commit()

    def add_new_turn(self, messages: List[Dict[str, Any]], turn: int = -1):
        """
        Adds a new message to the "messages" table. If turn is not provided, it will be inferred from the DB.
        Messages must follow standard OpenAI-type:
            [{'role': 'r1', 'message': msg1}, {'role': 'r2', 'message': msg2}]
        Here:
            - 'role' either 'ai_response', 'human_response', or <actual NPC name>
            - 'message' -- 'role' utterance

        :param messages:
        :param turn:
        :return:
        """

        # "turn" is a primary key for the messages table
        if turn == -1:
            # read the DB to find the latest turn number
            last_row = self.get_last_n_rows("messages", 1)
            if last_row != []:
                turn = last_row[0]
            else:
                logger.info(f"No rows found in \"messages\" table. Setting \"turn\" to 0")
                turn = 0

        row = {'turn': turn}
        for msg in messages:
            if msg['role'] not in self.messages_shema:
                logger.error(f"{msg['role']} is not within acceptable shema!")
                raise ValueError(f"{msg['role']} is not within acceptable shema!")

            row[msg['role']] = msg['message']
        self.add_row("messages", row, True)


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
            last_row = self.get_last_n_rows("messages", 1)
            if last_row != []:
                turn = last_row[0]
            else:
                logger.info(f"No rows found in \"messages\" table. Setting \"turn\" to 0")
                turn = 0
        _table_name = 'messages'
        _strict = True
        row = {
            'turn': turn
        }

        for msg in messages:
            if msg['role'] not in self.messages_shema:
                logger.error(f"{msg['role']} is not within acceptable shema!")
                raise ValueError(f"{msg['role']} is not within acceptable shema!")

            row[msg['role']] = msg['message']

        self.update_row(_table_name, row, _strict)