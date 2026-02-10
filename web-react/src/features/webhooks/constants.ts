export const SUPPORTED_EVENTS = [
  {
    group: "Model Registry",
    events: [
      "registered_model.created",
      "model_version.created",
      "model_version_tag.set",
      "model_version_tag.deleted",
      "model_version_alias.created",
      "model_version_alias.deleted",
    ],
  },
  {
    group: "Prompt Registry",
    events: [
      "prompt.created",
      "prompt_version.created",
      "prompt_tag.set",
      "prompt_tag.deleted",
      "prompt_version_tag.set",
      "prompt_version_tag.deleted",
      "prompt_alias.created",
      "prompt_alias.deleted",
    ],
  },
];
