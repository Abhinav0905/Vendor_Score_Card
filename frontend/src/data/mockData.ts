import { SupplierMetrics, PerformanceTrend, Recommendation } from '../types/supplier';

export const supplierData: SupplierMetrics[] = [
  {
    id: '1',
    name: 'PharmaCorp Inc.',
    dataAccuracy: 95.5,
    errorRate: 2.3,
    complianceScore: 98,
    responseTime: 24,
    lastSubmission: '2024-03-15',
    errorTypes: [
      { type: 'Missing GTIN', count: 12 },
      { type: 'Invalid Date Format', count: 8 },
      { type: 'Incomplete Shipping Data', count: 5 }
    ]
  },
  {
    id: '2',
    name: 'MediSupply Co.',
    dataAccuracy: 88.2,
    errorRate: 5.7,
    complianceScore: 92,
    responseTime: 48,
    lastSubmission: '2024-03-14',
    errorTypes: [
      { type: 'Missing Batch Number', count: 25 },
      { type: 'Invalid EPCIS Format', count: 15 },
      { type: 'Wrong Product Code', count: 10 }
    ]
  },
  {
    id: '3',
    name: 'GlobalPharma Ltd.',
    dataAccuracy: 97.8,
    errorRate: 1.2,
    complianceScore: 99,
    responseTime: 12,
    lastSubmission: '2024-03-16',
    errorTypes: [
      { type: 'Data Synchronization Error', count: 5 },
      { type: 'Missing Expiry Date', count: 3 },
      { type: 'Invalid Location Code', count: 2 }
    ]
  }
];

export const performanceTrends: Record<string, PerformanceTrend[]> = {
  '1': [
    { month: 'Jan', accuracy: 94, errors: 15 },
    { month: 'Feb', accuracy: 95, errors: 12 },
    { month: 'Mar', accuracy: 95.5, errors: 10 }
  ],
  '2': [
    { month: 'Jan', accuracy: 87, errors: 28 },
    { month: 'Feb', accuracy: 88, errors: 22 },
    { month: 'Mar', accuracy: 88.2, errors: 20 }
  ],
  '3': [
    { month: 'Jan', accuracy: 97, errors: 6 },
    { month: 'Feb', accuracy: 97.5, errors: 4 },
    { month: 'Mar', accuracy: 97.8, errors: 3 }
  ]
};

export const recommendations: Recommendation[] = [
  {
    id: '1',
    supplierId: '2',
    type: 'critical',
    message: 'High rate of missing batch numbers detected',
    action: 'Implement automated batch number validation before submission'
  },
  {
    id: '2',
    supplierId: '1',
    type: 'warning',
    message: 'Increasing trend in GTIN errors',
    action: 'Review GTIN assignment process and staff training'
  },
  {
    id: '3',
    supplierId: '3',
    type: 'improvement',
    message: 'Minor data synchronization issues',
    action: 'Update data synchronization protocols'
  }
];