export interface ChatPrompt {
  readonly id: string;
  readonly label: string;
  readonly content: string;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface ChatSkill {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly filename: "SKILL.md";
  readonly content: string;
  readonly metadata: Readonly<Record<string, unknown>>;
  readonly summary: string;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface ChatConfigurationData {
  readonly prompts: readonly ChatPrompt[];
  readonly skills: readonly ChatSkill[];
  readonly selectedPromptId: string | null;
  readonly selectedSkillIds: readonly string[];
}

export interface UpdateChatConfigurationRequest {
  readonly selectedPromptId: string | null;
  readonly selectedSkillIds: readonly string[];
}

export interface CreateChatPromptRequest {
  readonly label: string;
  readonly content: string;
}

export type UpdateChatPromptRequest = CreateChatPromptRequest;

export interface ChatAssetDeleteData {
  readonly deleted: true;
  readonly assetId: string;
}

export const CHAT_SKILL_UPLOAD_POLICY = {
  multipart: { file: "file" },
  filename: "SKILL.md",
  maxBytes: 256 * 1024,
  maxNameCharacters: 64,
  maxDescriptionCharacters: 500,
  maxSummaryCharacters: 240,
  normalizedNamePattern: "^[a-z0-9]+(?:-[a-z0-9]+)*$",
} as const;
