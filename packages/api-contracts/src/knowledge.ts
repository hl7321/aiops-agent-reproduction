export type ChunkingStrategy = "fixed-character" | "markdown-heading" | "paragraph";

export type ChunkingConfig =
  | { readonly strategy: "fixed-character"; readonly maxCharacters: number; readonly overlap: number }
  | { readonly strategy: "markdown-heading" | "paragraph" };

export interface KnowledgeBase {
  readonly id: string;
  readonly name: string;
  readonly isDefault: true;
}

export interface KnowledgeBaseListData { readonly items: readonly KnowledgeBase[] }

export interface KnowledgeDocument {
  readonly id: string;
  readonly knowledgeBaseId: string;
  readonly filename: string;
  readonly sizeBytes: number;
  readonly mimeType: "text/markdown" | "application/pdf";
  readonly sha256: string;
  readonly uploadedAt: string;
  readonly indexStatus: import("./document-indexing").DocumentIndexStatus;
  readonly chunkingConfig: ChunkingConfig;
}

export interface KnowledgeDocumentListData { readonly items: readonly KnowledgeDocument[] }
export interface ChunkPreviewItem { readonly index: number; readonly excerpt: string; readonly metadata: Readonly<Record<string, unknown>> }
export interface ChunkPreviewData { readonly totalChunks: number; readonly items: readonly ChunkPreviewItem[] }

export const KNOWLEDGE_UPLOAD_POLICY = {
  maxBytes: 10 * 1024 * 1024,
  allowedTypes: { ".md": "text/markdown", ".pdf": "application/pdf" },
  multipart: { file: "file", chunkingConfig: "chunkingConfig", overwrite: "overwrite" },
  strategies: ["fixed-character", "markdown-heading", "paragraph"],
} as const;
