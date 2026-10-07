import types

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Send

from src.agents.engine import (
    Engine,
    EngineConfig,
    NodeFns,
    build_graph,
    route_classification,
)
from src.agents.engine import nodes as nodes_module
from src.agents.engine import npc as npc_module
from src.agents.engine.npc import npc_act
from src.agents.engine.serde import build_serde
from src.agents.engine.state import make_npc_msg
from src.baml_client.types import (
    CharacterArrangement,
    GameResolve,
    InventoryDelta,
    OpeningScene,
    PlayerCharacterCard,
    PlayerGender,
    Settlement,
    SpecificLocation,
    StartingContext,
    StateDelta,
    WorldConcept,
    WorldNarrative,
    WorldTypes,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _card(name: str, items: list[str] | None = None, money: int = 0):
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
        inventory=items or [],
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


def make_fns(npc_actions=None, order=None) -> NodeFns:
    order = order if order is not None else []
    npc_actions = npc_actions or []

    async def cls(state):
        order.append("classification")
        turn = state.get("turn_no", 0) + 1
        return {
            "turn_no": turn,
            "classification": "valid_action",
            "classification_reason": "r",
            "invalid_reason": None,
            "messages": [
                HumanMessage(content=state["raw_input"], id=f"user:t{turn}")
            ],
        }

    async def npc(state):
        order.append(("npc", state["my_card"].name))
        return {"npc_actions": npc_actions} if npc_actions else {}

    async def game(state):
        order.append("game_response")
        return {"game_action": "[game]"}

    async def brf(state):
        order.append("brief")
        return {"brief_answer": "[brief]"}

    async def narr(state):
        order.append("narration")
        return {
            "narration": "Rendered.",
            "messages": [
                AIMessage(
                    content="Rendered.",
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


def base_state(**overrides) -> dict:
    state = {
        "raw_input": "look around",
        "turn_no": 1,
        "messages": [],
        "npc_actions": [],
        "inventories": {},
        "physical_states": {},
        "mental_states": {},
        "player_card": _card("Player"),
        "npc_cards": [_card("NPC")],
    }
    state.update(overrides)
    return state


def resolve_result(inventory_deltas=None, state_deltas=None, terse="[game]"):
    return GameResolve(
        terse=terse,
        inventory_deltas=inventory_deltas or [],
        state_deltas=state_deltas or [],
    )


def stub_b(resolve=None, brief_answer="", npc_intent=""):
    fake = types.SimpleNamespace()

    async def ResolveGame(context, input, intents, baml_options=None):
        return resolve if resolve is not None else resolve_result()

    async def AnswerBrief(context, question, baml_options=None):
        return brief_answer

    async def NpcAct(context, npc, history=None, baml_options=None):
        return npc_intent

    fake.ResolveGame = ResolveGame
    fake.AnswerBrief = AnswerBrief
    fake.NpcAct = NpcAct
    return fake


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def test_route_valid_without_cards_goes_to_game_response():
    assert route_classification(
        {"classification": "valid_action", "npc_cards": []}
    ) == "game_response"


def test_route_valid_with_cards_fans_out_with_full_payload():
    state = {
        "classification": "valid_action",
        "raw_input": "go",
        "turn_no": 2,
        "npc_cards": [_card("A"), _card("B")],
    }
    sends = route_classification(state)

    assert isinstance(sends, list)
    assert len(sends) == 2
    assert all(isinstance(send, Send) and send.node == "npc" for send in sends)
    assert [send.arg["my_card"].name for send in sends] == ["A", "B"]
    # full-state payload keeps the shared channels
    assert sends[0].arg["turn_no"] == 2
    assert sends[0].arg["raw_input"] == "go"


def test_route_clarification_and_invalid():
    assert route_classification({"classification": "clarification"}) == "brief"
    assert route_classification({"classification": "invalid"}) == "narration"


# ---------------------------------------------------------------------------
# npc_act node (BAML stubbed)
# ---------------------------------------------------------------------------


async def test_npc_act_writes_deterministic_message(monkeypatch):
    monkeypatch.setattr(npc_module, "b", stub_b(npc_intent="draws a blade"))
    state = base_state(npc_cards=[_card("NPC")])
    state["my_card"] = _card("NPC")

    out = await npc_act(state, EngineConfig())

    msg = out["npc_actions"][0]
    assert msg.id == make_npc_msg("NPC", 1, "draws a blade").id
    assert msg.id.startswith("npc:NPC:t1:")
    assert msg.name == "NPC"
    assert msg.additional_kwargs["turn_no"] == 1


async def test_npc_act_empty_writes_nothing(monkeypatch):
    monkeypatch.setattr(npc_module, "b", stub_b(npc_intent="   "))
    state = base_state()
    state["my_card"] = _card("NPC")
    assert await npc_act(state, EngineConfig()) == {}


async def test_npc_act_exception_is_swallowed(monkeypatch):
    fake = types.SimpleNamespace()

    async def NpcAct(context, npc, history=None, baml_options=None):
        raise RuntimeError("model down")

    fake.NpcAct = NpcAct
    monkeypatch.setattr(npc_module, "b", fake)

    state = base_state()
    state["my_card"] = _card("NPC")
    assert await npc_act(state, EngineConfig()) == {}


async def test_npc_act_passes_windowed_history(monkeypatch):
    seen: dict = {}

    async def NpcAct(context, npc, history=None, baml_options=None):
        seen["history"] = history
        return ""

    monkeypatch.setattr(npc_module, "b", types.SimpleNamespace(NpcAct=NpcAct))
    state = base_state(
        turn_no=2,
        npc_actions=[
            make_npc_msg("NPC", 1, "a1"),
            make_npc_msg("NPC", 2, "a2"),
        ],
    )
    state["my_card"] = _card("NPC")

    await npc_act(state, EngineConfig(npc_window=1))
    assert seen["history"] == "a2"


# ---------------------------------------------------------------------------
# Game stage (BAML stubbed)
# ---------------------------------------------------------------------------


async def test_game_response_applies_inventory_deltas(monkeypatch):
    monkeypatch.setattr(
        nodes_module,
        "b",
        stub_b(
            resolve=resolve_result(
                inventory_deltas=[
                    InventoryDelta(
                        actor="Player",
                        items_added=["torch"],
                        items_removed=["rope"],
                        money_delta=-3,
                    )
                ]
            )
        ),
    )
    state = base_state(
        inventories={"Player": {"items": ["rope"], "money": 10}}
    )

    out = await nodes_module.game_response(state, EngineConfig())

    assert out["game_action"] == "[game]"
    assert out["inventories"]["Player"] == {"items": ["torch"], "money": 7}
    assert "NPC" not in out["inventories"]


async def test_game_response_ignores_unknown_actor(monkeypatch):
    monkeypatch.setattr(
        nodes_module,
        "b",
        stub_b(
            resolve=resolve_result(
                inventory_deltas=[
                    InventoryDelta(
                        actor="Ghost",
                        items_added=["x"],
                        items_removed=[],
                        money_delta=1,
                    )
                ]
            )
        ),
    )
    out = await nodes_module.game_response(base_state(), EngineConfig())
    assert "inventories" not in out


async def test_game_response_state_deltas_player_location_only(monkeypatch):
    monkeypatch.setattr(
        nodes_module,
        "b",
        stub_b(
            resolve=resolve_result(
                state_deltas=[
                    StateDelta(
                        actor="Player",
                        physical="bruised",
                        mental="wary",
                        location="market",
                    ),
                    StateDelta(
                        actor="NPC",
                        physical="calm",
                        mental=None,
                        location="elsewhere",
                    ),
                ]
            )
        ),
    )

    out = await nodes_module.game_response(base_state(), EngineConfig())

    assert out["physical_states"] == {"Player": "bruised", "NPC": "calm"}
    assert out["mental_states"] == {"Player": "wary"}
    assert out["current_location"] == "market"  # NPC location ignored


async def test_game_response_writes_nothing_when_no_deltas(monkeypatch):
    monkeypatch.setattr(nodes_module, "b", stub_b(resolve=resolve_result()))
    out = await nodes_module.game_response(base_state(), EngineConfig())
    assert out == {"game_action": "[game]"}


# ---------------------------------------------------------------------------
# Brief / narration
# ---------------------------------------------------------------------------


async def test_brief_writes_answer(monkeypatch):
    monkeypatch.setattr(nodes_module, "b", stub_b(brief_answer="A short answer."))
    out = await nodes_module.brief(base_state(), EngineConfig())
    assert out == {"brief_answer": "A short answer."}


def test_narration_events_include_npc_intents():
    state = base_state(
        turn_no=2,
        game_action="[game]",
        npc_actions=[
            make_npc_msg("B", 2, "b acts"),
            make_npc_msg("A", 2, "a acts"),
            make_npc_msg("A", 1, "old"),
        ],
    )
    events = nodes_module._narration_events(state, "valid_action")
    assert events == "[game]\nA: a acts\nB: b acts"


# ---------------------------------------------------------------------------
# Engine / graph wiring
# ---------------------------------------------------------------------------


def test_engine_cfg_carries_max_concurrency():
    cfg = EngineConfig(max_npc_parallelism=3)
    engine = Engine(cfg, checkpointer=InMemorySaver(serde=build_serde()))
    assert engine._cfg("t")["max_concurrency"] == 3


async def test_graph_renders_all_nodes_including_npc():
    graph = build_graph(EngineConfig()).compile()
    mermaid = graph.get_graph().draw_mermaid()
    for name in ("classification", "npc", "game_response", "brief", "narration"):
        assert name in mermaid


async def test_valid_turn_with_one_npc_creates_action_then_game():
    order: list = []
    fns = make_fns(npc_actions=[make_npc_msg("NPC", 1, "watches")], order=order)

    async with memory_engine(fns) as engine:
        tid = await engine.new_game(fake_lore())
        st = await engine.turn(tid, "look around")

    assert [m.name for m in st["npc_actions"]] == ["NPC"]
    assert st["npc_actions"][0].additional_kwargs["turn_no"] == 1
    assert st["game_action"] == "[game]"
    assert st["narration"] == "Rendered."
    # NPC branch runs, then the barrier, then narration
    assert order.index(("npc", "NPC")) < order.index("game_response")
    assert order[-1] == "narration"


async def test_valid_turn_without_npc_skips_npc_node():
    order: list = []

    async with memory_engine(make_fns(order=order)) as engine:
        tid = await engine.new_game({})  # no npc_card
        st = await engine.turn(tid, "look around")

    assert not any(isinstance(o, tuple) and o[0] == "npc" for o in order)
    assert "game_response" in order
    assert st["game_action"] == "[game]"
