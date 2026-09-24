import {
  SimulationTelemetry,
  WardMetric,
  DrainageNodeTelemetry,
  CapAlertPayload,
  AiChatMessage
} from '../types/dashboard';

export const SIMULATION_FRAMES: SimulationTelemetry[] = [
  {
    timeStep: 0,
    timeLabel: 'T-15m (11:15)',
    rainfallRateMmHr: 32.0,
    totalRunoffM3: 42000,
    drainageDischargeM3s: 18.2,
    surchargingNodesCount: 2,
    maxFloodDepthM: 0.22,
    totalFloodedAreaKm2: 0.85,
    massBalanceErrorPercent: 0.04
  },
  {
    timeStep: 1,
    timeLabel: 'Now (11:30)',
    rainfallRateMmHr: 48.0,
    totalRunoffM3: 78500,
    drainageDischargeM3s: 26.4,
    surchargingNodesCount: 5,
    maxFloodDepthM: 0.52,
    totalFloodedAreaKm2: 1.94,
    massBalanceErrorPercent: 0.06
  },
  {
    timeStep: 2,
    timeLabel: '+15m (11:45)',
    rainfallRateMmHr: 62.5,
    totalRunoffM3: 124000,
    drainageDischargeM3s: 31.0,
    surchargingNodesCount: 9,
    maxFloodDepthM: 0.74,
    totalFloodedAreaKm2: 3.42,
    massBalanceErrorPercent: 0.08
  },
  {
    timeStep: 3,
    timeLabel: '+30m (12:00)',
    rainfallRateMmHr: 68.0,
    totalRunoffM3: 168000,
    drainageDischargeM3s: 32.8,
    surchargingNodesCount: 14,
    maxFloodDepthM: 0.95,
    totalFloodedAreaKm2: 4.88,
    massBalanceErrorPercent: 0.09
  },
  {
    timeStep: 4,
    timeLabel: '+45m (12:15)',
    rainfallRateMmHr: 54.0,
    totalRunoffM3: 189000,
    drainageDischargeM3s: 33.2,
    surchargingNodesCount: 12,
    maxFloodDepthM: 0.88,
    totalFloodedAreaKm2: 4.60,
    massBalanceErrorPercent: 0.07
  },
  {
    timeStep: 5,
    timeLabel: '+60m (12:30)',
    rainfallRateMmHr: 35.0,
    totalRunoffM3: 196000,
    drainageDischargeM3s: 31.5,
    surchargingNodesCount: 8,
    maxFloodDepthM: 0.70,
    totalFloodedAreaKm2: 3.90,
    massBalanceErrorPercent: 0.05
  },
  {
    timeStep: 6,
    timeLabel: '+90m (13:00)',
    rainfallRateMmHr: 20.0,
    totalRunoffM3: 198000,
    drainageDischargeM3s: 28.0,
    surchargingNodesCount: 4,
    maxFloodDepthM: 0.48,
    totalFloodedAreaKm2: 2.70,
    massBalanceErrorPercent: 0.03
  }
];

export const WARDS_SUMMARY: WardMetric[] = [
  {
    code: 'F/North',
    name: 'Sion - Matunga East',
    riskScore: 92,
    riskGrade: 'CRITICAL',
    populationAtRisk: 84200,
    floodedRoadKm: 6.4,
    activePumps: 6,
    criticalSpots: ['Gandhi Market (0.88m)', 'Sion Circle (0.42m)', 'Bhaudaji Rd']
  },
  {
    code: 'F/South',
    name: 'Parel - Hindmata',
    riskScore: 89,
    riskGrade: 'CRITICAL',
    populationAtRisk: 76500,
    floodedRoadKm: 5.8,
    activePumps: 8,
    criticalSpots: ['Hindmata Underpass (0.74m)', 'Madhavbaug', 'Chitra Cinema']
  },
  {
    code: 'L',
    name: 'Kurla - LBS Marg',
    riskScore: 84,
    riskGrade: 'CRITICAL',
    populationAtRisk: 95000,
    floodedRoadKm: 7.2,
    activePumps: 4,
    criticalSpots: ['Kamani Junction (0.55m)', 'Bail Bazar', 'Sheetal Cinema']
  },
  {
    code: 'H/West',
    name: 'Bandra - Santacruz West',
    riskScore: 78,
    riskGrade: 'HIGH',
    populationAtRisk: 48000,
    floodedRoadKm: 4.1,
    activePumps: 5,
    criticalSpots: ['Milan Subway (1.05m CLOSED)', 'Linking Rd Junction']
  },
  {
    code: 'K/West',
    name: 'Andheri West - Juhu',
    riskScore: 71,
    riskGrade: 'HIGH',
    populationAtRisk: 52000,
    floodedRoadKm: 3.6,
    activePumps: 6,
    criticalSpots: ['Andheri Subway (0.60m)', 'Veera Desai Rd']
  },
  {
    code: 'G/North',
    name: 'Dadar West - Dharavi',
    riskScore: 65,
    riskGrade: 'MODERATE',
    populationAtRisk: 38000,
    floodedRoadKm: 2.8,
    activePumps: 3,
    criticalSpots: ['Senapati Bapat Marg', 'Kalanagar Slipway']
  },
  {
    code: 'A',
    name: 'Colaba - Fort',
    riskScore: 32,
    riskGrade: 'LOW',
    populationAtRisk: 12000,
    floodedRoadKm: 0.8,
    activePumps: 2,
    criticalSpots: ['Regal Circle (Puddle)']
  }
];

