from src.baml_client.async_client import b
from src.baml_client.types import WorldTypes, WorldConcept, WorldConceptGenHistory
from loguru import logger

MAX_ITERATIONS = 10

class WorldConceptWriter:
    """
    A simple writer-reflexion agentic loop to generate logically coherent world concepts.
    """
    def __init__(self, max_iteration: int = MAX_ITERATIONS):
        self.max_iteration = max_iteration

    async def run(self, world_type: WorldTypes) -> WorldConcept:
        result = await b.GenWorldConcept(type=world_type)
        history: list[WorldConceptGenHistory] = []

        for i in range(self.max_iteration):
            logger.debug(f"{i+1}/{self.max_iteration}: draft. Text: {result}")
            critique_result = await b.WorldConceptCritique(type=world_type, concept=result, history=history)
            if critique_result.is_satisfied:
                logger.debug(f"{i+1}/{self.max_iteration}: critic is satisfied")
                break
            logger.debug(f"{i+1}/{self.max_iteration}: feedback: {critique_result.feedback}")
            history.append(WorldConceptGenHistory(draft=result, critique=critique_result))
            result = await b.GenWorldConcept(type=world_type, history=history)

        return result
