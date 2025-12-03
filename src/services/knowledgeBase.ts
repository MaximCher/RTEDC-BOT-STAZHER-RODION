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
  title: string;
  direction: KnowledgeDirection;
  content: string;
}

export interface KnowledgeContextOptions {
  direction?: KnowledgeDirection;
  freeText?: string;
  maxChars?: number;
}

export interface KnowledgeSelection {
  context: string;
  slugs: string[];
}

const knowledgeDirs = [
  path.resolve(__dirname, '..', 'knowledge'),
  path.resolve(process.cwd(), 'src', 'knowledge')
];
let knowledgeCache: KnowledgeChunk[] | null = null;

const slugToDirection: Record<string, KnowledgeDirection> = {
  financing: 'finance',
  logistics: 'logistics',
  payments: 'payments',
  partner_check: 'analytics',
  subsidies: 'subsidies',
  export: 'export',
  faq: 'general'
};

export const loadKnowledgeArticles = async (): Promise<KnowledgeChunk[]> => {
  if (knowledgeCache) {
    return knowledgeCache;
  }

  for (const dir of knowledgeDirs) {
    try {
      const files = await fs.readdir(dir);
      const articles: KnowledgeChunk[] = [];

      for (const file of files) {
        if (!file.endsWith('.md')) {
          continue;
        }
        const slug = file.replace(/\.md$/, '');
        const direction = slugToDirection[slug] ?? 'general';
        const raw = await fs.readFile(path.join(dir, file), 'utf-8');
        const titleMatch = raw.match(/^#\s+(.*)$/m);
        const title = titleMatch ? titleMatch[1].trim() : `Статья ${slug}`;

        articles.push({
          slug,
          title,
          direction,
          content: raw.trim()
        });
      }

      if (articles.length) {
        knowledgeCache = articles;
        return articles;
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

export const selectKnowledgeForContext = async (
  options: KnowledgeContextOptions
): Promise<KnowledgeSelection | null> => {
  const articles = await loadKnowledgeArticles();
  if (!articles.length) {
    return null;
  }

  const { direction, freeText, maxChars = 2500 } = options;
  const normalizedText = freeText?.toLowerCase() ?? '';
  const keywords = extractKeywords(normalizedText);

  let candidates = direction
    ? articles.filter((article) => article.direction === direction)
    : [...articles];

  if (keywords.length) {
    candidates = candidates
      .map((article) => ({
        article,
        score: keywords.reduce((acc, keyword) => {
          if (article.content.toLowerCase().includes(keyword)) {
            return acc + 1;
          }
          return acc;
        }, 0)
      }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((entry) => entry.article);
  }

  if (!candidates.length && direction) {
    candidates = articles.filter((article) => article.direction === direction);
  }

  if (!candidates.length) {
    return null;
  }

  const selected: KnowledgeChunk[] = [];
  let remainingChars = maxChars;

  for (const article of candidates) {
    if (selected.length >= 2) {
      break;
    }
    const snippet = article.content.slice(0, Math.floor(remainingChars / (2 - selected.length)));
    if (!snippet.length) {
      break;
    }
    selected.push({
      ...article,
      content: snippet
    });
    remainingChars -= snippet.length;
  }

  if (!selected.length) {
    return null;
  }

  const context = selected
    .map(
      (article) => `[Источник: ${article.title}]\n${article.content.trim()}\n`
    )
    .join('\n');

  return {
    context,
    slugs: selected.map((article) => article.slug)
  };
};

const extractKeywords = (text: string): string[] => {
  const baseKeywords = ['финанс', 'логист', 'платеж', 'банк', 'партнер', 'санк', 'субсид', 'экспорт'];
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

