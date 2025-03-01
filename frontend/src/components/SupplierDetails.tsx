import React from 'react';
import { PerformanceChart } from './charts/PerformanceChart';
import { SupplierMetrics } from '../types/supplier';
import { performanceTrends } from '../data/mockData';

interface SupplierDetailsProps {
  supplier: SupplierMetrics;
  onClose: () => void;
}

export const SupplierDetails: React.FC<SupplierDetailsProps> = ({ supplier, onClose }) => {
  const trends = performanceTrends[supplier.id] || [];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-40 flex items-center justify-center">
      <div className="bg-white rounded-lg w-full max-w-4xl p-6 m-4">
        <div className="flex justify-between items-start mb-6">
          <h2 className="text-2xl font-bold">{supplier.name}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ×
          </button>
        </div>

        <div className="mb-8">
          <h3 className="text-lg font-semibold mb-4">Performance Trends</h3>
          <PerformanceChart data={trends} />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-lg font-semibold mb-4">Error Analysis</h3>
            <div className="space-y-2">
              {supplier.errorTypes.map((error, index) => (
                <div key={index} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                  <span>{error.type}</span>
                  <span className="font-semibold text-red-600">{error.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-4">Compliance Details</h3>
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600">Overall Score</p>
                <p className="text-2xl font-bold text-blue-600">{supplier.complianceScore}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Response Time</p>
                <p className="text-xl">{supplier.responseTime}h average</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};