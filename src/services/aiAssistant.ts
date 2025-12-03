import OpenAI from 'openai';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions';
import { Direction } from '../types/lead';
import { logger } from '../utils/logger';
import { KnowledgeDirection } from './knowledgeBase';

export type AiDirection = Direction;

export interface AiCaseResult {
  direction: AiDirection;
  summary: string;
  advice: string;
}

export interface AiContextOptions {
  direction?: KnowledgeDirection;
  kbContext?: string | null;
}

const BASE_PROMPT = `
Ты — AI-консультант Совета по развитию внешней торговли (СРВТ).
Говори профессионально и по делу. По тексту предпринимателя:
1. Определи направление (finance | logistics | payments | analytics | other).
2. Сформулируй summary (1–3 предложения) — что происходит и почему это важно.
3. Дай практический advice (1–3 предложения) и мягко предложи передать кейс эксперту СРВТ через бота.
Если указан блок KB_CONTEXT — используй только эти данные как главный источник.
Если информация не покрывает запрос, опирайся на общий опыт и явно упомяни, что нужен разбор с экспертом.

Ответ строго в формате JSON:
{
  "direction": "finance | logistics | payments | analytics | other",
  "summary": "текст",
  "advice": "текст"
}

Никаких дополнительных комментариев.`;

const fallbackResponse = (text: string): AiCaseResult => ({
  direction: 'other',
  summary: text.slice(0, 300) || 'Зафиксировал ваш кейс.',
  advice:
    'Это предварительная оценка по общему опыту. Рекомендуем передать кейс эксперту СРВТ для детального разбора — это можно сделать через кнопку в боте.'
});

const apiKey = process.env.OPENAI_API_KEY;
const openaiClient = apiKey ? new OpenAI({ apiKey }) : null;

export const analyzeCase = async (
  text: string,
  options: AiContextOptions = {}
): Promise<AiCaseResult> => {
  if (!openaiClient) {
    return fallbackResponse(text);
  }

  try {
    const messages = buildMessages(text, options);
    const response = await openaiClient.chat.completions.create({
      model: 'gpt-4o-mini',
      messages,
      temperature: 0.3,
      max_tokens: 350
    });

    const content = response.choices[0]?.message?.content ?? '{}';
    const parsed = JSON.parse(content) as AiCaseResult;

    if (!parsed.direction || !parsed.summary || !parsed.advice) {
      throw new Error('AI response missing required fields');
    }

    return parsed;
  } catch (error) {
    logger.error('AI case analysis failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    return fallbackResponse(text);
  }
};

const buildMessages = (
  text: string,
  options: AiContextOptions
): ChatCompletionMessageParam[] => {
  const systemBlocks = [BASE_PROMPT];

  if (options.direction) {
    systemBlocks.push(`Потенциальное направление запроса: ${options.direction}.`);
  }

  if (options.kbContext) {
    systemBlocks.push(`KB_CONTEXT:\n${options.kbContext}`);
  }

  const systemContent = systemBlocks.join('\n\n');

  return [
    { role: 'system', content: systemContent },
    { role: 'user', content: text }
  ];
};
