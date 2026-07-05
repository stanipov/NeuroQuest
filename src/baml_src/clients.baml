// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview


client<llm> GenericLoreLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.LORE_GENERIC_LLM
    temperature 1.0
    // response_validation "relaxed"
  }
}


client<llm> NarrateWorldLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.WORLD_NARRATE_LLM
    temperature 0.5
    // response_validation "relaxed"
  }
}


client<llm> WorldConceptLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.WORLD_CONCEPT_GENERATOR_LLM
    temperature 0.9
    // response_validation "relaxed"
  }
}


client<llm> LoreLLMCritique {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.WORLD_CONCEPT_CRITIC_LLM
    temperature 0.3
    top_p 0.95
    // response_validation "relaxed"
  }
}


// Retry policies
// https://docs.boundaryml.com/docs/snippets/clients/retry
retry_policy Constant {
  max_retries 3
  strategy {
    type constant_delay
    delay_ms 200
  }
}

retry_policy Exponential {
  max_retries 2
  strategy {
    type exponential_backoff
    delay_ms 300
    multiplier 1.5
    max_delay_ms 10000
  }
}