import type { JsonValue } from "./http";

export interface KnowledgeRetrievalToolInput {
  readonly query: string;
  readonly topK?: number;
  readonly knowledgeBaseIds?: readonly string[];
  readonly documentIds?: readonly string[];
}

export interface KnowledgeRetrievalCitation {
  readonly chunkId: string;
  readonly documentId: string;
  readonly knowledgeBaseId: string;
  readonly source: string;
  readonly excerpt: string;
  readonly metadata: Readonly<Record<string, JsonValue>>;
  readonly vectorRank: number | null;
  readonly vectorScore: number | null;
  readonly bm25Rank: number | null;
  readonly bm25Score: number | null;
  readonly rrfScore: number;
  readonly rerankRank: number;
  readonly rerankScore: number;
  readonly score: number;
}

export interface KnowledgeRetrievalToolOutput {
  readonly results: readonly KnowledgeRetrievalCitation[];
}
