import React, { useState } from 'react';
import { Search, Filter, Download } from 'lucide-react';
import { SupplierCard } from './SupplierCard';
import { SupplierDetails } from './SupplierDetails';
import { FilterPanel } from './filters/FilterPanel';
import { QueryInput } from './nlp/QueryInput';
import { supplierData, recommendations } from '../data/mockData';
import { exportToCSV } from '../utils/export';

export const Dashboard: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSupplier, setSelectedSupplier] = useState<string | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const [filteredSuppliers, setFilteredSuppliers] = useState(supplierData);

  const handleSearch = (term: string) => {
    setSearchTerm(term);
    const filtered = supplierData.filter(supplier =>
      supplier.name.toLowerCase().includes(term.toLowerCase())
    );
    setFilteredSuppliers(filtered);
  };

  const handleFilterApply = (filters: any) => {
    const filtered = supplierData.filter(supplier =>
      supplier.dataAccuracy >= filters.minAccuracy &&
      supplier.errorRate <= filters.maxErrorRate
    );
    setFilteredSuppliers(filtered);
  };

  const handleNLPQuery = (result: { suppliers: any[]; message: string }) => {
    setFilteredSuppliers(result.suppliers);
  };

  const handleExport = () => {
    exportToCSV(filteredSuppliers);
  };

  const selectedSupplierData = selectedSupplier 
    ? supplierData.find(s => s.id === selectedSupplier)
    : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <h1 className="text-2xl font-bold text-gray-900">
            Supplier Score Card Analytics
          </h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
        {/* NLP Query Section */}
        <div className="mb-8">
          <QueryInput onQueryResult={handleNLPQuery} />
        </div>

        {/* Search and Actions Bar */}
        <div className="mb-6 flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              type="text"
              placeholder="Search suppliers..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={searchTerm}
              onChange={(e) => handleSearch(e.target.value)}
            />
          </div>
          <button 
            onClick={() => setIsFilterOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            <Filter className="w-5 h-5" />
            <span>Filter</span>
          </button>
          <button 
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Download className="w-5 h-5" />
            <span>Export</span>
          </button>
        </div>

        {/* Supplier Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {filteredSuppliers.map(supplier => (
            <SupplierCard
              key={supplier.id}
              supplier={supplier}
              onClick={() => setSelectedSupplier(supplier.id)}
            />
          ))}
        </div>

        {/* Recommendations Section */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4">Recommendations</h2>
          <div className="space-y-4">
            {recommendations.map(rec => (
              <div
                key={rec.id}
                className={`p-4 rounded-lg ${
                  rec.type === 'critical' ? 'bg-red-50 border-red-200' :
                  rec.type === 'warning' ? 'bg-yellow-50 border-yellow-200' :
                  'bg-blue-50 border-blue-200'
                } border`}
              >
                <h3 className="font-semibold mb-2">{rec.message}</h3>
                <p className="text-sm text-gray-600">
                  Recommended Action: {rec.action}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Modals */}
        {selectedSupplierData && (
          <SupplierDetails
            supplier={selectedSupplierData}
            onClose={() => setSelectedSupplier(null)}
          />
        )}
        
        <FilterPanel
          isOpen={isFilterOpen}
          onClose={() => setIsFilterOpen(false)}
          onApplyFilters={handleFilterApply}
        />
      </main>
    </div>
  );
};