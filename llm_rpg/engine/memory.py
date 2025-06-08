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
            logger.info(f"Loaded {len(self.models)} existing table(s): {list(self.models).keys()}")

    def create_table(self,
                     table_name: str,
                     columns: Dict[str, Any],
                     primary_keys: List[str],
                     index_keys: List[str] = [],
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
        Updates an entry in the table.
        :param table_name: str -- table name.
        :param row: Dict[str, Any] -- row to update
        :param strict: bool -- will enforce of primary keys in the input data. Default: True.
        :return: None
        """
        if table_name not in self.models:
            logger.warning(f"\"{table_name}\" is not found!")
            return
        model = self.models[table_name]

        if strict:
            pk_columns = self.primary_keys(table_name)
            if not all(pk in row for pk in pk_columns):
                raise KeyError(f"Missing primary key fields: expected {pk_columns}, got {list(row.keys())}")

        with self.Session() as session:
            try:
                # Build query to locate the row
                pk_filter = {pk: row[pk] for pk in pk_columns}
                obj = session.query(model).filter_by(**pk_filter).one_or_none()

                if not obj:
                    logger.error(f"Row with primary key {pk_filter} not found in table \"{table_name}\".")
                    raise ValueError(f"Row with primary key {pk_filter} not found in table \"{table_name}\".")

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

class GameMemory(SQLMemory):
    def __init__(self, db_path):
        super.__init__(db_path)
