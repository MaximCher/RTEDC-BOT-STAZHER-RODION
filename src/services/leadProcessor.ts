import { Prisma } from '@prisma/client';
import { LeadPayload } from '../types/lead';
import { logger } from '../utils/logger';
import { prisma } from './db';

export const processLead = async (lead: LeadPayload): Promise<void> => {
  logger.info('Processing lead payload', { lead });

  try {
    await prisma.lead.create({
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
};
