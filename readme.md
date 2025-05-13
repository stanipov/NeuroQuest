# RPG powered by LLMs!

Stay tuned, more to come!

**Current status:** 
1. Detection of changes in inventory, location, and physical/mental state
2. Memory/context generation
2. NPC interaction with the player and world
3. AI response

Most of these are in the state of architecture. I will not use the agentic libraries as the only
thing I will actually use is saving the session, state and memory. Given the current turbulent state
of the agentic libraries, it does not make sense to commit to any for such a simple need which 
can be implemented myself.

Lore generation progress:
- world
- locations (kingdoms and towns)
- playable character
- antagonist generation
- conditions to win and lose (added to game lore generation class)
- world rules/functioning principles
- inventory and inventory description
- npc (allies of the human player) — character cards and their behavioral traits

storyteller: convert bullet-point-like descriptions into a concise,
short, and appealing text like in real RPGs (rev 0.1 as it will be tested)



These are finally in a single class [LoreGeneratorGvt](llm_rpg.engine.lore_generation.LoreGeneratorGvt) which provides
a simple API to govern two underlying classes.
The starting location for the human player is randomly chosen. The NPCs start
together in the same location


## Gameplay
Every action shall be: 
- checked  against generic rules of the world (e.g. you can't use a BFG9000 in a fantasy setting!)
- checked against winning/loosing conditions
- track the game characters states (such as inventory, mental and physical health, etc.)

The LLMs deteriorate their performance with increase of the context window (in pp/tg and in terms of coherence). 
I plan to use a combination of RAG and sliding window for performance issues.


## Final goal
Rich CLI app