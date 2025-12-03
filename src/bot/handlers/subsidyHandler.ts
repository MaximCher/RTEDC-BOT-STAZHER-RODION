import { Telegraf } from 'telegraf';
import { CustomContext } from '../../types/context';
import { messages } from '../messages';
import { subsidyKeyboard, subsidyResultKeyboard } from '../keyboards/subsidy';
import { calculateSubsidies, didSubsidyLoadFail } from '../../services/subsidyCalculator';
import { SubsidyInput } from '../../types/subsidy';
import { withCallbackGuard } from '../../utils/callbackGuard';

export const registerSubsidyHandlers = (bot: Telegraf<CustomContext>) => {
  bot.action(
    'srvt:subsidy:start:init',
    withCallbackGuard(async (ctx) => {
      ctx.session.flow = 'subsidy';
      ctx.session.subsidy = { step: 'entity', draft: {} };
      await ctx.reply(messages.subsidyIntro);
      await askEntity(ctx);
    })
  );

  bot.action(
    /^srvt:subsidy:entity:(?<value>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      if (!ctx.session.subsidy) {
        return;
      }
      const code = ctx.match?.groups?.value ?? '';
      const entityType = entityCodeToLabel(code);
      ctx.session.subsidy.draft.entityType = entityType;
      ctx.session.subsidy.step = 'export';
      await askExport(ctx);
    })
  );

  bot.action(
    /^srvt:subsidy:export:(?<value>.+)/,
    withCallbackGuard(async (ctx) => {
      const value = ctx.match?.groups?.value;
      if (!ctx.session.subsidy || !value) {
        return;
      }
      ctx.session.subsidy.draft.hasExport = value === 'yes';
      ctx.session.subsidy.step = 'cost';
      await askCost(ctx);
    })
  );

  bot.action(
    /^srvt:subsidy:cost:(?<value>.+)/,
    withCallbackGuard(async (ctx) => {
      const value = ctx.match?.groups?.value;
      if (!ctx.session.subsidy || !value) {
        return;
      }
      ctx.session.subsidy.draft.costType = value as SubsidyInput['costType'];
      ctx.session.subsidy.step = 'amount';
      await askAmount(ctx);
    })
  );

  bot.action(
    /^srvt:subsidy:amount:(?<value>.+)/,
    withCallbackGuard(async (ctx) => {
      const range = ctx.match?.groups?.value;
      if (!ctx.session.subsidy || !range) {
        return;
      }
      const { midpoint, label } = parseSpendRange(range);
      ctx.session.subsidy.draft.spend = midpoint;
      ctx.session.subsidy.draft.spendRangeLabel = label;
      ctx.session.subsidy.step = 'region';
      await askRegion(ctx);
    })
  );

  bot.action(
    /^srvt:subsidy:region:(?<value>[a-z_]+)/,
    withCallbackGuard(async (ctx) => {
      const code = ctx.match?.groups?.value ?? '';
      const region = regionCodeToLabel(code);
      if (!ctx.session.subsidy || !region) {
        return;
      }
      ctx.session.subsidy.draft.region = region;
      ctx.session.subsidy.step = 'result';
      await showSubsidyResult(ctx);
    })
  );
};

const askEntity = async (ctx: CustomContext) => {
  await ctx.reply(
    'Форма предприятия:',
    subsidyKeyboard('entity', [
      { label: 'ИП', value: 'ip' },
      { label: 'ООО', value: 'ooo' },
      { label: 'Самозанятый', value: 'self' }
    ])
  );
};

const askExport = async (ctx: CustomContext) => {
  await ctx.reply(
    'Есть действующий экспорт?',
    subsidyKeyboard('export', [
      { label: 'Да', value: 'yes' },
      { label: 'Планируем', value: 'no' }
    ])
  );
};

const askCost = async (ctx: CustomContext) => {
  await ctx.reply(
    'Тип затрат:',
    subsidyKeyboard('cost', [
      { label: 'Логистика', value: 'logistics' },
      { label: 'Выставки', value: 'exhibitions' },
      { label: 'Сертификация', value: 'certification' },
      { label: 'Платежи/банки', value: 'payments' },
      { label: 'Разработка', value: 'development' },
      { label: 'Другое', value: 'other' }
    ])
  );
};

