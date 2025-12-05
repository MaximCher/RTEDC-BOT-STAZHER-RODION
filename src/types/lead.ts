import type { SolutionDialogTurn } from './session';
import type { SubsidyClassification, EstimatedProgram } from './subsidy';

export type Direction = 'finance' | 'logistics' | 'payments' | 'analytics' | 'other';

export interface SolutionMetadata {
  solutionDialog?: SolutionDialogTurn[];
  solutionManagerSummary?: string;
}

export interface SubsidyMetadata {
  subsidyDialog?: SolutionDialogTurn[];
  subsidyClassification?: SubsidyClassification;
  subsidyPrograms?: EstimatedProgram[];
}

export type ConversationMetadata = SolutionMetadata & SubsidyMetadata;

export interface LeadPayload {
  source: 'srvt_bot';
  scenario: string;
  direction: Direction;
  name: string;
  phone: string;
  company?: string;
  userId: number;
  score?: number;
  metadata?: (Record<string, unknown> & ConversationMetadata) | undefined;
}
