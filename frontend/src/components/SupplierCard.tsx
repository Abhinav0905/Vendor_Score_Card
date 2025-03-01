import React from 'react';
import { BarChart3, AlertTriangle, Clock, CheckCircle } from 'lucide-react';
import { SupplierMetrics } from '../types/supplier';

interface SupplierCardProps {
  supplier: SupplierMetrics;
  onClick: (id: string) => void;
}

export const SupplierCard: React.FC<SupplierCardProps> = ({ supplier, onClick }) => {
  const getScoreColor = (score: number) => {
    if (score >= 95) return 'text-green-600';
    if (score >= 85) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div 
      onClick={() => onClick(supplier.id)}
      className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-lg font-semibold text-gray-800">{supplier.name}</h3>
        <span className={`text-2xl font-bold ${getScoreColor(supplier.complianceScore)}`}>
          {supplier.complianceScore}%
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-500" />
          <div>
            <p className="text-sm text-gray-600">Accuracy</p>
            <p className="font-semibold">{supplier.dataAccuracy}%</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-red-500" />
          <div>
            <p className="text-sm text-gray-600">Error Rate</p>
            <p className="font-semibold">{supplier.errorRate}%</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-yellow-500" />
          <div>
            <p className="text-sm text-gray-600">Response Time</p>
            <p className="font-semibold">{supplier.responseTime}h</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-500" />
          <div>
            <p className="text-sm text-gray-600">Last Update</p>
            <p className="font-semibold">{new Date(supplier.lastSubmission).toLocaleDateString()}</p>
          </div>
        </div>
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-semibold text-gray-700 mb-2">Top Errors</h4>
        <div className="space-y-1">
          {supplier.errorTypes.slice(0, 2).map((error, index) => (
            <div key={index} className="flex justify-between text-sm">
              <span className="text-gray-600">{error.type}</span>
              <span className="font-medium text-red-500">{error.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};