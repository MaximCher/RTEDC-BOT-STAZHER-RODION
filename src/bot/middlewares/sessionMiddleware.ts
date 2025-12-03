import { MiddlewareFn } from 'telegraf';
import { CustomContext } from '../../types/context';
import { SessionData, initialSessionState } from '../../types/session';

const sessions = new Map<number, SessionData>();

export const sessionMiddleware = (): MiddlewareFn<CustomContext> => {
  return async (ctx, next) => {
    const userId = ctx.from?.id;
    if (!userId) {
      return next();
    }

    if (!sessions.has(userId)) {
      sessions.set(userId, initialSessionState());
    }

    const currentSession = sessions.get(userId) ?? initialSessionState();
    ctx.session = currentSession;
    ctx.setSession = (nextSession: SessionData) => {
      sessions.set(userId, nextSession);
      ctx.session = nextSession;
    };

    try {
      await next();
    } finally {
      sessions.set(userId, ctx.session);
    }
  };
};
