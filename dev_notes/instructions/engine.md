# Overview 
A graph that implements the game logic. Agent state includes:
- game lore
- message history
- inventory for each actor -- human player, NPCs
- ? anything else

The intended operation of the graph:
1. user writes their response
2. the graph classifies input:
	a. valid game action
	b. clarification question
	c. not valid game action

In case of 2a:
3. Every NPC defines thier actions.  These are short/concept actions, e.g. NPC joins fight and will use <...>
4. The game engine defines the game actions. These are also short statements of actions. 
5. The graph streams final response for every NPC and the game changes. This is proper narrative to show the response the player.

In case of 2b:
6. The graph routes directly to a node to answer on clarification questions. The node provides brief answer -- the same type of short/concept
7. The graph streams the final response. 

In case of 2c:
8. Prompt the player that this was invalid input and with brief description why.

Tentative topology:

```
user input --> classification node--------------|
				| valid 	| clarification     | invalid
				| game 		|					| game
				| action 	|					| action
			-------       -----------			|
			NPC actions	  Brief response		|
			-------       -----------			|
			|				|					|
			|				|					|
			-------			|					|
			game response	|					|
			-------			|					|
			|				|					|
			|				|					|
			-------------------------------------
				game narration
			-------------------------------------
							|
						streaming response
```

NPC actions	 -- are sub-graphs. 

# Nodes
## Classification node
The node identifies if the input
- alligns with the world type, concept, description. E.g. if we play a fantasy world, user prompt "I fire BFG-9000" will be clearly invalid action. 
- is a clarification request. E.g. "What is <...>?" or "Why is <...> important?".
- is a valid game action -- does not contradict the world type, world concept, world descritption.

The output of the node:
- DECISION: str
- reasoning: str -- brief explanation

## Game response
The node decides on what happens in the game.  
- Identifies any inventory changes and applies them
- Identifies changes in physical and mental states of everyone in the scene (i.e. the player and the NPCs)
- decides what happes in the game

The decision is a short, brief description of actions. Detailed, but very terse. This will be used to generate actual response that is shown to the user.


## NPC action
Probably a subgraph for each NPC. The subgraph shares the state with the game graph -- the NPC subgraph needs access to the current state + history via chekpointers

The subgraph decides:
- if the NPC shall do something based on the context and the situation. Outcomes: do nothing, act
- if act, the NPC acts in accordance to the NPC card and the world concept and the world description
- the outcome is a very short, declarative explanation of actions.

## Brief response
This node is invoked when the ## Classification node decides that this is a lore or other related questions.
The node generates brief, concept-like response

## game narration
This node narrates all previous responses into a coherent text into Markdown

This is what user sees in the end.

# YOUR TASK
- Review the code base. 
- Use LangChain's MCP for reference for LangGraph -- source of truth
- Review the plan and help to develop a plan for the development

## Checkpointer

The graph state shall include `npc_actions` -- dict[str, list[dict[str, str]]], key -- npc name, value -- list of messages


# Notes

## Session memory
We need to store previous actions from each NPC, game actions, user input, game responses. The history is essentially
a session memory. It is not necessary the graph's state. 

This means we may want to have a dedicated databases with dedicated tables per game session
(we can generate random strings for table names and keep a mapping between game sessions and the table names). 
Table:
Primary key: turn number
Columns: user input, <NPC_name>_column, game_action, game_narrated
In case when user asks clarification questions, we populate the game_narrated column 

The database to use: SQLite. We need to craete an SQLAlchemy class that manages the IO operations. We do not need ORM 
part of SQLAlchemy -- we can use SQL queries for pupulation and reading the tables

### Methods
.init(*) -- creates/read the table
other methods TBD




# UI
At this point we want just LangGraph graphs. Probably, we UI will be TUI in terminal using Python's `rich`. 
These details are out of scope, just for the context.






# EXTRA
```Python
from baml_client import b

# Create a scoped client instance with specific env overrides
my_custom_client = b.with_options(
    env={
        "OPENAI_API_KEY": "your-runtime-key-here",
        "BAML_LOG": "DEBUG"
    }
)

# Use it normally without needing to pass options again
result = await my_custom_client.ExtractResume(resume_text="...")

```