import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction, LeadPayload, ConversationMetadata } from '../../types/lead';
import { messages, formatLeadForManager } from '../messages';
import { backToMenuKeyboard, leadConfirmKeyboard } from '../keyboards/lead';
import { processLead } from '../../services/leadProcessor';
import { runtimeConfig } from '../../config/runtimeConfig';
import { logger } from '../../utils/logger';
import {
  initialSessionState,
  resetFlow,
  SolutionState,
  SubsidySolutionState
} from '../../types/session';
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
        metadata: current.metadata,
        introMessage: current.introMessage
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

  const solutionState = ctx.session.solution;
  const subsidyState = ctx.session.subsidy;
  const normalizedMetadata = normalizeMetadata(metadata);
  const solutionMetadata = buildSolutionMetadata(solutionState);
  const subsidyMetadata = buildSubsidyMetadata(subsidyState);
  const combinedMetadata = mergeMetadata(
    mergeMetadata(normalizedMetadata, solutionMetadata),
    subsidyMetadata
  );
  resetFlow(ctx.session, 'lead_form');

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
    metadata: combinedMetadata,
    introMessage: introMessage ?? selectLeadIntro(scenario, combinedMetadata),
    contactAsked: false
  };

  const leadState = ctx.session.leadForm;

  if (leadState.introMessage) {
    await ctx.replyWithMarkdown(leadState.introMessage);
  }

  if (scenario === 'manager_contact') {
    leadState.step = 'phone';
    if (!leadState.lead.name) {
      const fallbackName = ctx.from?.first_name || ctx.from?.last_name;
      if (fallbackName) {
        leadState.lead.name = fallbackName;
      }
    }
    await askForContact(ctx);
    return;
  }

  const defaultName = ctx.from?.first_name || ctx.from?.last_name;
  if (defaultName) {
    ctx.session.leadForm.lead.name = defaultName;
    ctx.session.leadForm.step = 'phone';
    await ctx.replyWithMarkdown(messages.leadFormNamePrefilled(defaultName));
    await askForContact(ctx);
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
      await askForContact(ctx);
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
      direction: 'other'
    };
  }

  if (slug === 'club') {
    return {
      scenario: 'club_application',
      direction: 'other',
      metadata: {
        service: 'club_application',
        source: 'main_menu',
        description: 'Вступление в клуб экспортёров и импортёров СРВТ.РФ'
      },
      introMessage: messages.clubApplicationIntro
    };
  }

  if (slug === 'academy') {
    return {
      scenario: 'academy_application',
      direction: 'other',
      metadata: {
        service: 'academy_application',
        source: 'main_menu',
        description: 'Запись в Академию СРВТ.РФ',
        landingUrl: 'https://www.xn--b1a1acg.xn--p1ai/academy'
      },
      introMessage: messages.academyApplicationIntro
    };
  }

  if (slug === 'subsidy_application' || slug === 'subsidy_ai') {
    const subsidyState = ctx.session.subsidy;
    if (!subsidyState) {
      return null;
    }
    return {
      scenario: 'subsidy_application',
      direction: 'finance'
    };
  }

  if (slug === 'solution') {
    const solution = ctx.session.solution;
    return {
      scenario: 'solution_case',
      direction: solution?.direction ?? 'other'
    };
  }

  if (slug === 'solution_case') {
    const insight = ctx.session.lastCase;
    if (!insight) {
      return null;
    }
    return {
      scenario: 'solution_case',
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

const mergeMetadata = (
  base?: Record<string, unknown>,
  extra?: Record<string, unknown>
): Record<string, unknown> | undefined => {
  if (!base && !extra) {
    return undefined;
  }
  return {
    ...(base ?? {}),
    ...(extra ?? {})
  };
};

const buildSolutionMetadata = (
  solution?: SolutionState
): Record<string, unknown> | undefined => {
  if (!solution) {
    return undefined;
  }

  const metadata: ConversationMetadata & Record<string, unknown> = {};
  if (solution.dialog?.length) {
    metadata.solutionDialog = solution.dialog;
  }
  if (solution.managerSummary) {
    metadata.solutionManagerSummary = solution.managerSummary;
  }

  return Object.keys(metadata).length ? metadata : undefined;
};

const buildSubsidyMetadata = (
  subsidy?: SubsidySolutionState
): Record<string, unknown> | undefined => {
  if (!subsidy) {
    return undefined;
  }

  const dialogExcerpt =
    subsidy.dialog?.length && subsidy.dialog.length > 15
      ? subsidy.dialog.slice(-15)
      : subsidy.dialog;

  const payload: Record<string, unknown> = {
    subsidy: {
      classification: subsidy.classification,
      dialog: dialogExcerpt,
      programs: subsidy.programs,
      hasAmountEstimate: subsidy.hasAmountEstimate ?? false
    }
  };

  if (subsidy.classification) {
    payload.subsidyClassification = subsidy.classification;
    payload.budgetFrom = subsidy.classification.budgetFrom;
    payload.budgetTo = subsidy.classification.budgetTo;
    payload.region = subsidy.classification.region;
    payload.costTypes = subsidy.classification.costTypes;
    payload.sectors = subsidy.classification.sectors;
    payload.export = subsidy.classification.export;
  }

  if (subsidy.programs?.length) {
    payload.subsidyPrograms = subsidy.programs;
  }

  if (typeof subsidy.hasAmountEstimate === 'boolean') {
    payload.hasAmountEstimate = subsidy.hasAmountEstimate;
  }

  if (dialogExcerpt?.length) {
    payload.subsidyDialog = dialogExcerpt;
  }

  return payload;
};

const askForContact = async (ctx: CustomContext): Promise<void> => {
  const leadState = ctx.session.leadForm;
  if (!leadState || leadState.contactAsked) {
    return;
  }

  leadState.contactAsked = true;
  await ctx.reply(messages.leadFormContact);
};

const selectLeadIntro = (
  scenario: string,
  metadata?: Record<string, unknown>
): string | undefined => {
  const score = extractScoreFromMetadata(metadata);
  if (typeof score === 'number') {
    if (score >= 4) {
      return messages.leadFormIntroHot;
    }
    if (score >= 2) {
      return messages.leadFormIntroWarm;
    }
    return messages.leadFormIntroCold;
  }

  if (scenario === 'manager_contact') {
    return messages.managerContact;
  }
  if (scenario === 'club_application') {
    return messages.clubApplicationIntro;
  }
  if (scenario === 'academy_application') {
    return messages.academyApplicationIntro;
  }
  if (scenario === 'solution_case') {
    return messages.leadFormIntroWarm;
  }
  if (scenario === 'subsidy_application' || scenario === 'subsidy_ai') {
    return messages.leadFormIntroHot;
  }
  if (scenario.startsWith('service_')) {
    return messages.leadFormIntroWarm;
  }

  return undefined;
};

const extractScoreFromMetadata = (
  metadata?: Record<string, unknown>
): number | undefined => {
  if (!metadata) {
    return undefined;
  }
  const scoring = (metadata as Record<string, unknown>)['scoring'];
  if (scoring && typeof scoring === 'object' && !Array.isArray(scoring)) {
    const extendedScore = (scoring as Record<string, unknown>)['extendedScore'];
    if (typeof extendedScore === 'number') {
      return extendedScore;
    }
  }
  return undefined;
};

