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
  lead: LeadPayload & { score?: number },
  options?: SendLeadOptions
): Promise<BitrixLeadResult> {
  const baseUrl = runtimeConfig.bitrixWebhookUrl?.trim();
  if (!baseUrl) {
    return { success: false, error: 'bitrix_disabled' };
  }

  const endpoint = ensureEndpoint(baseUrl);
  const scenarioLabel = getScenarioLabel(lead.scenario);
  const directionLabel = getDirectionLabel(lead.direction);

  const fields: Record<string, unknown> = {
    TITLE: `SRVT Assistant — ${scenarioLabel} / ${directionLabel}`,
    NAME: lead.name ?? '',
    PHONE: lead.phone ? [{ VALUE: lead.phone, VALUE_TYPE: 'WORK' }] : [],
    COMMENTS: buildComments(lead, options)
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

