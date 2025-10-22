import random
import time
from typing import Dict, List

from llm_rpg.gui.chat import HookResponse


def user_input_process_mock(user_input: str) -> Dict[str, str]:
    """Enhanced input processing with thinking emulation"""
    # Emulate parsing and understanding
    time.sleep(0.4)  # Processing delay

    # Add RPG-style processing effects
    processing_phrases = [
        f"\n*The mage studies your words carefully*",
        f"\n*Ancient runes glow as your message is analyzed*",
        f"\n*The spirit guide nods slowly*"
    ]
    roles = ['user', 'Ctulhu', 'Aragorn', 'Sauron']
    input_processing_status = ['done','continue']

    # Return enriched input with processing flavor
    dummy_response = {
        "message": random.choice(processing_phrases),
        "role": random.choice(roles),
        "message_status": "success",
        "input_processing_status": random.choice(input_processing_status)

    }

    return dummy_response


def ai_response_mock(responses: List[HookResponse]):
    """Enhanced RPG response generator with dramatic pacing"""
    # Initial delay before responding
    time.sleep(1.2)

    # Stage 1: Acknowledgment
    yield f"\n*adjusts robes* Your words about..."
    time.sleep(0.01)

    # Stage 2: Dramatic build-up
    dramatic_pauses = [
        "\n*casts divination spell*",
        "\n*consults ancient tome*",
        "\n*gazes into crystal ball*"
    ]
    yield random.choice(dramatic_pauses)
    time.sleep(0.15)

    # Stage 3: Revelation
    revelations = [
        "\nThe spirits reveal...",
        "\nThe stars align to show...",
        "\nMy magical senses perceive..."
    ]
    yield random.choice(revelations)
    time.sleep(0.8)

    # Stage 4: Actual response
    response_body = [
        "\nYou must seek the lost artifact in the Caves of Despair!",
        "\nBeware! The dark lord's minions are watching you...",
        "\nI foresee a great battle in your near future!",
        "\nThe answer lies eastward, beyond the Mountains of Madness."
    ]
    yield random.choice(response_body)
    time.sleep(0.5)

    # Final prompt
    yield "\n\n*leans forward* What will you do next, adventurer?"
