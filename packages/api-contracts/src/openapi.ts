import manifest from "../contract-manifest.json";

export type HttpMethod = "DELETE" | "GET" | "PATCH" | "POST" | "PUT";

export interface OpenApiPathDefinition {
  readonly method: HttpMethod;
  readonly operationId: string;
  readonly successData: string;
}

export type OpenApiPath = keyof typeof manifest.openapi.paths;

export const OPENAPI_PATHS = manifest.openapi.paths as unknown as Readonly<
  Record<OpenApiPath, OpenApiPathDefinition>
>;
