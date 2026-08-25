package AuditoryMemoryFlow {
  part sound_observation;
  part working_memory_node;
  part long_term_memory_node;
  part persistent_ltm_json;
  part rqt_plugin;

  flow sound_observation -> working_memory_node;
  flow working_memory_node -> rqt_plugin : wm_state, graph_viz;
  flow working_memory_node -> long_term_memory_node : consolidation;
  flow long_term_memory_node -> persistent_ltm_json : learned_patterns;
  flow long_term_memory_node -> rqt_plugin : ltm_patterns;
}
