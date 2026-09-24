import { FloodAlert, WaterHotspot, SafeRoute, Shelter, CrowdReport, NowcastForecastItem } from '../types/citizen';

export const ACTIVE_ALERT: FloodAlert = {
  id: 'BOM-CAP-2026-09-001',
  severity: 'red',
  headline: 'IMD RED ALERT: Extreme Flash Flooding & Drainage Surcharge in Low-Lying Wards',
  affectedWards: ['Ward F/North (Sion-Matunga)', 'Ward F/South (Parel-Hindmata)', 'Ward L (Kurla)', 'Ward H/West (Bandra-Santacruz)'],
  description: 'Convective rainfall cell active over Island City and Suburbs with rain rates exceeding 55 mm/hr. Stormwater drainage networks in Hindmata and Gandhi Market are experiencing reverse orifice surcharge due to coinciding 4.6m high tide.',
  actionGuidance: [
    'Stay indoors unless advised by SDRF or BMC disaster marshals.',
    'Avoid all railway subways (Milan, Andheri, Khar, Dahisar) — completely closed to traffic.',
    'Do not walk or drive through moving water above ankle level.',
    'Move critical assets and family members to 1st floor or designated municipal relief shelters.'
  ],
  issuedAt: '2026-09-23 11:00 IST',
  validUntil: '2026-09-23 16:00 IST',
  source: 'MCGM Disaster Management Unit & IMD Nowcast Radar'
};

export const WATER_HOTSPOTS: WaterHotspot[] = [
  {
    id: 'spot-hindmata',
    name: 'Hindmata Cinema Junction',
    ward: 'F/South',
    lat: 19.0178,
    lng: 72.8478,
    currentDepthMeters: 0.52,
    predictedDepth30m: 0.74,
    flowVelocityMs: 0.42,
    isPassableWalking: false,
    isPassableCar: false,
    drainStatus: 'surcharged',
    lastUpdated: '3 mins ago'
  },
  {
    id: 'spot-gandhi-mkt',
    name: 'Gandhi Market (King\'s Circle)',
    ward: 'F/North',
    lat: 19.0345,
    lng: 72.8592,
    currentDepthMeters: 0.65,
    predictedDepth30m: 0.88,
    flowVelocityMs: 0.58,
    isPassableWalking: false,
    isPassableCar: false,
    drainStatus: 'backflowing',
    lastUpdated: '1 min ago'
  },
  {
    id: 'spot-milan-subway',
    name: 'Milan Subway Santacruz',
    ward: 'H/West',
    lat: 19.0832,
    lng: 72.8425,
    currentDepthMeters: 0.85,
    predictedDepth30m: 1.05,
    flowVelocityMs: 0.65,
    isPassableWalking: false,
    isPassableCar: false,
    drainStatus: 'backflowing',
    lastUpdated: 'Just now'
  },
  {
    id: 'spot-kurla-kamani',
    name: 'Kurla Kamani - LBS Road',
    ward: 'L',
    lat: 19.0726,
    lng: 72.8845,
    currentDepthMeters: 0.38,
    predictedDepth30m: 0.55,
    flowVelocityMs: 0.31,
    isPassableWalking: false,
    isPassableCar: false,
    drainStatus: 'surcharged',
    lastUpdated: '4 mins ago'
  },
  {
    id: 'spot-andheri-subway',
    name: 'Andheri Subway',
    ward: 'K/West',
    lat: 19.1197,
    lng: 72.8464,
    currentDepthMeters: 0.45,
    predictedDepth30m: 0.60,
    flowVelocityMs: 0.48,
    isPassableWalking: false,
    isPassableCar: false,
    drainStatus: 'surcharged',
    lastUpdated: '2 mins ago'
  },
  {
    id: 'spot-dadar-tt',
    name: 'Dadar TT Circle (Upper Flyover Ramp)',
    ward: 'F/North',
    lat: 19.0195,
    lng: 72.8431,
    currentDepthMeters: 0.12,
    predictedDepth30m: 0.18,
    flowVelocityMs: 0.15,
    isPassableWalking: true,
    isPassableCar: true,
    drainStatus: 'normal',
    lastUpdated: '5 mins ago'
  },
  {
    id: 'spot-bandra-sv',
    name: 'Bandra SV Road - Lucky Junction',
    ward: 'H/West',
    lat: 19.0552,
    lng: 72.8398,
    currentDepthMeters: 0.18,
    predictedDepth30m: 0.24,
    flowVelocityMs: 0.20,
    isPassableWalking: true,
    isPassableCar: true,
    drainStatus: 'normal',
    lastUpdated: '6 mins ago'
  }
];

