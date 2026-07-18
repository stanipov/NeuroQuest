from pydantic import BaseModel


class PhaseConfig(BaseModel):
    max_iterations: int = 10


class WorldGenConfig(BaseModel):
    concept: PhaseConfig = PhaseConfig(max_iterations=10)
    narrative: PhaseConfig = PhaseConfig(max_iterations=10)


class StartingPlaceConfig(BaseModel):
    context: PhaseConfig = PhaseConfig(max_iterations=5)
    scene: PhaseConfig = PhaseConfig(max_iterations=5)


class LorePipelineConfig(BaseModel):
    world_gen: WorldGenConfig = WorldGenConfig()
    starting_place: StartingPlaceConfig = StartingPlaceConfig()
