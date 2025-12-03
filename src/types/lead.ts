export type Direction = 'finance' | 'logistics' | 'payments' | 'analytics' | 'other';

export interface LeadPayload {
  source: 'srvt_bot';
  scenario: string;
  direction: Direction;
  name: string;
  phone: string;
  company?: string;
  userId: number;
  score?: number;
  metadata?: Record<string, unknown>;
}
