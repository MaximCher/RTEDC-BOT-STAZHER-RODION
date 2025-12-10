import { LeadPayload, Direction } from './lead';
import { SubsidyClassification, EstimatedProgram } from './subsidy';
import { ServiceCategory } from './service';

export type FlowName =
  | 'idle'
  | 'solution'
  | 'lead_form'
  | 'subsidy_solution'
  | 'manager_contact'
  | 'service_consultation';

export type SolutionDialogTurnRole = 'user' | 'assistant';

export interface SolutionDialogTurn {
  role: SolutionDialogTurnRole;
  text: string;
  ts?: string;
}

export interface SolutionState {
  dialog: SolutionDialogTurn[];
  direction?: Direction;
  managerSummary?: string;
  aiReady?: boolean;
  turnCount: number;
}

export type LeadFormStep = 'name' | 'phone' | 'company' | 'confirm';

export interface LeadFormState {
  scenario: string;
  direction: Direction;
  step: LeadFormStep;
  lead: Partial<LeadPayload> & Pick<LeadPayload, 'source' | 'scenario' | 'direction' | 'userId'>;
  metadata?: Record<string, unknown>;
  introMessage?: string;
  contactAsked?: boolean;
}

export interface SubsidySolutionState {
  dialog: SolutionDialogTurn[];
  classification?: SubsidyClassification;
  aiReady?: boolean;
  clarifyCount?: number;
  needMore?: boolean;
  turnCount: number;
  programs?: EstimatedProgram[];
  hasAmountEstimate?: boolean;
  history: SubsidyStepSnapshot[];
}

export interface SubsidyStepSnapshot {
  classification: SubsidyClassification;
  dialogLength: number;
  clarifyCount: number;
}

export interface ServiceDialogState {
  category: ServiceCategory;
  dialog: SolutionDialogTurn[];
  turnCount: number;
  stage: 'awaiting_initial' | 'awaiting_clarification' | 'awaiting_ai' | 'ready';
  offer: string;
  description: string;
  clarifyQuestion: string;
  managerLabel: string;
  firstInput?: string;
  clarification?: string;
}

export interface CaseInsight {
  text: string;
  direction: Direction;
  summary: string;
  advice: string;
  sources?: string[];
  kbUsed?: boolean;
  riskLevel?: string;
  potentialValue?: string;
}

export interface SessionData {
  flow: FlowName;
  leadForm?: LeadFormState;
  solution?: SolutionState;
  subsidy?: SubsidySolutionState;
  serviceDialog?: ServiceDialogState;
  lastCase?: CaseInsight;
  lastLeadId?: number;
}

export const initialSessionState = (): SessionData => ({
  flow: 'idle'
});

export const resetFlow = (session: SessionData, nextFlow: FlowName = 'idle'): void => {
  session.leadForm = undefined;
  session.solution = undefined;
  session.subsidy = undefined;
  session.serviceDialog = undefined;
  session.flow = nextFlow;
};
