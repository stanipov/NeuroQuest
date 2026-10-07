import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from src.agents.engine.serde import build_serde
from src.agents.engine.state import (
    GameState,
    initial_state,
    make_npc_msg,
    npc_history,
    turn_actions,
)
from src.baml_client.types import (
    CharacterArrangement,
    OpeningScene,
    PlayerCharacterCard,
    PlayerGender,
    Settlement,
    SpecificLocation,
    StartingContext,
    WorldConcept,
    WorldNarrative,
    WorldTypes,
)


def _card(name: str, items: list[str], money: int) -> PlayerCharacterCard:
    return PlayerCharacterCard(
        name=name,
        gender=PlayerGender.Male,
        occupation="wanderer",
        age=30,
        biography="b",
        physical="phys",
        wisdom="wis",
        strengths="st",
        weaknesses="wk",
        money=money,
        inventory=items,
    )


def fake_lore() -> dict:
    return {
        "world_type": WorldTypes(type="high fantasy", inspiration="test"),
        "world_concept": WorldConcept(
            magic=[], physics=["p"], society=["s"], geography=["g"], technology=["t"]
        ),
        "world_narrative": WorldNarrative(
            name="Testworld", history="h", current_state="c"
        ),
        "player_card": _card("Player", ["rope"], 10),
        "npc_card": _card("NPC", ["lantern"], 3),
        "context": StartingContext(
            region_name="R",
            region_description="d",
            settlement=Settlement(
                name="S", type="town", description="sd", background="sb"
            ),
            location=SpecificLocation(
                name="L",
                type="tavern",
                description="ld",
                atmosphere="la",
                notable_features=["f"],
            ),
        ),
        "arrangement": CharacterArrangement(
            player_circumstance="pc", npc_circumstance="nc", shared_situation="ss"
        ),
        "scene": OpeningScene(narrative="Opening scene.", immediate_hook="hook"),
    }


def base_state() -> GameState:
    return initial_state(fake_lore())


def base_input() -> dict:
    return {**base_state(), "raw_input": "look around"}


def test_make_npc_msg_id_is_deterministic():
    a = make_npc_msg("NPC", 1, "draws a blade")
    b = make_npc_msg("NPC", 1, "draws a blade")
    assert a.id == b.id
    assert a.id.startswith("npc:NPC:t1:")
    assert a.name == "NPC"
    assert a.additional_kwargs["turn_no"] == 1
    assert "ts" in a.additional_kwargs
    assert a.additional_kwargs["ts"] not in a.id


def test_make_npc_msg_id_changes_with_content_and_turn():
    a = make_npc_msg("NPC", 1, "draws a blade")
    b = make_npc_msg("NPC", 1, "draws a coin")
    c = make_npc_msg("NPC", 2, "draws a blade")
    assert len({a.id, b.id, c.id}) == 3


def test_add_messages_overwrites_same_id():
    a = make_npc_msg("NPC", 1, "acts")
    b = make_npc_msg("NPC", 1, "acts")
    assert len(add_messages([], [a])) == 1
    merged = add_messages([a], [b])
    assert len(merged) == 1


def test_same_content_different_turns_yields_two_entries():
    a = make_npc_msg("NPC", 1, "acts")
    b = make_npc_msg("NPC", 2, "acts")
    assert len(add_messages([a], [b])) == 2


def test_npc_history_filters_orders_and_windows():
    s = base_state()
    s["npc_actions"] = [
        make_npc_msg("A", 2, "a2"),
        make_npc_msg("B", 1, "b1"),
        make_npc_msg("A", 1, "a1"),
    ]
    assert [m.content for m in npc_history(s, "A")] == ["a1", "a2"]
    assert [m.content for m in npc_history(s, "B")] == ["b1"]
    assert [m.content for m in npc_history(s, "A", k=1)] == ["a2"]


def test_turn_actions_filters_and_sorts_by_name():
    s = base_state()
    s["npc_actions"] = [
        make_npc_msg("B", 1, "b"),
        make_npc_msg("A", 1, "a"),
        make_npc_msg("A", 2, "a2"),
    ]
    assert [m.content for m in turn_actions(s, 1)] == ["a", "b"]
    assert [m.content for m in turn_actions(s, 2)] == ["a2"]


def test_initial_state_maps_lore_and_seeds_runtime():
    st = initial_state(fake_lore())
    assert st["starting_context"].region_name == "R"
    assert st["current_location"] == "L"
    assert [c.name for c in st["npc_cards"]] == ["NPC"]
    assert st["inventories"]["Player"] == {"items": ["rope"], "money": 10}
    assert st["inventories"]["NPC"] == {"items": ["lantern"], "money": 3}
    assert st["turn_no"] == 0
    assert st["npc_actions"] == []
    assert len(st["messages"]) == 1
    assert st["messages"][0].id == "opening"
    assert st["messages"][0].content == "Opening scene."


def test_initial_state_drops_missing_lore_keys():
    lore = fake_lore()
    lore.pop("context")
    lore.pop("npc_card")
    st = initial_state(lore)
    assert "starting_context" not in st
    assert "current_location" not in st
    assert "npc_cards" not in st
    assert st["inventories"]["Player"] == {"items": ["rope"], "money": 10}


def test_inventories_reducer_merges_complete_actor_dicts():
    def a(state):
        return {"inventories": {"P": {"items": ["x"], "money": 1}}}

    def b(state):
        return {"inventories": {"N": {"items": ["y"], "money": 2}}}

    g = (
        StateGraph(GameState)
        .add_node("a", a)
        .add_node("b", b)
        .add_node("end", lambda s: {})
        .add_edge(START, "a")
        .add_edge(START, "b")
        .add_edge("a", "end")
        .add_edge("b", "end")
        .add_edge("end", END)
        .compile()
    )
    out = asyncio.run(g.ainvoke(base_input()))
    assert set(out["inventories"]) == {"Player", "NPC", "P", "N"}
    assert out["inventories"]["P"]["items"] == ["x"]
    assert out["inventories"]["N"]["money"] == 2


def test_state_graph_smoke_renders_mermaid():
    g = (
        StateGraph(GameState)
        .add_node("noop", lambda s: {})
        .add_edge(START, "noop")
        .add_edge("noop", END)
        .compile()
    )
    assert "noop" in g.get_graph().draw_mermaid()


def test_baml_types_survive_checkpoint_roundtrip():
    g = (
        StateGraph(GameState)
        .add_node("noop", lambda s: {})
        .add_edge(START, "noop")
        .add_edge("noop", END)
        .compile(checkpointer=InMemorySaver(serde=build_serde()))
    )
    cfg = {"configurable": {"thread_id": "roundtrip"}}
    asyncio.run(g.ainvoke(base_input(), cfg))
    values = g.get_state(cfg).values
    assert values["world_concept"].physics == ["p"]
    assert values["player_card"].name == "Player"
    assert values["inventories"]["NPC"]["money"] == 3
