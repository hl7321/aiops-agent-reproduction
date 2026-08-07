export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface PublicConfig {
  readonly title: string;
  readonly apiBaseUrl: string;
  readonly analyticsPublicKey: string;
}

export function deepMerge(
  base: Record<string, JsonValue>,
  override: Record<string, JsonValue>,
): Record<string, JsonValue>;

export function loadMergedConfig(
  projectPath: string,
  userPath: string,
): Promise<Record<string, JsonValue>>;

export function toPublicConfig(config: Record<string, JsonValue>): PublicConfig;
