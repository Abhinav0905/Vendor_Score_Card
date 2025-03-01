import { SupplierMetrics } from '../types/supplier';

export const exportToCSV = (suppliers: SupplierMetrics[]) => {
  const headers = ['Name', 'Compliance Score', 'Data Accuracy', 'Error Rate', 'Response Time'];
  const rows = suppliers.map(s => [
    s.name,
    s.complianceScore,
    s.dataAccuracy,
    s.errorRate,
    s.responseTime
  ]);

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n');

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', 'supplier_analytics.csv');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};