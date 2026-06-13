// Test case for dark fantasy world
test dystopian_fantasy {
  functions [GenWorldRules]
  args {
    type {
      type "dystopian dark fantasy"
      inspiration "Orwell's 1984 totalitarianism meets brutality of Game of Thrones and horrors of cosmic dread, where ancient curses and forgotten gods twist the natural order"
    }
  }
}


test dark_fantasy_world {
  functions [GenWorldRules]
  args {
    type {
      type "dark fantasy"
      inspiration "Gothic horror meets cosmic dread, where ancient curses and forgotten gods twist the natural order"
    }
  }
}

// Test case for sci-fi world
test sci_fi_world {
  functions [GenWorldRules]
  args {
    type {
      type "sci-fi"
      inspiration "Post-scarcity society where consciousness can be uploaded to quantum networks, but something ancient lives in the data streams"
    }
  }
}

// Test case for steampunk world
test steampunk_world {
  functions [GenWorldRules]
  args {
    type {
      type "steampunk"
      inspiration "Victorian-era aesthetic with clockwork automatons, aether-powered airships, and a ruling class of techno-aristocrats"
    }
  }
}

// Test case for elemental fantasy
test elemental_fantasy {
  functions [GenWorldRules]
  args {
    type {
      type "elemental fantasy"
      inspiration "The world is built on the corpse of a primordial elemental, and different cultures draw power from its decaying body parts"
    }
  }
}

// Test case for post-apocalyptic world
test post_apocalyptic_world {
  functions [GenWorldRules]
  args {
    type {
      type "post-apocalyptic"
      inspiration "Biological nanotech plague reshaped reality 200 years ago - now forests grow metal, rivers flow with data, and mutations are currency"
    }
  }
}

// Edge case: Very specific niche genre
test cyberpunk_mythology {
  functions [GenWorldRules]
  args {
    type {
      type "cyberpunk mythology"
      inspiration "Greek gods were actually advanced AI constructs that now rule mega-corporations from orbital platforms"
    }
  }
}

// Edge case: Minimal inspiration text
test minimal_inspiration {
  functions [GenWorldRules]
  args {
    type {
      type "high fantasy"
      inspiration "Dragons and magic"
    }
  }
}

// Batch test all worlds at once
test all_world_types {
  functions [GenWorldRules]
  args {
    type {
      type "multi-genre fusion"
      inspiration "What if Dune met Studio Ghibli's Spirited Away - spice must flow through bathhouse dimensions"
    }
  }
}