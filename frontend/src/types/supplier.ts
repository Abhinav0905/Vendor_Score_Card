export interface SupplierMetrics {
  id: string;
  name: string;
  dataAccuracy: number;
  errorRate: number;
  complianceScore: number;
  responseTime: number;
  lastSubmission: string;
  errorTypes: {
    type: string;
    count: number;
  }[];
}

export interface PerformanceTrend {
  month: string;
  accuracy: number;
  errors: number;
}

export interface Recommendation {
  id: string;
  supplierId: string;
  type: 'critical' | 'warning' | 'improvement';
  message: string;
  action: string;
}