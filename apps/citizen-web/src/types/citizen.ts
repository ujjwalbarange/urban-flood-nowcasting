export type AlertSeverity = 'red' | 'orange' | 'yellow' | 'green';

export interface FloodAlert {
  id: string;
  severity: AlertSeverity;
  headline: string;
  affectedWards: string[];
  description: string;
  actionGuidance: string[];
  issuedAt: string;
  validUntil: string;
  source: string;
}

export interface WaterHotspot {
  id: string;
  name: string;
  ward: string;
  lat: number;
  lng: number;
  currentDepthMeters: number;
  predictedDepth30m: number;
  flowVelocityMs: number;
  isPassableWalking: boolean;
  isPassableCar: boolean;
  drainStatus: 'normal' | 'surcharged' | 'backflowing';
  lastUpdated: string;
}

export interface RouteStep {
  instruction: string;
  distanceMeters: number;
  waterDepthMeters: number;
  isFlooded: boolean;
}

export interface SafeRoute {
  id: string;
  routeName: string;
  origin: string;
  destination: string;
  mode: 'walking' | 'two_wheeler' | 'car' | 'emergency';
  totalDistanceKm: number;
  estimatedMinutes: number;
  maxFloodDepthMeters: number;
  safeStatus: 'SAFE' | 'CAUTION' | 'IMPASSABLE';
  steps: RouteStep[];
}

export interface Shelter {
  id: string;
  name: string;
  ward: string;
  address: string;
  distanceKm: number;
  lat: number;
  lng: number;
  totalCapacity: number;
  currentOccupancy: number;
  contactNumber: string;
  facilities: string[];
  isRescueHub: boolean;
}

export interface CrowdReport {
  id: string;
  locality: string;
  ward: string;
  category: 'waterlogging' | 'drain_overflow' | 'open_manhole' | 'stranded' | 'tree_fall';
  depthDescription: string;
  depthMeters: number;
  reportedAt: string;
  upvotes: number;
  status: 'VERIFIED_BMC' | 'COMMUNITY_REPORTED';
}

export interface NowcastForecastItem {
  timeLabel: string;
  rainfallMmHr: number;
  accumulatedMm: number;
  inundationRisk: 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME';
}