export const SAFE_ROUTES: SafeRoute[] = [
  {
    id: 'route-sion-to-ruia',
    routeName: 'Sion Circle to Matunga Ruia Shelter via Dr. Ambedkar High Road',
    origin: 'Sion Koliwada',
    destination: 'Ruia College Relief Camp',
    mode: 'walking',
    totalDistanceKm: 2.1,
    estimatedMinutes: 26,
    maxFloodDepthMeters: 0.08,
    safeStatus: 'SAFE',
    steps: [
      { instruction: 'Head south on Sion Flyover service lane (Elevated ridge, dry surface)', distanceMeters: 450, waterDepthMeters: 0.02, isFlooded: false },
      { instruction: 'Turn left away from Gandhi Market dip onto Bhaudaji Road', distanceMeters: 800, waterDepthMeters: 0.05, isFlooded: false },
      { instruction: 'Follow elevated sidewalk past Maheshwari Udyan', distanceMeters: 550, waterDepthMeters: 0.08, isFlooded: false },
      { instruction: 'Arrive at Ruia College Auditorium Main Gate (Shelter Hub)', distanceMeters: 300, waterDepthMeters: 0.01, isFlooded: false }
    ]
  },
  {
    id: 'route-dadar-to-hinduja',
    routeName: 'Dadar Station (West) to Hinduja Emergency Hospital via Senapati Bapat Marg',
    origin: 'Dadar West Railway Stn',
    destination: 'P.D. Hinduja National Hospital',
    mode: 'car',
    totalDistanceKm: 2.8,
    estimatedMinutes: 14,
    maxFloodDepthMeters: 0.14,
    safeStatus: 'CAUTION',
    steps: [
      { instruction: 'Exit via Senapati Bapat Marg north corridor (Bypassing Hindmata depression)', distanceMeters: 1100, waterDepthMeters: 0.12, isFlooded: false },
      { instruction: 'Cross over Tilak Bridge flyover (High ground)', distanceMeters: 650, waterDepthMeters: 0.0, isFlooded: false },
      { instruction: 'Take Veer Savarkar Marg towards Mahim (Pavement ponding 14cm — reduce speed)', distanceMeters: 850, waterDepthMeters: 0.14, isFlooded: false },
      { instruction: 'Turn right into Hinduja Emergency Trauma Entrance', distanceMeters: 200, waterDepthMeters: 0.02, isFlooded: false }
    ]
  },
  {
    id: 'route-hindmata-direct',
    routeName: 'Hindmata Direct Corridor (Avoid — Submerged)',
    origin: 'Dadar TT',
    destination: 'Parel Junction',
    mode: 'car',
    totalDistanceKm: 1.4,
    estimatedMinutes: 45,
    maxFloodDepthMeters: 0.65,
    safeStatus: 'IMPASSABLE',
    steps: [
      { instruction: 'Dr. Ambedkar Road at Hindmata Cinema underpass (WATER DEPTH 65cm — HYDRAULIC LOCK RISK)', distanceMeters: 600, waterDepthMeters: 0.65, isFlooded: true },
      { instruction: 'Drain backflowing with manhole cover displacement risk', distanceMeters: 800, waterDepthMeters: 0.58, isFlooded: true }
    ]
  }
];

