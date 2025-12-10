import { CustomContext } from '../../types/context';
import { resetFlow, ServiceDialogState, SolutionDialogTurn } from '../../types/session';
import { ServiceCategory } from '../../types/service';
import { SERVICE_PLAYBOOK, isServiceCategory } from '../../config/servicePlaybook';
import { serviceDialogKeyboard } from '../keyboards/services';
import { splitToTelegramChunks } from '../../utils/text';
import { messages } from '../messages';
import {
  nextServiceConsultationStep,
  buildAiContextFromSupabase
} from '../../services/aiAssistant';

export const startServiceDialog = async (
  ctx: CustomContext,
  category: ServiceCategory
): Promise<void> => {
  const playbook = SERVICE_PLAYBOOK[category];
  if (!playbook) {
    return;
  }
  resetFlow(ctx.session, 'service_consultation');
  const introText = [playbook.offer, playbook.description, messages.serviceScenarioInitialPrompt]
    .filter(Boolean)
    .join('\n\n');

  const state: ServiceDialogState = {
    category,
    dialog: [],
    turnCount: 0,
    stage: 'awaiting_initial',
    offer: playbook.offer,
    description: playbook.description,
    clarifyQuestion: playbook.clarifyQuestion,
    managerLabel: playbook.managerLabel
  };
  ctx.session.serviceDialog = state;
  appendTurn(state.dialog, 'assistant', introText);
  await sendChunkedReplies(ctx, introText, serviceDialogKeyboard(category));
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
  const playbook = SERVICE_PLAYBOOK[state.category];
  if (!playbook) {
    return false;
  }

  appendTurn(state.dialog, 'user', text);
  state.turnCount += 1;

  if (state.stage === 'awaiting_initial') {
    state.firstInput = text;
  }

  // AI mini-консультация
  const supaCtx = await buildAiContextFromSupabase(text);
  const aiStep = await nextServiceConsultationStep(
    state.category,
    state.dialog,
    supaCtx.externalContext ?? null
  );
  appendTurn(state.dialog, 'assistant', aiStep.botMessage);

  // Если данных достаточно — усиливаем CTA
  const replyText = aiStep.needMore
    ? aiStep.botMessage
    : [aiStep.botMessage, messages.serviceScenarioReady].filter(Boolean).join('\n\n');

  state.stage = aiStep.needMore ? 'awaiting_ai' : 'ready';
  state.clarification = text;

  await sendChunkedReplies(ctx, replyText, serviceDialogKeyboard(state.category));
  return true;
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
  for (const [index, chunk] of chunks.entries()) {
    const chunkKeyboard = index === chunks.length - 1 ? keyboard : undefined;
    await ctx.reply(chunk, chunkKeyboard);
  }
};
