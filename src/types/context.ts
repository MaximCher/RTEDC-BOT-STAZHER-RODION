import { Context } from 'telegraf';
import { SessionData } from './session';

export interface CustomContext extends Context {
  session: SessionData;
  setSession: (next: SessionData) => void;
}
