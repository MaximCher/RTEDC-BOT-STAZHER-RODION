import { Direction } from '../../types/lead';

export interface QuizQuestionOption {
  label: string;
  value: string;
}

export interface QuizQuestion {
  key: string;
  text: string;
  options: QuizQuestionOption[];
}

interface DirectionFlow {
  primary: QuizQuestion;
  followUp?: QuizQuestion;
}

const directionFlows: Record<Direction, DirectionFlow> = {
  finance: {
    primary: {
      key: 'finance_need',
      text: 'Что нужно профинансировать?',
      options: [
        { label: 'Оборот / контракты', value: 'working-capital' },
        { label: 'Расширение / экспорт', value: 'expansion' },
        { label: 'Гранты / субсидии', value: 'grants' }
      ]
    },
    followUp: {
      key: 'finance_amount',
      text: 'Какой ориентировочный объём или оборот?',
      options: [
        { label: 'До 50 млн ₽', value: 'size_small' },
        { label: '50-200 млн ₽', value: 'size_mid' },
        { label: '200+ млн ₽', value: 'size_large' }
      ]
    }
  },
  logistics: {
    primary: {
      key: 'logistics_issue',
      text: 'В чём основная сложность логистики?',
      options: [
        { label: 'Маршруты и тарифы', value: 'routes' },
        { label: 'Таможня и страхование', value: 'customs' },
        { label: 'Склад / фулфилмент', value: 'warehouse' }
      ]
    },
    followUp: {
      key: 'logistics_region',
      text: 'Куда планируете поставки?',
      options: [
        { label: 'Европа', value: 'region_eu' },
        { label: 'Азия / Китай', value: 'region_asia' },
        { label: 'Ближний Восток / ОАЭ', value: 'region_me' }
      ]
    }
  },
  payments: {
    primary: {
      key: 'payments_issue',
      text: 'Какие платежи сложнее всего провести?',
      options: [
        { label: 'USD / EUR', value: 'hard-currency' },
        { label: 'Дружественные валюты', value: 'friendly' },
        { label: 'Блокировки банков', value: 'blocks' }
      ]
    },
    followUp: {
      key: 'payments_bank',
      text: 'Где держите расчётные счета?',
      options: [
        { label: 'Российские банки', value: 'bank_ru' },
        { label: 'Иностранные банки', value: 'bank_foreign' },
        { label: 'Финтех-провайдеры', value: 'bank_fintech' }
      ]
    }
  },
  analytics: {
    primary: {
      key: 'analytics_goal',
      text: 'Что нужно проверить или исследовать?',
      options: [
        { label: 'Партнёра / контрагента', value: 'partner' },
        { label: 'Рынок / страну', value: 'market' },
        { label: 'Возможности выхода', value: 'go-to-market' }
      ]
    },
    followUp: {
      key: 'analytics_type',
      text: 'Какой тип контрагента или рынка?',
      options: [
        { label: 'Крупная компания', value: 'type_enterprise' },
        { label: 'SMB / стартап', value: 'type_smb' },
        { label: 'Новый рынок / страна', value: 'type_country' }
      ]
    }
  },
  other: {
    primary: {
      key: 'other_goal',
      text: 'Что планируете делать?',
      options: [
        { label: 'Выход на новый рынок', value: 'new-market' },
        { label: 'Поиск партнёров', value: 'partners' },
        { label: 'Другое', value: 'custom' }
      ]
    },
    followUp: {
      key: 'export_target',
      text: 'Какой целевой регион для выхода?',
      options: [
        { label: 'ЕС / Великобритания', value: 'target_eu' },
        { label: 'Азия / Китай', value: 'target_asia' },
        { label: 'Ближний Восток / Африка', value: 'target_mea' }
      ]
    }
  }
};

export const getPrimaryQuestion = (direction: Direction): QuizQuestion =>
  directionFlows[direction].primary;

export const getFollowUpQuestion = (direction: Direction): QuizQuestion | undefined =>
  directionFlows[direction].followUp;

export const buildQuizSummary = (direction: Direction, answerValue: string): string => {
  switch (direction) {
    case 'finance':
      if (answerValue === 'working-capital') {
        return 'Нужно усиливать оборот: настроим финансирование контрактов и закупок, чтобы не тормозить рост.';
      }
      if (answerValue === 'expansion') {
        return 'Готовность к расширению есть — подключим субсидии и инвесторов под экспорт.';
      }
      return 'Можно комбинировать гранты и льготные программы, чтобы ускорить запуск.';
    case 'logistics':
      if (answerValue === 'routes') {
        return 'Важен пересмотр маршрутов и ставок — оптимизируем цепочку поставок.';
      }
      if (answerValue === 'customs') {
        return 'Есть узкие места на таможне и страховании — подключим экспертов для закрытия рисков.';
      }
      return 'Склад и фулфилмент можно усилить за счёт сетевых партнёров СРВТ.';
    case 'payments':
      if (answerValue === 'hard-currency') {
        return 'Платежи в USD/EUR блокируются — поможем с банками и альтернативными каналами.';
      }
      if (answerValue === 'friendly') {
        return 'Нужны устойчивые каналы в дружественных валютах — подскажем, как распределить потоки.';
      }
      return 'Комплаенс можно закрыть через проверенных провайдеров и сопровождение юристов.';
    case 'analytics':
      if (answerValue === 'partner') {
        return 'Важно проверить контрагентов и собрать фактуру перед сделкой.';
      }
      if (answerValue === 'market') {
        return 'Требуется экспресс-аналитика рынка и конкурентная разведка.';
      }
      return 'Готовность к выходу на новый рынок — соберём практичный план и подберём партнёров.';
    case 'other':
    default:
      if (answerValue === 'new-market') {
        return 'Проект на пороге нового рынка — поможем упаковать предложение и найти вход.';
      }
      if (answerValue === 'partners') {
        return 'Расширение партнёрской сети критично — подключим проверенные контакты СРВТ.';
      }
      return 'Запрос нестандартный, но решаемый — сформируем команду под ваш кейс.';
  }
};



