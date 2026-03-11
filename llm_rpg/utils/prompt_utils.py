import json
import time
import logging
from copy import deepcopy as dCP
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def cooldown_llm_temp(temp: float, dt: float, min_temp: float = 0.5) -> float:
    """
    Reduces temperature by a step amount, with a configurable minimum floor.

    Args:
        temp: Current temperature value (typically 0.0 to 2.0 for most LLMs)
        dt: Step decrease amount (e.g., 0.1 for gradual cooling)
        min_temp: Minimum temperature floor (default: 0.5)

    Returns:
        New temperature value, capped at minimum of min_temp

    Example:
        >>> cooldown_llm_temp(0.7, 0.1)
        0.6
        >>> cooldown_llm_temp(0.5, 0.1)
        0.5  # Capped at minimum
        >>> cooldown_llm_temp(0.6, 0.1, min_temp=0.3)
        0.5  # Uses custom minimum
    """
    return max(min_temp, temp - dt)


def enhance_system_message_for_retry(
    messages: List[Dict[str, str]],
    response_model,
    attempt: int,
    max_retries: int,
    last_error: Exception = None,
) -> List[Dict[str, str]]:
    """
    Enhances system message with progressively stricter JSON enforcement.

    The enhancement level is calculated based on current attempt relative to
    max_retries, providing increasingly strict guidance as retries continue.
    This helps LLMs understand the expected output format when initial attempts fail.

    Enhancement Levels:
        Level 1 (early retry): Adds schema reminder with full JSON schema
        Level 2 (mid retry): Adds explicit example structure with field values
        Level 3 (late retry): Maximum strictness with field-by-field breakdown

    Args:
        messages: Current message list (will be modified in-place)
        response_model: Pydantic model for schema extraction and example generation
        attempt: Current retry attempt number (0-based, so first retry is attempt=1)
        max_retries: Total maximum retry attempts configured
        last_error: Previous error that caused the retry (can be used for
                   error-specific guidance in future enhancements)

    Returns:
        Enhanced message list with additional system guidance appended to
        existing system message or as new system message if none exists

    Note:
        This function modifies the messages list in-place and returns it
        for convenience. Callers should pass a copy if original preservation is needed.
    """
    # Find existing system message or create new one
    system_msg = next((m for m in messages if m.get("role") == "system"), None)

    # Calculate enhancement level based on progress through retries
    # attempt=1 is first retry, attempt=max_retries-1 is last attempt
    # Maps retry progress (0.0 to 1.0) to enhancement levels 1, 2, or 3
    retry_progress = attempt / max(max_retries - 1, 1)
    enhancement_level = min(int(retry_progress * 3) + 1, 3)

    if enhancement_level == 1:
        # First retry (early): Add schema reminder
        schema_str = json.dumps(response_model.model_json_schema(), indent=2)
        enhancement = f"""

IMPORTANT: Your previous response was not valid JSON. Please output ONLY valid JSON matching this exact schema:

{schema_str}

Do NOT include markdown formatting, code blocks, or any explanatory text."""

    elif enhancement_level == 2:
        # Second retry (mid): Add explicit example
        schema = response_model.model_json_schema()
        properties = schema.get("properties", {})

        # Build a minimal example structure
        example_parts = []
        for key, value in properties.items():
            if "default" in value:
                example_parts.append(f'  "{key}": {json.dumps(value["default"])}')
            elif value.get("type") == "array":
                example_parts.append(f'  "{key}": []')
            elif value.get("type") == "string":
                example_parts.append(f'  "{key}": ""')
            else:
                example_parts.append(f'  "{key}": null')

        example_str = "{\n" + ",\n".join(example_parts) + "\n}"

        enhancement = f"""

CRITICAL: Previous attempts failed. You MUST output valid JSON only.

Required structure (example):
{example_str}

Rules:
1. Output ONLY the JSON object, nothing else
2. No markdown code blocks (no ```json or ```)
3. No introductory or explanatory text
4. Ensure all required fields are present"""

    else:
        # Third+ retry (late): Maximum strictness with field-by-field breakdown
        schema = response_model.model_json_schema()
        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})

        field_descriptions = []
        for field in required_fields:
            prop = properties.get(field, {})
            desc = prop.get("description", "no description")
            ftype = prop.get("type", "any")
            field_descriptions.append(f"- {field} ({ftype}): {desc}")

        enhancement = f"""

EMERGENCY MODE: Multiple attempts have failed. Follow these instructions EXACTLY:

Required JSON fields:
{chr(10).join(field_descriptions)}

Output Format:
{{
  "FIELD1": "value",
  "FIELD2": "value"
}}

NO MARKDOWN. NO CODE BLOCKS. NO TEXT BEFORE OR AFTER THE JSON.
JUST THE RAW JSON OBJECT."""

    # Add enhancement to existing system message or prepend new one
    if system_msg:
        system_msg["content"] = system_msg["content"] + enhancement
    else:
        new_system = {"role": "system", "content": enhancement}
        messages.insert(0, new_system)

    return messages


