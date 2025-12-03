const PHONE_REGEX = /^\+?\d[\d\s\-()]{6,18}$/;

const MESSENGER_TOKENS = ['@', 't.me', 'whatsapp', 'ватсап', 'telegram', 'телеграм'];

export const isValidContact = (input: string): boolean => {
  const value = input.trim();
  if (!value) {
    return false;
  }

  const lower = value.toLowerCase();

  if (MESSENGER_TOKENS.some((token) => lower.includes(token))) {
    return true;
  }

  if (PHONE_REGEX.test(value)) {
    const digitsCount = value.replace(/\D/g, '').length;
    return digitsCount >= 7;
  }

  return false;
};

