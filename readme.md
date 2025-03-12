# RPG powered by LLMs!

Stay tuned, more to come!

**Current status:** working on hierarchical lore generation.

Lore generation progress:
- world
- locations (kingdoms and towns)
- playable character
- antagonist generation
- conditions to win and lose (added to game lore generation class)

To-do:
- world rules/functioning principles
- storyteller: convert bullet-point-like descriptions into a concise, short, and appealing text like in real RPGs

## Gameplay
Every action shall be: 
- checked against generic rules of the world (e.g. you can't use a BFG9000 in a fantasy setting!)
- checked against winning/loosing conditions
- track the game characters states (such as inventory, mental and physical health, etc)

The LLMs deteriorate their performance with increase of the context window (in pp/tg and in terms of coherence). 
I plan to use a combination of RAG and sliding window for performance issues.

## Final goal
Make the game as RestAPI server and write a front-end.