const askAmount = async (ctx: CustomContext) => {
  await ctx.reply(
    'Сумма затрат:',
    subsidyKeyboard('amount', [
      { label: 'До 1 млн ₽', value: '0-1000000' },
      { label: '1-5 млн ₽', value: '1000000-5000000' },
      { label: '5-15 млн ₽', value: '5000000-15000000' },
      { label: 'Более 15 млн ₽', value: '15000000+' }
    ])
  );
};

const askRegion = async (ctx: CustomContext) => {
  await ctx.reply(
    'Регион присутствия:',
    subsidyKeyboard('region', [
      { label: 'Москва / МО', value: 'msk' },
      { label: 'Санкт-Петербург / ЛО', value: 'spb' },
      { label: 'Дальний Восток', value: 'dfo' },
      { label: 'Другой регион', value: 'other' }
    ])
  );
};

const showSubsidyResult = async (ctx: CustomContext) => {
  const draft = ctx.session.subsidy?.draft;
  if (!draft?.entityType || !draft.costType || typeof draft.spend !== 'number' || !draft.region) {
    await ctx.reply('Не хватает данных для расчета. Начнем заново.');
    ctx.session.subsidy = undefined;
    ctx.session.flow = 'idle';
    return;
  }

  const input: SubsidyInput = {
    entityType: draft.entityType as SubsidyInput['entityType'],
    costType: draft.costType,
    hasExport: draft.hasExport ?? false,
    spend: draft.spend,
    region: draft.region
  };

  const results = await calculateSubsidies(input);

  if (!results.length) {
    ctx.session.lastSubsidyRecommendation = {
      input,
      results: [],
      spendRangeLabel: draft.spendRangeLabel
    };
    const fallbackMessage = didSubsidyLoadFail()
      ? messages.technicalIssue
      : messages.subsidyNoMatch;
    await ctx.reply(fallbackMessage, subsidyResultKeyboard());
    ctx.session.flow = 'idle';
    ctx.session.subsidy = undefined;
    return;
  }

  const summaryLines = results
    .map(
      (result) =>
        `• ${result.title}\n  ${result.description}\n  ${result.notes}\n  До ${result.estimatedAmount.toLocaleString(
          'ru-RU'
        )} ₽`
    )
    .join('\n\n');

  const spendSummary = formatSpendLabel(input, draft.spendRangeLabel);
  const summaryText = `Субсидия на ${input.costType}: затраты ${spendSummary}, регион ${displayRegionLabel(
    input.region
  )}`;

  const maxAmount = Math.max(...results.map((r) => r.estimatedAmount));
  await ctx.reply(messages.subsidyResult(maxAmount));
  await ctx.reply(summaryLines);
  await ctx.reply(messages.subsidySummaryLead(maxAmount), subsidyResultKeyboard());

  ctx.session.flow = 'idle';
  ctx.session.subsidy = undefined;
  ctx.session.lastSubsidyRecommendation = {
    input,
    results,
    spendRangeLabel: draft.spendRangeLabel,
    summary: summaryText
  };
};

const parseSpendRange = (range: string): { midpoint: number; label: string } => {
  if (range.endsWith('+')) {
    const value = Number(range.replace('+', ''));
    return { midpoint: value, label: `>${(value / 1_000_000).toFixed(0)} млн ₽` };
  }

  const [minStr, maxStr] = range.split('-');
  const min = Number(minStr);
  const max = Number(maxStr);
  return {
    midpoint: Math.round((min + max) / 2),
    label: `${(min / 1_000_000).toFixed(1)}-${(max / 1_000_000).toFixed(1)} млн ₽`
  };
};

const entityCodeToLabel = (code: string): SubsidyInput['entityType'] => {
  switch (code) {
    case 'ip':
      return 'ИП';
    case 'ooo':
      return 'ООО';
    case 'self':
      return 'Самозанятый';
    default:
      return 'ИП';
  }
};

const regionCodeToLabel = (code: string): string => {
  switch (code) {
    case 'msk':
      return 'Москва';
    case 'spb':
      return 'Санкт-Петербург';
    case 'dfo':
      return 'Дальний Восток';
    case 'other':
      return 'all';
    default:
      return 'all';
  }
};

const formatSpendLabel = (
  input: SubsidyInput,
  rangeLabel?: string
): string => {
  if (typeof input.spend === 'number') {
    return `${(input.spend / 1_000_000).toFixed(1)} млн ₽`;
  }
  return rangeLabel ?? 'не указано';
};

const displayRegionLabel = (region: string): string => {
  if (region.toLowerCase() === 'all') {
    return 'Другой регион';
  }
  return region;
};

