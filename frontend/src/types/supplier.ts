export interface SupplierErrorType {
  type: string;
  count: number;
}

export interface SupplierError {
  supplier_id: string;
  error_types: SupplierErrorType[];
}

export interface PerformanceTrend {
  id: number;
  supplier_id: string;
  month: string;
  accuracy: number;
  errors: number;
}

export interface Supplier {
  id: string;
  name: string;
  data_accuracy: number;
  error_rate: number;
  compliance_score: number;
  response_time: number; // in hours
  last_submission?: string;
}

export interface SupplierMetrics extends Supplier {
  supplier_errors: SupplierError[];
  performance_trends: PerformanceTrend[];
}

export interface Recommendation {
  id: number;
  supplier_id: string;
  title: string;
  description: string;
  impact: 'high' | 'medium' | 'low';
}

// EPCIS file submission interfaces
export enum FileStatus {
  RECEIVED = "received",
  PROCESSING = "processing",
  VALIDATED = "validated",
  FAILED = "failed",
  HELD = "held", 
  REPROCESSED = "reprocessed"
}

export interface ValidationError {
  id: string;
  type: string; // structure, field, sequence, aggregation
  severity: string; // error, warning
  message: string;
  line_number?: number;
  is_resolved: boolean;
  resolution_note?: string;
  resolved_at?: string;
  resolved_by?: string;
}

export interface EPCISSubmission {
  id: string;
  supplier_id: string;
  file_name: string;
  status: string;
  submission_date: string;
  completion_date?: string;
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  event_count: number;
  errors: ValidationError[];
}

export interface SubmissionListResponse {
  total: number;
  offset: number;
  limit: number;
  submissions: EPCISSubmission[];
}

// Supplier scorecard interface
export interface ErrorTypeBreakdown {
  [key: string]: number;
}

export interface WeeklyMetric {
  week: string;
  submissions: number;
  errors: number;
  error_rate: number;
}

export interface SubmissionStats {
  total: number;
  valid: number;
  invalid: number;
  validity_rate: number;
}

export interface ErrorStats {
  total_errors: number;
  total_warnings: number;
  avg_errors_per_submission: number;
  error_type_breakdown: ErrorTypeBreakdown;
}

export interface SupplierScorecard {
  supplier_id: string;
  supplier_name: string;
  time_period: string;
  data_accuracy: number;
  error_rate: number;
  response_time: number;
  submission_stats: SubmissionStats;
  error_stats: ErrorStats;
  weekly_trends: WeeklyMetric[];
}

// Dashboard stats interface
export interface TopSupplier {
  failure_count: any;
  success_count: any;
  error_rate: any;
  id: string;
  name: string;
  submission_count: number;
}

export interface DashboardStats {
  total_submissions: number;
  successful_submissions: number;
  failed_submissions: number;
  submission_by_status: Record<string, number>;
  top_suppliers: TopSupplier[];
  error_type_distribution: Record<string, number>;
}