def generate_with_retry(
    client,
    messages: List[Dict[str, str]],
    response_model,
    max_retries: int = 3,
    fallback_value=None,
    component_name: str = "",
    temperature_cooldown_step: float = 0.1,
    temperature_min: float = 0.5,
    **client_kw,
) -> Dict[str, Any]:
    """
    Attempt structured output generation with configurable retries and fallback.

    This function provides robust error handling for LLM structured output by:
    1. Retrying failed attempts with progressive message enhancement
    2. Gradually reducing temperature for more deterministic output on retries
    3. Falling back to default values if all attempts fail

    On each retry attempt:
    - System message is enhanced with increasingly strict JSON guidance
    - Temperature is reduced by cooldown_step (capped at temperature_min)
    - A short delay (0.5s) occurs between attempts

    Args:
        client: LLM client instance with struct_output() method
        messages: Original message list for the LLM call (will not be modified)
        response_model: Pydantic BaseModel class defining expected output structure
        max_retries: Maximum number of total attempts including initial (default: 3)
                    Must be >= 1. Higher values provide more chances but increase latency.
        fallback_value: Default Pydantic model instance to return if all retries fail.
                       If None and all retries fail, the last exception is raised.
        component_name: Descriptive name for logging (e.g., "NPC Rules: Silas Reed")
        temperature_cooldown_step: Temperature reduction amount per retry attempt
                                   (default: 0.1). Use 0.0 to disable cooling.
        temperature_min: Minimum temperature floor during cooldown (default: 0.5).
                        Prevents temperature from going too low and losing creativity.
        **client_kw: Additional keyword arguments passed to client.struct_output()
                    Common options include:
                    - temperature: Initial temperature (default varies by client)
                    - max_tokens: Maximum tokens to generate
                    - top_p: Nucleus sampling parameter

    Returns:
        Dict with keys:
            - 'message': Parsed response as dict (from Pydantic model_dump())
            - 'stats': Dict with token usage and timing info:
                - 'prompt_tokens': Number of tokens in prompt
                - 'eval_tokens': Number of tokens in response
                - 'prompt_eval_duration': Prompt processing time in ms
                - 'eval_duration': Generation time in ms

        If fallback is used, stats will have zero values.

    Raises:
        Exception: The last exception if all retries fail and no fallback_value provided

    Example:
        from llm_rpg.prompts.lore_generation import gen_npc_behavior_msgs
        from llm_rpg.prompts.response_models import NPCBehaviorRulesModel

        msgs = gen_npc_behavior_msgs(npc_data)
        result = _generate_with_retry(
             client=llm_client,
             messages=msgs,
             response_model=NPCBehaviorRulesModel,
             max_retries=5,
             fallback_value=default_rules,
             component_name="NPC: Silas Reed",
             temperature_cooldown_step=0.1,
             temperature_min=0.3
        )
        print(result['message'])  # Dict of NPC rules

    Note:
        This function makes a deep copy of messages to avoid modifying the caller's
        original list. System message enhancements are applied to the copy only.
    """
    last_error = None

    # Extract initial temperature from kwargs or use default
    current_temp = client_kw.get("temperature", 0.7)

    # Prepare working messages - make a deep copy so we don't modify the original
    working_messages = dCP(messages)

    for attempt in range(max_retries):
        try:
            logger.debug(
                f"{component_name}: Structured output attempt {attempt + 1}/{max_retries}"
                + (f" (temp={current_temp:.2f})" if attempt > 0 else "")
            )

            # On retry attempts (attempt > 0), enhance system message
            if attempt > 0:
                working_messages = enhance_system_message_for_retry(
                    working_messages, response_model, attempt, max_retries, last_error
                )

                # Apply temperature cooldown on retries
                new_temp = cooldown_llm_temp(
                    current_temp, temperature_cooldown_step, temperature_min
                )
                if new_temp != current_temp:
                    logger.info(
                        f"{component_name}: Cooling down temperature from {current_temp:.2f} to {new_temp:.2f}"
                    )
                    current_temp = new_temp
                    client_kw["temperature"] = current_temp

            response = client.struct_output(
                working_messages, response_model, **client_kw
            )

            if response["message"] is not None:
                logger.info(
                    f"{component_name}: Generated successfully on attempt {attempt + 1}"
                    + (f" with temp={current_temp:.2f}" if attempt > 0 else "")
                )
                # Convert Pydantic model to dict for JSON serialization
                response["message"] = response["message"].model_dump()
                return response

            last_error = ValueError("struct_output returned None message")
            logger.warning(
                f"{component_name}: Attempt {attempt + 1} failed - message is None"
            )

        except Exception as e:
            last_error = e
            logger.warning(
                f"{component_name}: Attempt {attempt + 1} failed - {type(e).__name__}: {e}"
            )

        if attempt < max_retries - 1:
            time.sleep(0.5)

    logger.error(
        f"{component_name}: All {max_retries} attempts failed. Last error: {last_error}"
    )

    if fallback_value is not None:
        logger.info(f"{component_name}: Using fallback/default values")
        # Convert Pydantic model to dict for JSON serialization
        fallback_value = fallback_value.model_dump()
        return {
            "message": fallback_value,
            "stats": {"prompt_tokens": 0, "eval_tokens": 0},
        }

    if last_error is not None:
        raise last_error
    raise RuntimeError(
        f"{component_name}: Generation failed after {max_retries} attempts"
    )
