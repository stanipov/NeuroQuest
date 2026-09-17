// Learn more about clients at https://docs.boundaryml.com/docs/snippets/clients/overview
// See /ext4/src/beellama.cpp for how reasoning is handled:
// - top-level `reasoning_effort: "none"` only disables thinking (server-common.cpp:1090)
// - Qwen3.8-27B Unsloth/HauhauCS uses Jinja vars via chat_template_kwargs:
//   `reasoning_effort` ("none"|  "medium"| "medium""|"high"|"max") and `enable_thinking` bool
//   are read from chat_template_kwargs (beellama --chat-template-kwargs '{"reasoning_effort": "medium""}')
// - `preserve_reasoning` bool maps via common/chat.cpp:919 -> caps_apply_preserve_reasoning()
//   to preserve_thinking/clear_thinking/drop_thinking (jinja/caps.cpp:22). Server default
//   is --reasoning-preserve (llama_swap_cfg.yaml:281,321). Per-request override via kwargs.
// - reasoning_budget enforced via common/sampling.cpp:325 sampler, exposed as top-level
//   reasoning_budget_tokens/message (server-common.cpp:1128, server-schema.cpp:433).

client<llm> GenericLoreLLM {
  provider openai-generic
  retry_policy Constant
  options {
    base_url env.BASE_URL
    api_key env.API_KEY
    model env.LORE_GENERIC_LLM
    temperature 1.0

    reasoning_effort:  "medium"
    chat_template_kwargs {
      "enable_thinking" true
      "reasoning_effort"   "medium"
      "preserve_reasoning" true
    }
    //reasoning_budget_tokens 1024
    //reasoning_budget_message "Thinking budget exceeded. Summarize thoughts and answer now."

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

    reasoning_effort:  "medium"
    chat_template_kwargs {
      "enable_thinking" true
      "reasoning_effort"   "medium"
      "preserve_reasoning" true
    }
    //reasoning_budget_tokens 1024
    //reasoning_budget_message "Thinking budget exceeded. Summarize thoughts and answer now."
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

    enable_thinking: false
    reasoning_effort:  "medium"
    chat_template_kwargs {
      "enable_thinking" false
      "reasoning_effort"   "medium"
      "preserve_reasoning" true
    }
    //reasoning_budget_tokens 1024
    //reasoning_budget_message "Thinking budget exceeded. Summarize thoughts and answer now."

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

    enable_thinking: false
    reasoning_effort:  "medium"
    chat_template_kwargs {
      "enable_thinking" false
      "reasoning_effort"   "medium"
      "preserve_reasoning" true
    }
    //reasoning_budget_tokens 1024
    //reasoning_budget_message "Thinking budget exceeded. Summarize thoughts and answer now."

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
