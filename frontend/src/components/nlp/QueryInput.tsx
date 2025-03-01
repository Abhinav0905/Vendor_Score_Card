import React, { useState } from 'react';
import { Search, Sparkles } from 'lucide-react';
import { processNLPQuery } from '../../utils/nlpProcessor';

interface QueryInputProps {
  onQueryResult: (result: any) => void;
}

export const QueryInput: React.FC<QueryInputProps> = ({ onQueryResult }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await processNLPQuery(query);
    onQueryResult(result);
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="flex items-center gap-2 mb-4">
        <Sparkles className="w-5 h-5 text-blue-500" />
        <span className="text-sm font-medium">Ask anything about your suppliers</span>
      </div>
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., 'Show me suppliers with error rates above 5%'"
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
      </div>
    </form>
  );
};