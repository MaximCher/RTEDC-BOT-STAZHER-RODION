import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction, LeadPayload } from '../../types/lead';
import { messages, formatLeadForManager } from '../messages';
import { backToMenuKeyboard, leadConfirmKeyboard } from '../keyboards/lead';
import { processLead } from '../../services/leadProcessor';
import { runtimeConfig } from '../../config/runtimeConfig';
import { logger } from '../../utils/logger';
import { CaseInsight, initialSessionState } from '../../types/session';
import { isValidContact } from '../../services/validation';
import { calculateLeadScoreDetails } from '../../services/leadScoring';
import { withCallbackGuard } from '../../utils/callbackGuard';

interface LeadFormOptions {
  scenario: string;
  direction: Direction;
  metadata?: unknown;
  introMessage?: string;
}

export const registerLeadHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:lead:restart:form',
    withCallbackGuard(async (ctx) => {
      await ctx.reply('Запускаю форму заново 👇');
    const current = ctx.session.leadForm;
    if (!current) {
      return;
    }
    await startLeadForm(ctx, {
      scenario: current.scenario,
      direction: current.direction,
      metadata: current.metadata
    });
    })
  );

  bot.action(
    /^srvt:lead:start:(?<slug>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const slug = ctx.match?.groups?.slug ?? '';
      const options = resolveLeadOptions(ctx, slug);
      if (!options) {
        await ctx.reply(messages.leadDataMissing);
        return;
      }
      await startLeadForm(ctx, options);
    })
  );

  bot.action(
    'srvt:lead:submit:confirm',
    withCallbackGuard(async (ctx) => {
      await submitLead(ctx);
    })
  );
};

export const startLeadForm = async (
  ctx: CustomContext,
  { scenario, direction, metadata, introMessage }: LeadFormOptions
): Promise<void> => {
  const userId = ctx.from?.id;
  if (!userId) {
    await ctx.reply(messages.technicalIssue);
    return;
  }

  const normalizedMetadata = normalizeMetadata(metadata);

  ctx.session.flow = 'lead_form';
  ctx.session.leadForm = {
    scenario,
    direction,
    step: 'name',
    lead: {
      source: 'srvt_bot',
      scenario,
      direction,
      userId
    },
    metadata: normalizedMetadata
  };

  const defaultName = ctx.from?.first_name || ctx.from?.last_name;
  if (defaultName) {
    ctx.session.leadForm.lead.name = defaultName;
    ctx.session.leadForm.step = 'phone';
    await ctx.replyWithMarkdown(messages.leadFormNamePrefilled(defaultName));
    await ctx.reply(messages.leadFormContact);
    return;
  }

  await ctx.reply(messages.leadFormName);
};

export const handleLeadText = async (ctx: CustomContext): Promise<boolean> => {
  const leadState = ctx.session.leadForm;
  if (!leadState) {
    return false;
  }

  const text = extractMessageText(ctx);
  if (!text) {
    return false;
  }

  switch (leadState.step) {
    case 'name':
      leadState.lead.name = text;
      leadState.step = 'phone';
      await ctx.reply(messages.leadFormContact);
      return true;
    case 'phone':
      if (!isValidContact(text)) {
        await ctx.reply(messages.leadFormValidationError);
        return true;
      }
      leadState.lead.phone = text;
      leadState.step = 'company';
      await ctx.reply(messages.leadFormCompany);
      return true;
    case 'company':
      if (text.toLowerCase() !== 'нет') {
        leadState.lead.company = text;
      }
      leadState.step = 'confirm';
      await ctx.reply(messages.leadFormConfirm(leadState.lead as LeadPayload), leadConfirmKeyboard());
      return true;
    default:
      return false;
  }
};

const submitLead = async (ctx: CustomContext): Promise<void> => {
  const leadState = ctx.session.leadForm;
  if (!leadState || leadState.step !== 'confirm') {
    await ctx.reply('Форма заполнена не до конца. Пожалуйста, завершите все шаги.');
    return;
  }

  if (!leadState.lead.name || !leadState.lead.phone) {
    await ctx.reply('Не удалось прочитать контактные данные. Попробуйте заполнить форму снова.');
    return;
  }

  const metadata = normalizeMetadata(leadState.metadata);
  const scoring = calculateLeadScoreDetails({
    scenario: leadState.scenario,
    direction: leadState.direction,
    metadata
  });
  if (metadata) {
    metadata.scoring = scoring;
  }

  const lead: LeadPayload = {
    ...(leadState.lead as LeadPayload),
    company: leadState.lead.company,
    metadata,
    score: scoring.extendedScore
  };

  await processLead(lead);
  const adminChatId = runtimeConfig.adminChatId;
  if (adminChatId) {
    await ctx.telegram.sendMessage(adminChatId, formatLeadForManager(lead), {
      parse_mode: 'Markdown'
    });
  } else {
    logger.warn('ADMIN_CHAT_ID is not configured');
  }

  await ctx.reply(messages.leadFormSubmitted, backToMenuKeyboard());
  ctx.setSession(initialSessionState());
};

const resolveLeadOptions = (
  ctx: CustomContext,
  slug: string
): LeadFormOptions | null => {
  if (slug === 'manager') {
    return {
      scenario: 'manager_contact',
      direction: 'other',
      introMessage: messages.managerContact
    };
  }

  if (slug === 'subsidy') {
    if (!ctx.session.lastSubsidyRecommendation) {
      return null;
    }
    return {
      scenario: 'subsidy_application',
      direction: 'finance',
      metadata: ctx.session.lastSubsidyRecommendation
    };
  }

  if (slug === 'quiz') {
    if (!ctx.session.lastQuiz) {
      return null;
    }
    return {
      scenario: 'quiz_help',
      direction: ctx.session.lastQuiz.direction,
      metadata: ctx.session.lastQuiz
    };
  }

  if (slug === 'case') {
    const insight = ctx.session.lastCase;
    if (!insight) {
      return null;
    }
    return {
      scenario: 'case_review',
      direction: insight.direction,
      metadata: insight
    };
  }

  return null;
};

const extractMessageText = (ctx: CustomContext): string | undefined => {
  const message = ctx.message;
  if (message && 'text' in message) {
    const payload = message as { text?: string };
    return payload.text?.trim();
  }
  return undefined;
};

const normalizeMetadata = (
  metadata: unknown
): Record<string, unknown> | undefined => {
  if (!metadata) {
    return undefined;
  }
  if (Array.isArray(metadata)) {
    return { items: metadata };
  }
  if (typeof metadata === 'object') {
    return { ...(metadata as Record<string, unknown>) };
  }
  return { value: metadata };
};