export const SHELTERS: Shelter[] = [
  {
    id: 'sh-1',
    name: 'Ruia College Relief Camp & Medical Hub',
    ward: 'Ward F/North',
    address: 'L.N. Road, Matunga East, Mumbai 400019',
    distanceKm: 0.8,
    lat: 19.0234,
    lng: 72.8521,
    totalCapacity: 350,
    currentOccupancy: 82,
    contactNumber: '+91 22 2414 3098',
    facilities: ['Clean Drinking Water', 'Dry Food Packets', 'First Aid Station', 'Backup Power Generator', 'Charging Stations'],
    isRescueHub: true
  },
  {
    id: 'sh-2',
    name: 'Sion Municipal Higher Secondary School',
    ward: 'Ward F/North',
    address: 'Sion West, Near L.T.M.G Hospital, Mumbai 400022',
    distanceKm: 1.4,
    lat: 19.0410,
    lng: 72.8610,
    totalCapacity: 250,
    currentOccupancy: 110,
    contactNumber: '+91 22 2407 6381',
    facilities: ['Emergency Doctor On-Duty', 'Infant Care Supplies', 'Sheltered Halls', 'Direct Ambulance Lane'],
    isRescueHub: false
  },
  {
    id: 'sh-3',
    name: 'Sharadashram Vidyamandir Emergency Center',
    ward: 'Ward G/North',
    address: 'Dr. B.A. Road, Dadar West, Mumbai 400028',
    distanceKm: 1.9,
    lat: 19.0190,
    lng: 72.8390,
    totalCapacity: 400,
    currentOccupancy: 145,
    contactNumber: '+91 22 2430 4562',
    facilities: ['SDRF Inflatable Boat Team Base', 'Community Kitchen (Meals)', 'Sanitation Kits', 'Security Desk'],
    isRescueHub: true
  },
  {
    id: 'sh-4',
    name: 'Kurla Bhabha Municipal Hall',
    ward: 'Ward L',
    address: 'Belgrami Road, Kurla West, Mumbai 400070',
    distanceKm: 3.2,
    lat: 19.0680,
    lng: 72.8790,
    totalCapacity: 300,
    currentOccupancy: 190,
    contactNumber: '+91 22 2650 0144',
    facilities: ['Emergency Water Tanker', 'Medical Triage', 'Power Battery Bank'],
    isRescueHub: false
  }
];

export const CROWD_REPORTS: CrowdReport[] = [
  {
    id: 'rep-01',
    locality: 'Sion Circle Flyover Slipway',
    ward: 'Ward F/North',
    category: 'waterlogging',
    depthDescription: 'Knee deep water (~40 cm), BEST buses crawling, smaller cars stalled',
    depthMeters: 0.40,
    reportedAt: '12 mins ago',
    upvotes: 42,
    status: 'VERIFIED_BMC'
  },
  {
    id: 'rep-02',
    locality: 'Hindmata Underpass Pedestrian Pathway',
    ward: 'Ward F/South',
    category: 'drain_overflow',
    depthDescription: 'Stormwater manhole lid popping open due to backpressure; muddy water spewing',
    depthMeters: 0.55,
    reportedAt: '18 mins ago',
    upvotes: 68,
    status: 'VERIFIED_BMC'
  },
  {
    id: 'rep-03',
    locality: 'Gandhi Market North Entrance',
    ward: 'Ward F/North',
    category: 'stranded',
    depthDescription: '3 elderly residents stranded near shop portico, water level rising',
    depthMeters: 0.65,
    reportedAt: '25 mins ago',
    upvotes: 89,
    status: 'VERIFIED_BMC'
  },
  {
    id: 'rep-04',
    locality: 'Bandra Station East Skywalk Stairs',
    ward: 'Ward H/East',
    category: 'waterlogging',
    depthDescription: 'Ankle deep runoff (~15 cm), staircase slippery but passable',
    depthMeters: 0.15,
    reportedAt: '34 mins ago',
    upvotes: 15,
    status: 'COMMUNITY_REPORTED'
  }
];

export const NOWCAST_TIMELINE: NowcastForecastItem[] = [
  { timeLabel: 'Now (11:30)', rainfallMmHr: 48, accumulatedMm: 12.0, inundationRisk: 'HIGH' },
  { timeLabel: '+15m (11:45)', rainfallMmHr: 58, accumulatedMm: 26.5, inundationRisk: 'EXTREME' },
  { timeLabel: '+30m (12:00)', rainfallMmHr: 65, accumulatedMm: 42.8, inundationRisk: 'EXTREME' },
  { timeLabel: '+45m (12:15)', rainfallMmHr: 52, accumulatedMm: 55.8, inundationRisk: 'EXTREME' },
  { timeLabel: '+60m (12:30)', rainfallMmHr: 36, accumulatedMm: 64.8, inundationRisk: 'HIGH' },
  { timeLabel: '+90m (13:00)', rainfallMmHr: 22, accumulatedMm: 72.0, inundationRisk: 'MEDIUM' },
  { timeLabel: '+120m (13:30)', rainfallMmHr: 14, accumulatedMm: 76.5, inundationRisk: 'LOW' },
];
