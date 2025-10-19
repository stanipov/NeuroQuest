# RPG powered by LLMs!

Console text-based RPG with full control by LLMs.

**Completed parts:**
1. Lore generation -- locations, NPCs, player's card, player's antagonist
1. NPC ai -- actions, detects inventory and mental/physical changes
1. Auxiliary functions -- SQL game memory, saved games management
1. UI -- a simple textual UI in terminal.
1. User input validation and simple classification

**Planned/remaining**:
1. GamePlay AI -- generates game response and tracks inventory and physical/mental state of the player, checks if the game
is finished. Under design
1. Game AI class -- governs the gameplay process. TBD.
1. Simpler NPC and GamePlay AI.
1. Performance optimizations
1. TBD: service commands and respective UI hooks/actions.

**Current gameplay direction**
1. For every user input the game checks if the input is valid.
1. An invalid input will generate response with a simple message, loop till correct input is obtained
1. For a valid input, it is classified as a game or non-game action. A non-game action could be e.g. a lore question. This is
a sort of optimization to avoid generating response for the NPCs and other actions.
1. A valid game action will trigger a defined sequence of actions -- NPC responses and game play response
1. The actions are looped in a while loop -- it breaks either by completion of the game or exit.