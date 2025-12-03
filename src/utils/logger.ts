/* Simple timestamped console logger */
export const logger = {
  info(message: string, meta?: Record<string, unknown>): void {
    console.log(formatLog('INFO', message, meta));
  },
  warn(message: string, meta?: Record<string, unknown>): void {
    console.warn(formatLog('WARN', message, meta));
  },
  error(message: string, meta?: Record<string, unknown>): void {
    console.error(formatLog('ERROR', message, meta));
  }
};

function formatLog(level: string, message: string, meta?: Record<string, unknown>): string {
  const payload = meta ? ` ${JSON.stringify(meta)}` : '';
  return `[${new Date().toISOString()}] [${level}] ${message}${payload}`;
}
