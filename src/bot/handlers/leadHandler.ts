import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { Direction, LeadPayload, ConversationMetadata } from '../../types/lead';
import { messages, formatLeadForManager } from '../messages';
import { backToMenuKeyboard, leadConfirmKeyboard } from '../keyboards/lead';
import { processLead } from '../../services/leadProcessor';
import { logger } from '../../utils/logger';
import { runtimeConfig } from '../../config/runtimeConfig';
import {
  initialSessionState,
  resetFlow,
  SolutionState,
  SubsidySolutionState,
  SolutionDialogTurn
} from '../../types/session';
import { calculateLeadScoreDetails } from '../../services/leadScoring';
import { withCallbackGuard } from '../../utils/callbackGuard';
import { isValidContact } from '../../services/validation';
import { serviceCategoryToDirection } from '../../config/servicePlaybook';

interface LeadFormOptions {
  scenario: string;
  direction: Direction;
  metadata?: unknown;
  introMessage?: string;
}

export const registerLeadHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    /^srvt:lead:start:(?<slug>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const slug = ctx.match?.groups?.slug ?? '';
      await submitLeadImmediate(ctx, slug);
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

  if (slug.startsWith('service_')) {
    const serviceState = ctx.session.serviceDialog;
    return {
      scenario: slug,
      direction: serviceState?.category ? serviceCategoryToDirection(serviceState.category) : 'other',
      metadata: {
        serviceCategory: serviceState?.category,
        serviceDialog: serviceState?.dialog?.slice(-10),
        serviceTurnCount: serviceState?.turnCount,
        serviceType: serviceState?.managerLabel,
        serviceOffer: serviceState?.offer,
        serviceDescription: serviceState?.description,
        serviceClarifyQuestion: serviceState?.clarifyQuestion,
        serviceFirstInput: serviceState?.firstInput,
        serviceClarification: serviceState?.clarification
      }
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

export const submitLeadImmediate = async (ctx: CustomContext, slug: string): Promise<void> => {
  const tgId = ctx.from?.id;
  if (!tgId) {
    await ctx.reply(messages.technicalIssue);
    return;
  }
  const options = resolveLeadOptions(ctx, slug);
  if (!options) {
    await ctx.reply(messages.leadDataMissing);
    return;
  }
  const { leadPayload, comments, title } = buildLeadPayload(ctx, options);

  const result = await processLead(leadPayload, {
    comments,
    title,
    telegramUsername: ctx.from?.username,
    lastName: ctx.from?.last_name
  });

  if (!result.success) {
    await ctx.reply(messages.technicalIssue, backToMenuKeyboard());
    return;
  }

  ctx.session.lastLeadId = result.leadId;
  await ctx.reply(
    'Спасибо за обращение! Мы передали вашу заявку специалистам СРВТ. Они свяжутся с вами в ближайшее время.',
    backToMenuKeyboard()
  );
  ctx.setSession(initialSessionState());
};

const buildLeadPayload = (
  ctx: CustomContext,
  options: LeadFormOptions
): {
  leadPayload: LeadPayload & { telegramUsername?: string };
  comments: string;
  title: string;
} => {
  const tgId = ctx.from?.id ?? 0;
  const tgUsername = ctx.from?.username ?? '';
  const tgFirstName = ctx.from?.first_name ?? '';
  const tgLastName = ctx.from?.last_name ?? '';

  const solutionState = ctx.session.solution;
  const subsidyState = ctx.session.subsidy;
  const normalizedMetadata = normalizeMetadata(options.metadata);
  const solutionMetadata = buildSolutionMetadata(solutionState);
  const subsidyMetadata = buildSubsidyMetadata(subsidyState);
  const combinedMetadata = mergeMetadata(
    mergeMetadata(normalizedMetadata, solutionMetadata),
    subsidyMetadata
  );

  const caseSummary = buildCaseSummary(ctx);
  const caseType = resolveCaseType(options.scenario);

  const comments = [
    'Источник: Telegram-бот SRVT Assistant',
    `Тип обращения: ${caseType}`,
    '',
    'Резюме кейса:',
    caseSummary || '—',
    '',
    'Telegram:',
    `- ID: ${tgId}`,
    `- Username: @${tgUsername || 'нет'}`,
    `- Имя: ${tgFirstName} ${tgLastName}`.trim(),
    '',
    'История диалога:',
    formatDialogExcerpt(solutionState, subsidyState, ctx.session.serviceDialog)
  ].join('\n');

  const lead: LeadPayload & { telegramUsername?: string } = {
    source: 'srvt_bot',
    scenario: options.scenario,
    direction: options.direction,
    name: tgFirstName || 'Telegram',
    phone: '',
    company: undefined,
    userId: tgId,
    metadata: combinedMetadata,
    telegramUsername: tgUsername
  };

  const title = `[SRVT Bot] ${caseType} — Telegram #${tgId}`;

  return { leadPayload: lead, comments, title };
};

const resolveCaseType = (scenario: string): string => {
  if (scenario === 'subsidy_application' || scenario === 'subsidy_ai') {
    return 'Субсидии и меры поддержки';
  }
  if (scenario.startsWith('service_')) {
    return 'Услуги СРВТ';
  }
  if (scenario === 'solution_case' || scenario === 'solution') {
    return 'Подбор решения';
  }
  if (scenario === 'manager_contact') {
    return 'Связаться с экспертом';
  }
  return 'Обращение';
};

const buildCaseSummary = (ctx: CustomContext): string => {
  if (ctx.session.lastCase?.summary) {
    return ctx.session.lastCase.summary;
  }
  if (ctx.session.solution?.managerSummary) {
    return ctx.session.solution.managerSummary;
  }
  if (ctx.session.subsidy?.classification) {
    const cls = ctx.session.subsidy.classification;
    const budget =
      (cls.budgetFrom && cls.budgetTo && cls.budgetFrom === cls.budgetTo
        ? cls.budgetFrom
        : cls.budgetTo ?? cls.budgetFrom) ?? null;
    const budgetText = budget ? `${budget.toLocaleString('ru-RU')} ₽` : 'не указан';
    const sectorText = cls.sectors?.length ? cls.sectors.join(', ') : '—';
    return `Запрос на субсидии: сектор ${sectorText}, регион ${cls.region}, бюджет ${budgetText}`;
  }
  if (ctx.session.serviceDialog) {
    const svc = ctx.session.serviceDialog;
    return `Услуги СРВТ: ${svc.managerLabel}. Запрос: ${svc.firstInput ?? svc.clarification ?? 'не указан'}`;
  }
  return 'Описание не указано';
};

const formatDialogExcerpt = (
  solution?: SolutionState,
  subsidy?: SubsidySolutionState,
  service?: { dialog?: SolutionDialogTurn[] }
): string => {
  if (solution?.dialog?.length) {
    return solution.dialog.slice(-5).map((d) => `${d.role}: ${d.text}`).join('\n');
  }
  if (subsidy?.dialog?.length) {
    return subsidy.dialog.slice(-5).map((d) => `${d.role}: ${d.text}`).join('\n');
  }
  if (service?.dialog?.length) {
    return service.dialog.slice(-5).map((d) => `${d.role}: ${d.text}`).join('\n');
  }
  return '—';
};

