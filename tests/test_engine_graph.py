import types

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer
from langgraph.graph.message import add_messages

from src.agents.engine import Engine, EngineConfig, NodeFns, build_graph
from src.agents.engine import nodes as nodes_module
from src.agents.engine.serde import build_serde
from src.baml_client.types import (
    CharacterArrangement,
    InputClassification,
    InputDecision,
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

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


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


def make_fns(
    decision: str = "valid_action",
    narration_text: str = "Rendered.",
    tokens: tuple[str, ...] = ("Ren", "dered."),
) -> NodeFns:
    async def cls(state):
        turn = state.get("turn_no", 0) + 1
        return {
            "turn_no": turn,
            "classification": decision,
            "classification_reason": "r",
            "invalid_reason": None,
            "messages": [
                HumanMessage(content=state["raw_input"], id=f"user:t{turn}")
            ],
        }

    async def game(state):
        return {"game_action": "[game]"}

    async def npc(state):
        return {}

    async def brf(state):
        return {"brief_answer": "[brief]"}

    async def narr(state):
        writer = get_stream_writer()
        for token in tokens:
            writer({"narration_token": token})
        return {
            "narration": narration_text,
            "messages": [
                AIMessage(
                    content=narration_text,
                    name="narrator",
                    id=f"narrator:t{state.get('turn_no', 0)}",
                )
            ],
        }

    return NodeFns(
        classification=cls,
        npc=npc,
        game_response=game,
        brief=brf,
        narration=narr,
    )


def memory_engine(fns: NodeFns, config: EngineConfig | None = None) -> Engine:
    return Engine(
        config or EngineConfig(),
        checkpointer=InMemorySaver(serde=build_serde()),
        node_fns=fns,
    )


def human_ids(state) -> list[str]:
    return [m.id for m in state["messages"] if isinstance(m, HumanMessage)]


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


async def test_valid_path_reaches_game_stage_and_narration():
    async with memory_engine(make_fns("valid_action")) as engine:
        tid = await engine.new_game({})
        st = await engine.turn(tid, "draw my blade")

    assert st["classification"] == "valid_action"
    assert st["game_action"] == "[game]"
    assert st["narration"] == "Rendered."
    assert "brief_answer" not in st


async def test_clarification_path_reaches_brief_and_narration():
    async with memory_engine(make_fns("clarification")) as engine:
        tid = await engine.new_game({})
        st = await engine.turn(tid, "what is this place?")

    assert st["classification"] == "clarification"
    assert st["brief_answer"] == "[brief]"
    assert st["narration"] == "Rendered."
    assert "game_action" not in st


async def test_invalid_path_skips_game_and_brief():
    async with memory_engine(make_fns("invalid")) as engine:
        tid = await engine.new_game({})
        st = await engine.turn(tid, "I summon a dragon")

    assert st["classification"] == "invalid"
    assert st["narration"] == "Rendered."
    assert "game_action" not in st
    assert "brief_answer" not in st


# ---------------------------------------------------------------------------
# Turn accounting / messages
# ---------------------------------------------------------------------------


async def test_turn_bumps_once_and_appends_one_human_message():
    async with memory_engine(make_fns("valid_action")) as engine:
        tid = await engine.new_game({})
        st = await engine.turn(tid, "look around")

    assert st["turn_no"] == 1
    assert human_ids(st) == ["user:t1"]


async def test_human_message_id_is_retry_stable():
    st = {"messages": [HumanMessage(content="look", id="user:t1")]}
    again = HumanMessage(content="look", id="user:t1")
    merged = add_messages(st["messages"], [again])
    assert len(merged) == 1


async def test_narration_message_has_deterministic_id():
    async with memory_engine(make_fns("valid_action")) as engine:
        tid = await engine.new_game({})
        st = await engine.turn(tid, "look around")

    narrators = [m for m in st["messages"] if isinstance(m, AIMessage)]
    assert len(narrators) == 1
    assert narrators[0].id == "narrator:t1"
    assert narrators[0].name == "narrator"
    assert narrators[0].content == "Rendered."


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


async def test_stream_turn_emits_narration_tokens_then_updates():
    async with memory_engine(make_fns("clarification")) as engine:
        tid = await engine.new_game({})
        events = [ev async for ev in engine.stream_turn(tid, "huh?")]

    custom = [e for e in events if e["type"] == "custom"]
    updates = [e for e in events if e["type"] == "updates"]
    assert custom, "expected narration tokens"
    assert "".join(e["data"]["narration_token"] for e in custom) == "Rendered."
    assert any("narration" in e["data"] for e in updates)


# ---------------------------------------------------------------------------
# Engine seeding / persistence
# ---------------------------------------------------------------------------


async def test_new_game_seeds_lore_across_turns():
    async with memory_engine(make_fns("valid_action")) as engine:
        tid = await engine.new_game(fake_lore())
        await engine.turn(tid, "look around")
        st = await engine.turn(tid, "keep going")

    assert st["world_narrative"].name == "Testworld"
    assert [c.name for c in st["npc_cards"]] == ["NPC"]
    assert st["turn_no"] == 2
    # opening + 2 human + 2 narrator
    assert len(st["messages"]) == 5
    assert human_ids(st) == ["user:t1", "user:t2"]


async def test_sqlite_checkpoint_persists_across_engines(tmp_path):
    path = str(tmp_path / "engine.db")
    cfg = EngineConfig(sqlite_path=path)

    async with Engine(cfg, node_fns=make_fns("valid_action")) as engine:
        tid = await engine.new_game(fake_lore(), thread_id="persist")
        await engine.turn(tid, "look around")

    async with Engine(cfg, node_fns=make_fns("valid_action")) as engine:
        st = (await engine.state("persist")).values

    assert st["turn_no"] == 1
    assert st["narration"] == "Rendered."
    assert len(st["messages"]) == 3
    assert st["world_concept"].physics == ["p"]


# ---------------------------------------------------------------------------
# Real node functions (BAML stubbed)
# ---------------------------------------------------------------------------


class FakeStream:
    def __init__(self, chunks: list[str], final: str | None = None):
        self._chunks = chunks
        self._final = final if final is not None else (chunks[-1] if chunks else "")

    def __aiter__(self):
        async def gen():
            for chunk in self._chunks:
                yield chunk

        return gen()

    async def get_final_response(self):
        return self._final


def fake_b(decision: InputDecision, chunks: list[str], final: str | None = None):
    fake = types.SimpleNamespace()

    async def classify(context, input, baml_options=None):
        return InputClassification(
            decision=decision,
            reason="because",
            invalid_reason="bad input" if decision is InputDecision.Invalid else None,
        )

    class _Stream:
        def NarrateTurn(self, *, context, events, mode, baml_options=None):
            return FakeStream(chunks, final)

    fake.ClassifyInput = classify
    fake.stream = _Stream()
    return fake


async def test_classification_node_writes_decision_and_human_message(monkeypatch):
    monkeypatch.setattr(
        nodes_module, "b", fake_b(InputDecision.Clarification, [])
    )
    state = {"raw_input": "what?", "turn_no": 4, "messages": []}
    out = await nodes_module.classification(state, EngineConfig())

    assert out["turn_no"] == 5
    assert out["classification"] == "clarification"
    assert out["classification_reason"] == "because"
    assert out["invalid_reason"] is None
    assert out["messages"][0].id == "user:t5"
    assert out["messages"][0].content == "what?"


async def test_classification_node_maps_invalid(monkeypatch):
    monkeypatch.setattr(nodes_module, "b", fake_b(InputDecision.Invalid, []))
    state = {"raw_input": "i fly", "turn_no": 0, "messages": []}
    out = await nodes_module.classification(state, EngineConfig())
    assert out["classification"] == "invalid"
    assert out["invalid_reason"] == "bad input"


async def test_narration_node_streams_deltas_and_writes_message(monkeypatch):
    # cumulative partials: second chunk contains the first
    monkeypatch.setattr(
        nodes_module, "b", fake_b(InputDecision.ValidAction, ["Hel", "Hello"])
    )
    written: list[dict] = []
    monkeypatch.setattr(nodes_module, "get_stream_writer", lambda: written.append)

    state = {
        "raw_input": "hi",
        "turn_no": 3,
        "classification": "valid_action",
        "game_action": "you wave",
        "messages": [],
        "npc_actions": [],
    }
    out = await nodes_module.narration(state, EngineConfig())

    assert [w["narration_token"] for w in written] == ["Hel", "lo"]
    assert out["narration"] == "Hello"
    assert out["messages"][0].id == "narrator:t3"
    assert out["messages"][0].name == "narrator"


async def test_build_context_tolerates_empty_state():
    text = nodes_module.build_context({"messages": []}, EngineConfig())
    assert isinstance(text, str)


# ---------------------------------------------------------------------------
# Graph render
# ---------------------------------------------------------------------------


async def test_graph_renders_mermaid_with_all_nodes():
    graph = build_graph(EngineConfig()).compile()
    mermaid = graph.get_graph().draw_mermaid()
    for name in ("classification", "game_response", "brief", "narration"):
        assert name in mermaid
