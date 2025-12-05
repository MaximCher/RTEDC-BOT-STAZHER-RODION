import fs from 'fs/promises';
import path from 'path';
import { logger } from '../utils/logger';

export type KnowledgeDirection =
  | 'finance'
  | 'logistics'
  | 'payments'
  | 'analytics'
  | 'subsidies'
  | 'export'
  | 'general';

export interface KnowledgeChunk {
  slug: string;
  source: string;
  title: string;
  direction: KnowledgeDirection;
  content: string;
}

export interface KnowledgeRetrieval {
  context: string;
  articles: string[];
}

const knowledgeDirs = [
  path.resolve(__dirname, '..', 'knowledge'),
  path.resolve(process.cwd(), 'src', 'knowledge')
];

const slugToDirection: Record<string, KnowledgeDirection> = {
  financing: 'finance',
  logistics: 'logistics',
  payments: 'payments',
  partner_check: 'analytics',
  subsidies: 'subsidies',
  export: 'export',
  faq: 'general'
};

const CHUNK_SIZE = 900;
const MAX_CHUNKS = 4;

let knowledgeCache: KnowledgeChunk[] | null = null;

export const loadKnowledgeArticles = async (): Promise<KnowledgeChunk[]> => {
  if (knowledgeCache) {
    return knowledgeCache;
  }

  const aggregated: KnowledgeChunk[] = [];

  for (const dir of knowledgeDirs) {
    try {
      const files = await fs.readdir(dir);

      for (const file of files) {
        if (!file.endsWith('.md')) {
          continue;
        }
        const slug = file.replace(/\.md$/, '');
        const direction = slugToDirection[slug] ?? 'general';
        const raw = await fs.readFile(path.join(dir, file), 'utf-8');
        aggregated.push(...splitIntoChunks(raw, slug, direction));
      }

      if (aggregated.length) {
        knowledgeCache = aggregated;
        return aggregated;
      }
    } catch (error) {
      logger.warn('Knowledge base directory not available', {
        path: dir,
        error: error instanceof Error ? { message: error.message } : error
      });
    }
  }

  logger.error('Knowledge base not found in expected directories');
  knowledgeCache = [];
  return [];
};

export const getRelevantKnowledge = async (
  query: string,
  direction?: KnowledgeDirection,
  maxChars = 2400
): Promise<KnowledgeRetrieval | null> => {
  const chunks = await loadKnowledgeArticles();
  if (!chunks.length) {
    return null;
  }

  const normalizedQuery = query.toLowerCase();
  const keywords = extractKeywords(normalizedQuery);
  const freeTokens = normalizedQuery
    .split(/[\s,.;:!?()]+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 3);

  const scored = chunks
    .map((chunk) => {
      const content = chunk.content.toLowerCase();
      let score = 0;

      if (direction && chunk.direction === direction) {
        score += 3;
      }

      for (const keyword of keywords) {
        if (content.includes(keyword)) {
          score += 2;
        }
      }

      for (const token of freeTokens) {
        if (content.includes(token)) {
          score += 1;
        }
      }

      if (!keywords.length && !freeTokens.length && !direction) {
        score += 1;
      }

      return { chunk, score };
    })
    .sort((a, b) => b.score - a.score);

  const selected: KnowledgeChunk[] = [];
  let remainingChars = maxChars;

  for (const { chunk, score } of scored) {
    if (selected.length >= MAX_CHUNKS || remainingChars <= 0) {
      break;
    }
    if (!chunk.content.trim()) {
      continue;
    }

    if (score <= 0 && selected.length) {
      continue;
    }

    const slice = chunk.content.slice(0, remainingChars);
    if (!slice.length) {
      continue;
    }

    selected.push({ ...chunk, content: slice });
    remainingChars -= slice.length;
  }

  if (!selected.length) {
    return null;
  }

  const context = selected
    .map((chunk) => `[Источник: ${chunk.title}]\n${chunk.content.trim()}`)
    .join('\n\n');

  const articles = Array.from(new Set(selected.map((chunk) => chunk.source)));

  return { context, articles };
};

const splitIntoChunks = (
  raw: string,
  slug: string,
  direction: KnowledgeDirection
): KnowledgeChunk[] => {
  const normalized = raw.replace(/\r\n/g, '\n');
  const docTitleMatch = normalized.match(/^#\s+(.*)$/m);
  const docTitle = docTitleMatch ? docTitleMatch[1].trim() : `Статья ${slug}`;
  const body = normalized.replace(/^#\s+.*$/m, '').trim();

  const sections = extractSections(body);
  const chunks: KnowledgeChunk[] = [];

  const sectionsWithFallback =
    sections.length > 0 ? sections : [{ title: docTitle, content: body }];

  sectionsWithFallback.forEach((section, sectionIndex) => {
    const parts = chunkText(section.content);
    parts.forEach((content, chunkIndex) => {
      if (!content.trim()) {
        return;
      }
      chunks.push({
        slug: `${slug}#${sectionIndex}-${chunkIndex}`,
        source: slug,
        title:
          chunkIndex === 0
            ? section.title || docTitle
            : `${section.title || docTitle} (${chunkIndex + 1})`,
        direction,
        content: content.trim()
      });
    });
  });

  return chunks;
};

const extractSections = (
  body: string
): Array<{ title: string; content: string }> => {
  const lines = body.split('\n');
  let currentTitle = '';
  let buffer: string[] = [];
  const sections: Array<{ title: string; content: string }> = [];

  const flush = () => {
    if (buffer.length) {
      const content = buffer.join('\n').trim();
      if (content) {
        sections.push({ title: currentTitle || '', content });
      }
      buffer = [];
    }
  };

  for (const line of lines) {
    if (line.startsWith('## ')) {
      flush();
      currentTitle = line.replace(/^##\s+/, '').trim();
      continue;
    }
    buffer.push(line);
  }

  flush();
  return sections;
};

const chunkText = (text: string): string[] => {
  const trimmed = text.trim();
  if (!trimmed) {
    return [];
  }
  if (trimmed.length <= CHUNK_SIZE) {
    return [trimmed];
  }

  const chunks: string[] = [];
  let pointer = 0;
  while (pointer < trimmed.length) {
    chunks.push(trimmed.slice(pointer, pointer + CHUNK_SIZE));
    pointer += CHUNK_SIZE;
  }
  return chunks;
};

const extractKeywords = (text: string): string[] => {
  const baseKeywords = [
    'финанс',
    'логист',
    'платеж',
    'банк',
    'партнер',
    'санк',
    'субсид',
    'экспорт',
    'выход',
    'рынок'
  ];
  const tokens = text
    .split(/[\s,.;:!?()-]+/)
    .map((token) => token.trim().toLowerCase())
    .filter(Boolean);

  const matched = new Set<string>();
  for (const token of tokens) {
    for (const keyword of baseKeywords) {
      if (token.includes(keyword)) {
        matched.add(keyword);
      }
    }
  }

  return Array.from(matched);
};

