import OpenAI from 'openai';
import { supabaseClient } from './supabaseClient';
import { logger } from '../utils/logger';

export interface SrvtRagChunk {
  id: number;
  content: string;
  url: string | null;
  similarity: number;
}

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const openaiClient = OPENAI_API_KEY ? new OpenAI({ apiKey: OPENAI_API_KEY }) : null;

export async function searchSrvtRag(
  query: string,
  options?: { matchCount?: number; minSimilarity?: number }
): Promise<SrvtRagChunk[]> {
  const matchCount = options?.matchCount ?? 5;
  const minSimilarity = options?.minSimilarity ?? 0.1;

  if (!supabaseClient) {
    logger.warn('vector_search_no_supabase_client');
    return [];
  }
  if (!openaiClient) {
    logger.warn('vector_search_no_openai_client');
    return [];
  }

  const embedding = await buildEmbedding(query);
  if (!embedding) {
    return [];
  }

  try {
    console.log('[RAG] call match_documents', {
      matchCount,
      minSimilarity,
      embeddingLength: embedding.length
    });

    const { data, error } = await supabaseClient.rpc('match_documents', {
      query_embedding: embedding,
      match_count: matchCount,
      min_similarity: minSimilarity
    });

    console.log('[RAG] match_documents result', {
      rows: data?.length ?? 0,
      error
    });

    if (error) {
      logger.error('vector_search_supabase_error', { error });
      return [];
    }

    if (!Array.isArray(data)) {
      return [];
    }

    return data
      .map((row) => ({
        id: typeof row.id === 'number' ? row.id : 0,
        content: typeof row.content === 'string' ? row.content : '',
        url: typeof row.url === 'string' ? row.url : null,
        similarity:
          typeof row.similarity === 'number'
            ? Math.max(0, Math.min(1, row.similarity))
            : 0
      }))
      .filter((item) => item.content && item.similarity >= minSimilarity);
  } catch (error) {
    logger.error('vector_search_unexpected_error', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return [];
  }
}

const buildEmbedding = async (text: string): Promise<number[] | null> => {
  if (!openaiClient) {
    return null;
  }
  const trimmed = text?.trim();
  if (!trimmed) {
    return null;
  }
  try {
    const response = await openaiClient.embeddings.create({
      model: 'text-embedding-3-small',
      input: trimmed
    });
    const embedding = response.data?.[0]?.embedding;
    return Array.isArray(embedding) ? embedding : null;
  } catch (error) {
    logger.error('vector_search_embedding_failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return null;
  }
};

