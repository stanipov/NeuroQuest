"""
Classes/methods to work with memory
"""
from typing import List, Dict, Any, Callable
import re
from sqlalchemy import text

from sqlalchemy import create_engine

# ----------------------------- Module logging -----------------------------
import logging

logger = logging.getLogger(__name__)
# ----------------------------- Module logging -----------------------------


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
