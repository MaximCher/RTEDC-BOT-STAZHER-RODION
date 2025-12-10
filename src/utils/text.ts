export const splitToTelegramChunks = (text: string, maxLen = 1200): string[] => {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) {
    return [];
  }

  const chunks: string[] = [];
  let rest = cleaned;

  while (rest.length > maxLen) {
    let cut = rest.lastIndexOf(' ', maxLen);
    if (cut === -1 || cut < maxLen * 0.5) {
      cut = maxLen;
    }
    chunks.push(rest.slice(0, cut).trim());
    rest = rest.slice(cut).trim();
  }

  if (rest.length) {
    chunks.push(rest);
  }

  return chunks;
};

const MARKDOWN_ESCAPE_REGEX = /([\\_*\\[\\]~`>#+=|{}])/g;

export const escapeMarkdown = (text: string): string =>
  text.replace(MARKDOWN_ESCAPE_REGEX, '\\$1');


