I want to write a ReAct agent that generates a lore for a textual RPG game. On the high level it genereates:
- World description -- a generic story, how the world functions (e.g. rules of magic, technology, etc.) in a consistent and not self-contradictory way
- a playeable character for a human player. 
- a companion to the player (NPC). Imprtatnt, that they start at the same place together
- both human player and the NPC shall have something in common (history, background, etc.)
- generate a starting point for the player and npc -- where are they starting
- generate a plot for the campaign

The inspiration here is a DnD cmapaign but we have an open world.

This agent will be later used to answer player's questions about the lore, historic event, etc

The tech stack:
- Python async
- BAML for LLM ineractions (async)
- no libraries (e.g. LangGraph, etc)

Architecture approximately:
- orchestrator
- async queue of tasks (Pydantic classes)
- the tasks are picked from the queue and returned to the orchestrator
- the orchestrator awaits gatherting the tasks, calls a critic, and decides if new tasks to improve shall be queued. 
- there is a limit on iterations MAX_ITER_LIMIT
- either limit on the iterations is reached or the critique is staisfied
