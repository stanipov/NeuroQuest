from src.baml_client.async_client import b
from src.baml_client.types import WorldTypes, WorldConcept, WorldNarrative, WorldNarrativeGenHistory
from loguru import logger

MAX_ITERATIONS = 10


class WorldNarrativeWriter:
    """
    A writer-critic agentic loop to generate faithful world narratives from world concepts.
    """

    def __init__(self, max_iteration: int = MAX_ITERATIONS):
        self.max_iteration = max_iteration

    async def run(self, world_type: WorldTypes, concept: WorldConcept) -> WorldNarrative:
        result = await b.NarrateWorld(world_type=world_type, concept=concept)
        history: list[WorldNarrativeGenHistory] = []

        for i in range(self.max_iteration):
            logger.debug(f"{i+1}/{self.max_iteration}: draft. Text: {result}")
            critique_result = await b.NarrateWorldCritique(concept=concept, narrative=result, history=history)
            if critique_result.is_satisfied:
                logger.debug(f"{i+1}/{self.max_iteration}: critic is satisfied")
                break
            logger.debug(f"{i+1}/{self.max_iteration}: feedback: {critique_result.feedback}")
            history.append(WorldNarrativeGenHistory(draft=result, critique=critique_result))
            result = await b.NarrateWorld(world_type=world_type, concept=concept, history=history)

        return result
