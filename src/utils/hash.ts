export const stableHash = (input: string): number => {
  let hash = 0;
  const normalized = input || '';
  for (let i = 0; i < normalized.length; i += 1) {
    hash = (hash << 5) - hash + normalized.charCodeAt(i);
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash) || 1;
};

