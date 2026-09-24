export type ColorRamp = 'water' | 'thermal' | 'turbo';

export interface SimulationTelemetry {
  timeStep: number;
  timeLabel: string;
  rainfallRateMmHr: number;
  totalRunoffM3: number;
  drainageDischargeM3s: number;
  surchargingNodesCount: number;
  maxFloodDepthM: number;
  totalFloodedAreaKm2: number;
  massBalanceErrorPercent: number;
}

export interface WardMetric {
  code: string;
  name: string;
  riskScore: number; // 0-100
  riskGrade: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  populationAtRisk: number;
  floodedRoadKm: number;
  activePumps: number;
  criticalSpots: string[];
}

export interface DrainageNodeTelemetry {
  id: string;
  name: string;
  ward: string;
  capacityM3s: number;
  inflowM3s: number;
  surchargeDepthM: number;
  isBackflowing: boolean;
  waterLevelStatus: 'NORMAL' | 'SURCHARGED' | 'REVERSE_OVERFLOW';
}

export interface CapAlertPayload {
  id: string;
  identifier: string;
  sender: string;
  sent: string;
  status: 'Draft' | 'Issued' | 'Cancelled';
  msgType: 'Alert' | 'Update';
  scope: 'Public';
  severity: 'Extreme' | 'Severe' | 'Moderate' | 'Minor';
  urgency: 'Immediate' | 'Expected';
  certainty: 'Observed' | 'Likely';
  headline: string;
  description: string;
  instruction: string;
  areaDesc: string;
  polygon: string;
}

export interface AiChatMessage {
  id: string;
  sender: 'operator' | 'ai' | 'system';
  content: string;
  toolCall?: {
    name: string;
    args: Record<string, any>;
    result: string;
  };
  timestamp: string;
}
