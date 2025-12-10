import { LeadPayload } from '../types/lead';
import { runtimeConfig } from '../config/runtimeConfig';
import { formatLeadForManager, getDirectionLabel, getScenarioLabel } from '../bot/messages';
import { logger } from '../utils/logger';

export interface BitrixLeadResult {
  success: boolean;
  leadId?: number;
  error?: string;
}

interface SendLeadOptions {
  dbId?: bigint | number;
}

export async function sendLeadToBitrix(
  lead: LeadPayload & { score?: number; telegramUsername?: string },
  options?: SendLeadOptions & { title?: string; comments?: string; lastName?: string }
): Promise<BitrixLeadResult> {
  const baseUrl = runtimeConfig.bitrixWebhookUrl?.trim();
  if (!baseUrl) {
    return { success: false, error: 'bitrix_disabled' };
  }

  const endpoint = ensureEndpoint(baseUrl);
  const scenarioLabel = getScenarioLabel(lead.scenario);
  const directionLabel = getDirectionLabel(lead.direction);

  const fields: Record<string, unknown> = {
    TITLE: options?.title ?? `SRVT Assistant — ${scenarioLabel} / ${directionLabel}`,
    NAME: lead.name ?? '',
    LAST_NAME: options?.lastName ?? '',
    PHONE: lead.phone ? [{ VALUE: lead.phone, VALUE_TYPE: 'WORK' }] : [],
    COMMENTS: options?.comments ?? buildComments(lead, options),
    UF_CRM_TG_ID: lead.userId ? String(lead.userId) : undefined,
    UF_CRM_TG_USERNAME: lead.telegramUsername ?? undefined
  };

  if (runtimeConfig.bitrixResponsibleId !== undefined) {
    fields.ASSIGNED_BY_ID = runtimeConfig.bitrixResponsibleId;
  }

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields })
    });

    const payload = await parseJson(response);
    if (response.ok && payload && typeof payload.result === 'number') {
      return { success: true, leadId: payload.result };
    }

    const errorMessage =
      (payload && (payload.error_description || payload.error)) ||
      `HTTP_${response.status}`;
    logger.error('bitrix_lead_failed', { error: errorMessage, lead });
    return { success: false, error: errorMessage };
  } catch (error) {
    logger.error('bitrix_lead_failed', { error, lead });
    return { success: false, error: error instanceof Error ? error.message : 'unknown_error' };
  }
}

const ensureEndpoint = (input: string): string => {
  const trimmed = input.replace(/\s+/g, '');
  if (trimmed.endsWith('crm.lead.add')) {
    return trimmed;
  }
  return `${trimmed.replace(/\/+$/, '')}/crm.lead.add`;
};

const ensureListEndpoint = (input: string): string => {
  const trimmed = input.replace(/\s+/g, '');
  if (trimmed.endsWith('crm.lead.list')) {
    return trimmed;
  }
  return `${trimmed.replace(/\/+$/, '')}/crm.lead.list`;
};

const buildComments = (lead: LeadPayload, options?: SendLeadOptions): string => {
  const plain = stripMarkdown(formatLeadForManager(lead));
  if (options?.dbId !== undefined) {
    return `${plain}\n\nID в базе: ${options.dbId.toString()}`;
  }
  return plain;
};

const stripMarkdown = (text: string): string =>
  text.replace(/[*_`]/g, '').replace(/\u200b/g, '');

const parseJson = async (
  response: { json: () => Promise<Record<string, any>> }
): Promise<Record<string, any> | undefined> => {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
};

export interface UserCase {
  id: number;
  title: string;
  status: string;
  created: string;
}

export async function getUserCasesByTelegramId(tgId: number, limit = 10): Promise<UserCase[]> {
  const baseUrl = runtimeConfig.bitrixWebhookUrl?.trim();
  if (!baseUrl) {
    return [];
  }
  const endpoint = ensureListEndpoint(baseUrl);
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filter: { UF_CRM_TG_ID: String(tgId) },
        order: { ID: 'DESC' },
        select: ['ID', 'TITLE', 'STATUS_ID', 'STATUS_NAME', 'DATE_CREATE'],
        start: 0
      })
    });

    const payload = await parseJson(response as any);
    const rows = (payload?.result ?? []) as Array<Record<string, any>>;
    return rows.slice(0, limit).map((row) => ({
      id: Number(row.ID),
      title: row.TITLE ?? 'Без названия',
      status: row.STATUS_NAME ?? row.STATUS_ID ?? 'Статус не указан',
      created: row.DATE_CREATE ?? ''
    }));
  } catch (error) {
    logger.error('bitrix_list_failed', { error, tgId });
    return [];
  }
}

