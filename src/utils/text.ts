const TELEGRAM_HARD_LIMIT = 3500;
const TARGET_CHUNK = 900;

export const limitTelegramLength = (text: string, limit = TELEGRAM_HARD_LIMIT): string => {
  if (text.length <= limit) {
    return text;
  }
  return text.slice(0, limit);
};

export const splitToTelegramChunks = (
  text: string,
  hardLimit = TELEGRAM_HARD_LIMIT,
  targetChunk = TARGET_CHUNK
): string[] => {
  if (text.length <= hardLimit) {
    return [text];
  }

  const sentences = splitIntoSentences(text);
  const chunks: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    const candidate = current ? `${current} ${sentence}` : sentence;
    if (candidate.length > targetChunk && current) {
      chunks.push(current);
      current = sentence;
    } else if (candidate.length > hardLimit) {
      const forced = chunkByHardLimit(sentence, hardLimit);
      if (current) {
        chunks.push(current);
      }
      chunks.push(...forced.slice(0, -1));
      current = forced[forced.length - 1];
    } else {
      current = candidate;
    }
  }

  if (current) {
    chunks.push(current);
  }

  return chunks;
};

const splitIntoSentences = (text: string): string[] => {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) {
    return [];
  }
  const tokens = cleaned.split(/(?<=[.!?…])\s+/g);
  return tokens.map((token) => token.trim()).filter(Boolean);
};

const chunkByHardLimit = (text: string, hardLimit: number): string[] => {
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > hardLimit) {
    chunks.push(remaining.slice(0, hardLimit));
    remaining = remaining.slice(hardLimit);
  }
  if (remaining.length) {
    chunks.push(remaining);
  }
  return chunks;
};

const slicesPush = (chunks: string[], value: string) => {
  if (value.length) {
    chunks.push(value);
  }
};


