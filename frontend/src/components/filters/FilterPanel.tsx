import React from 'react';
import { X } from 'lucide-react';

interface FilterPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onApplyFilters: (filters: FilterState) => void;
}

interface FilterState {
  minAccuracy: number;
  maxErrorRate: number;
  dateRange: string;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({ isOpen, onClose, onApplyFilters }) => {
  const [filters, setFilters] = React.useState<FilterState>({
    minAccuracy: 0,
    maxErrorRate: 100,
    dateRange: '30'
  });

  const handleApply = () => {
    onApplyFilters(filters);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex justify-end">
      <div className="bg-white w-96 h-full p-6 shadow-lg">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold">Advanced Filters</h3>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Minimum Accuracy (%)
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={filters.minAccuracy}
              onChange={(e) => setFilters(prev => ({ ...prev, minAccuracy: Number(e.target.value) }))}
              className="w-full"
            />
            <span className="text-sm text-gray-600">{filters.minAccuracy}%</span>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Maximum Error Rate (%)
            </label>
            <input
              type="range"
              min="0"
              max="100"
              value={filters.maxErrorRate}
              onChange={(e) => setFilters(prev => ({ ...prev, maxErrorRate: Number(e.target.value) }))}
              className="w-full"
            />
            <span className="text-sm text-gray-600">{filters.maxErrorRate}%</span>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Date Range
            </label>
            <select
              value={filters.dateRange}
              onChange={(e) => setFilters(prev => ({ ...prev, dateRange: e.target.value }))}
              className="w-full border border-gray-300 rounded-md p-2"
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </select>
          </div>

          <button
            onClick={handleApply}
            className="w-full bg-blue-600 text-white py-2 rounded-md hover:bg-blue-700"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </div>
  );
};