import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { PerformanceTrend } from '../../types/supplier';

interface PerformanceChartProps {
  data: PerformanceTrend[];
}

export const PerformanceChart: React.FC<PerformanceChartProps> = ({ data }) => {
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis yAxisId="left" />
          <YAxis yAxisId="right" orientation="right" />
          <Tooltip />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="accuracy" stroke="#2563eb" name="Accuracy %" />
          <Line yAxisId="right" type="monotone" dataKey="errors" stroke="#dc2626" name="Errors" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};