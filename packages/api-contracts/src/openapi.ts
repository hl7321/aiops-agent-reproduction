import manifest from "../contract-manifest.json";
import type { ErrorCode } from "./errors";

export type HttpMethod = "DELETE" | "GET" | "PATCH" | "POST" | "PUT";

export interface OpenApiPathDefinition {
  readonly method: HttpMethod;
  readonly operationId: string;
  readonly successData: string;
  readonly security?: readonly OpenApiSecuritySchemeName[];
  readonly errors?: readonly ErrorCode[];
}

export interface OpenApiSecuritySchemeDefinition {
  readonly type: "http";
  readonly scheme: "bearer";
}

export type OpenApiSecuritySchemeName = keyof typeof manifest.openapi.securitySchemes;

export type OpenApiPath = keyof typeof manifest.openapi.paths;

export const OPENAPI_PATHS = manifest.openapi.paths as unknown as Readonly<
  Record<OpenApiPath, OpenApiPathDefinition>
>;

export const OPENAPI_SECURITY_SCHEMES = manifest.openapi.securitySchemes as unknown as Readonly<
  Record<OpenApiSecuritySchemeName, OpenApiSecuritySchemeDefinition>
>;

export interface OpenApiOperation {
  readonly path: string;
  readonly method: HttpMethod;
  readonly operationId: string;
  readonly successData: string;
  readonly security: readonly OpenApiSecuritySchemeName[];
  readonly errors: readonly ErrorCode[];
}

export const KNOWLEDGE_OPENAPI_OPERATIONS = manifest.openapi.knowledgeOperations as readonly OpenApiOperation[];
export const DOCUMENT_INDEX_OPENAPI_OPERATIONS =
  manifest.openapi.documentIndexOperations as readonly OpenApiOperation[];
export const CHAT_OPENAPI_OPERATIONS =
  manifest.openapi.chatOperations as readonly OpenApiOperation[];
export const CHAT_CONFIGURATION_OPENAPI_OPERATIONS =
  manifest.openapi.chatConfigurationOperations as readonly OpenApiOperation[];
export const MCP_OPENAPI_OPERATIONS =
  manifest.openapi.mcpOperations as readonly OpenApiOperation[];
export const ALERT_OPENAPI_OPERATIONS =
  manifest.openapi.alertOperations as readonly OpenApiOperation[];
export { CHAT_SKILL_UPLOAD_POLICY } from "./chat-configuration";

export interface ProtectedPathPolicy {
  readonly security: OpenApiSecuritySchemeName;
  readonly errors: readonly ErrorCode[];
}

export const PROTECTED_PATH_POLICY = manifest.openapi.protectedPathPolicy as unknown as Readonly<
  ProtectedPathPolicy
>;