export const DRAINAGE_NODES: DrainageNodeTelemetry[] = [
  {
    id: 'NODE_HM_01',
    name: 'Hindmata Main Trunk Manhole M-104',
    ward: 'F/South',
    capacityM3s: 4.5,
    inflowM3s: 5.8,
    surchargeDepthM: 0.48,
    isBackflowing: true,
    waterLevelStatus: 'REVERSE_OVERFLOW'
  },
  {
    id: 'NODE_GM_02',
    name: 'Gandhi Market Outfall Culvert C-22',
    ward: 'F/North',
    capacityM3s: 6.2,
    inflowM3s: 7.9,
    surchargeDepthM: 0.62,
    isBackflowing: true,
    waterLevelStatus: 'REVERSE_OVERFLOW'
  },
  {
    id: 'NODE_MS_03',
    name: 'Milan Subway Sump Pit & Pump Intake',
    ward: 'H/West',
    capacityM3s: 3.0,
    inflowM3s: 3.8,
    surchargeDepthM: 0.85,
    isBackflowing: false,
    waterLevelStatus: 'SURCHARGED'
  },
  {
    id: 'NODE_KL_04',
    name: 'Kurla Mithi River Sluice Gate 04',
    ward: 'L',
    capacityM3s: 12.0,
    inflowM3s: 11.2,
    surchargeDepthM: 0.35,
    isBackflowing: false,
    waterLevelStatus: 'SURCHARGED'
  },
  {
    id: 'NODE_DH_05',
    name: 'Dadar TT Storm Box Drain B-08',
    ward: 'G/North',
    capacityM3s: 5.0,
    inflowM3s: 3.2,
    surchargeDepthM: 0.0,
    isBackflowing: false,
    waterLevelStatus: 'NORMAL'
  }
];

export const SAMPLE_CAP_ALERT: CapAlertPayload = {
  id: 'CAP-MCGM-2026-0923-004',
  identifier: 'urn:oid:2.49.0.0.356.0.2026.0923.004',
  sender: 'dmc-control@mcgm.gov.in',
  sent: '2026-09-23T11:30:00+05:30',
  status: 'Issued',
  msgType: 'Alert',
  scope: 'Public',
  severity: 'Extreme',
  urgency: 'Immediate',
  certainty: 'Observed',
  headline: 'EXTREME URBAN FLOODING & DRAINAGE SURCHARGE WARNING FOR LOW-LYING BASINS',
  description: 'Convective rainfall intensity of 65 mm/hr coupled with a 4.62m astronomical high tide at Mahim Bay has initiated severe reverse hydraulic orifice surcharge at Hindmata, Gandhi Market, and Milan Subway. Surface water depth exceeds 0.7m in depressions.',
  instruction: 'Disaster management officers and traffic wardens have blocked all subway approaches. Residents in ground-floor tenements in Ward F/North and Ward L must relocate immediately to designated municipal relief camps.',
  areaDesc: 'Greater Mumbai: Wards F/North, F/South, L, and H/West depressions',
  polygon: '19.015,72.845 19.040,72.865 19.075,72.885 19.085,72.840 19.015,72.845'
};

export const INITIAL_OPERATOR_CHATS: AiChatMessage[] = [
  {
    id: 'msg-01',
    sender: 'system',
    content: 'SIH26085 AI Municipal Assistant online. Wired to deterministic backend simulation engine, hydraulic network graphs, and CAP v1.2 alert dispatchers.',
    timestamp: '11:28'
  },
  {
    id: 'msg-02',
    sender: 'operator',
    content: 'What is the current maximum predicted flood depth at Hindmata at t+30m, and are the storm drains backflowing?',
    timestamp: '11:29'
  },
  {
    id: 'msg-03',
    sender: 'ai',
    content: 'According to our 2D diffusive wave solver coupled with the signed orifice exchange model:\n\n1. At Hindmata (Ward F/South), maximum water depth is predicted to reach **0.74m** at t+30m (12:00 IST).\n2. Trunk Manhole M-104 is actively **backflowing** at +1.3 m³/s because the hydraulic head in the surcharged drain line exceeds the street surface elevation.\n3. Recommendation: Deploy 2 additional high-discharge dewatering pumps (100 HP) towards Britannia Outfall.',
    toolCall: {
      name: 'get_nowcast_inundation_profile',
      args: { hotspot_id: 'spot-hindmata', horizon_minutes: 30 },
      result: '{"depth_m": 0.74, "drain_status": "surcharged_backflow", "inflow_rate_m3s": 5.8}'
    },
    timestamp: '11:29'
  }
];
