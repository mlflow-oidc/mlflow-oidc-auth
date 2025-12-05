export type ExperimentListItem = {
  id: string;
  name: string;
  tags: Record<string, string>;
};

export type ModelListItem = {
  aliases: string;
  description: string;
  name: string;
  tags: Record<string, string>;
};

export type PromptListItem = ModelListItem;
