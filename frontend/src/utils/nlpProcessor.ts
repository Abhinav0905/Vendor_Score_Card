import { supplierData } from '../data/mockData';
import { SupplierMetrics } from '../types/supplier';

type QueryResult = {
  suppliers: SupplierMetrics[];
  message: string;
};

export const processNLPQuery = async (query: string): Promise<QueryResult> => {
  const normalizedQuery = query.toLowerCase();
  
  // Simple keyword-based processing
  if (normalizedQuery.includes('error rate') && normalizedQuery.includes('above')) {
    const threshold = parseFloat(normalizedQuery.match(/\d+(\.\d+)?/)?.[0] || '5');
    const filteredSuppliers = supplierData.filter(s => s.errorRate > threshold);
    return {
      suppliers: filteredSuppliers,
      message: `Found ${filteredSuppliers.length} suppliers with error rate above ${threshold}%`
    };
  }

  if (normalizedQuery.includes('top') && normalizedQuery.includes('accuracy')) {
    const count = parseInt(normalizedQuery.match(/\d+/)?.[0] || '5');
    const sortedSuppliers = [...supplierData]
      .sort((a, b) => b.dataAccuracy - a.dataAccuracy)
      .slice(0, count);
    return {
      suppliers: sortedSuppliers,
      message: `Top ${count} suppliers by accuracy`
    };
  }

  return {
    suppliers: supplierData,
    message: 'Showing all suppliers'
  };
};