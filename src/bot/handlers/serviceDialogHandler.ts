import { CustomContext } from '../../types/context';
import { resetFlow, ServiceDialogState, SolutionDialogTurn } from '../../types/session';
import { ServiceCategory } from '../../types/service';
import {
  SERVICE_PLAYBOOK,
  isServiceCategory
} from '../../config/servicePlaybook';
import { serviceDialogKeyboard } from '../keyboards/services';
import { nextServiceConsultationStep } from '../../services/aiAssistant';
import { logger } from '../../utils/logger';
import { splitToTelegramChunks } from '../../utils/text';

const MAX_CLARIFY_TURNS = 3;

export const startServiceDialog = async (
  ctx: CustomContext,
  category: ServiceCategory
): Promise<void> => {
  const playbook = SERVICE_PLAYBOOK[category];
  if (!playbook) {
    return;
  }
  resetFlow(ctx.session, 'service_consultation');
  const state: ServiceDialogState = {
    category,
    dialog: [],
    turnCount: 0,
    aiReady: false,
    completed: false
  };
  ctx.session.serviceDialog = state;
  appendTurn(state.dialog, 'assistant', playbook.intro);
  await sendChunkedReplies(ctx, playbook.intro, serviceDialogKeyboard(category, 'clarify'));
};

export const handleServiceDialogText = async (ctx: CustomContext): Promise<boolean> => {
  if (ctx.session.flow !== 'service_consultation') {
    return false;
  }
  const state = ctx.session.serviceDialog;
  if (!state) {
    return false;
  }
  const text = extractMessageText(ctx);
  if (!text) {
    return false;
  }
  appendTurn(state.dialog, 'user', text);
  state.turnCount += 1;

  try {
    const aiStep = await nextServiceConsultationStep(state.category, state.dialog);
    const stillNeedDetails =
      aiStep.needMore && state.turnCount < MAX_CLARIFY_TURNS && !state.completed;
    if (!stillNeedDetails) {
      state.completed = true;
    }
    const enrichedMessage = buildSellingMessage(
      aiStep.botMessage || SERVICE_PLAYBOOK[state.category].defaultFollowUp,
      state.category,
      stillNeedDetails
    );
    appendTurn(state.dialog, 'assistant', enrichedMessage);
    await sendChunkedReplies(
      ctx,
      enrichedMessage,
      serviceDialogKeyboard(state.category, stillNeedDetails ? 'clarify' : 'cta')
    );
    return true;
  } catch (error) {
    logger.error('service_dialog_step_failed', {
      error: error instanceof Error ? { message: error.message, stack: error.stack } : error
    });
    const fallback =
      SERVICE_PLAYBOOK[state.category].defaultFollowUp ??
      'Давайте передам кейс эксперту, чтобы он быстро подсказал, как двигаться дальше.';
    appendTurn(state.dialog, 'assistant', fallback);
    await sendChunkedReplies(ctx, fallback, serviceDialogKeyboard(state.category, 'clarify'));
    return true;
  }
};

export const isServiceDialogCategory = (value: string): value is ServiceCategory =>
  isServiceCategory(value);

const appendTurn = (
  dialog: SolutionDialogTurn[],
  role: SolutionDialogTurn['role'],
  text: string
): void => {
  dialog.push({ role, text, ts: new Date().toISOString() });
};

const extractMessageText = (ctx: CustomContext): string | undefined => {
  const message = ctx.message;
  if (message && 'text' in message) {
    const payload = message as { text?: string };
    return payload.text?.trim();
  }
  return undefined;
};

const sendChunkedReplies = async (
  ctx: CustomContext,
  text: string,
  keyboard: ReturnType<typeof serviceDialogKeyboard>
): Promise<void> => {
  const chunks = splitToTelegramChunks(text);
  for (let i = 0; i < chunks.length; i += 1) {
    const chunkKeyboard = i === chunks.length - 1 ? keyboard : undefined;
    await ctx.reply(chunks[i], chunkKeyboard);
  }
};

const buildSellingMessage = (
  raw: string,
  category: ServiceCategory,
  needClarify: boolean
): string => {
  const normalized = raw
    .replace(/\.\.\./g, '.')
    .replace(/\s+/g, ' ')
    .trim();
  if (!normalized) {
    return SERVICE_PLAYBOOK[category].defaultFollowUp;
  }
  const sentences = splitIntoSentences(normalized);
  const limit = needClarify ? 3 : 4;
  const selected = sentences.slice(0, limit);
  const body = selected.join(' ').trim();
  const closer = needClarify
    ? 'Чтобы подобрать точнее, напишите дополнительную информацию — и я сразу подключу эксперта СРВТ.'
    : SERVICE_PLAYBOOK[category].closingHook;
  return [body, closer].filter(Boolean).join('\n\n');
};

const splitIntoSentences = (text: string): string[] => {
  const matches = text.match(/[^.!?…]+[.!?…]?/g);
  if (!matches) {
    return [text];
  }
  return matches.map((sentence) => sentence.trim()).filter(Boolean);
};


