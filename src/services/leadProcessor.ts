import { Prisma } from '@prisma/client';
import { LeadPayload } from '../types/lead';
import { logger } from '../utils/logger';
import { prisma } from './db';
import { runtimeConfig } from '../config/runtimeConfig';
import { sendLeadToBitrix, BitrixLeadResult } from './bitrixClient';

interface ProcessLeadOptions {
  comments?: string;
  title?: string;
  telegramUsername?: string;
  lastName?: string;
}

export const processLead = async (
  lead: LeadPayload & { telegramUsername?: string },
  options?: ProcessLeadOptions
): Promise<BitrixLeadResult> => {
  logger.info('Processing lead payload', { lead });

  let prismaRecord: { id: number } | null = null;
  try {
    prismaRecord = await prisma.lead.create({
      data: {
        userId: BigInt(lead.userId),
        source: lead.source,
        scenario: lead.scenario,
        direction: lead.direction,
        name: lead.name,
        phone: lead.phone,
        company: lead.company ?? null,
        metadata: (lead.metadata ?? null) as Prisma.InputJsonValue
      }
    });
  } catch (error) {
    logger.error('Failed to persist lead', { error });
  }

  let bitrixResult: BitrixLeadResult = { success: false };
  if (runtimeConfig.bitrixWebhookUrl) {
    try {
      bitrixResult = await sendLeadToBitrix(
        lead,
        {
          ...(prismaRecord ? { dbId: prismaRecord.id } : {}),
          comments: options?.comments,
          title: options?.title,
          lastName: options?.lastName
        }
      );
      if (!bitrixResult.success) {
        logger.error('bitrix_lead_failed', { error: bitrixResult.error, lead });
      } else {
        logger.info('bitrix_lead_created', {
          leadId: bitrixResult.leadId,
          dbId: prismaRecord?.id,
          direction: lead.direction,
          scenario: lead.scenario
        });
      }
    } catch (error) {
      logger.error('bitrix_lead_exception', { error, lead });
    }
  }
  return bitrixResult;
};
