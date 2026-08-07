import manifest from "../contract-manifest.json";

export type ErrorCategory =
  | "authentication"
  | "authorization"
  | "business"
  | "validation"
  | "system";

export interface ErrorDefinition {
  readonly code: ErrorCode;
  readonly category: ErrorCategory;
  readonly httpStatus: number;
  readonly defaultMessage: string;
}

export type ErrorCode = keyof typeof manifest.errors;

export const ERROR_DEFINITIONS = manifest.errors as unknown as Readonly<{
  [Code in ErrorCode]: ErrorDefinition & { readonly code: Code };
}>;
