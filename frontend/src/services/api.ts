import { supabase } from '../lib/supabase';
import { SupplierMetrics, PerformanceTrend, Recommendation } from '../types/supplier';

export const api = {
  suppliers: {
    async getAll(): Promise<SupplierMetrics[]> {
      const { data, error } = await supabase
        .from('suppliers')
        .select(`
          *,
          supplier_errors(
            error_types(type, count)
          ),
          performance_trends(month, accuracy, errors)
        `);
      
      if (error) throw error;
      return data;
    },

    async getById(id: string): Promise<SupplierMetrics | null> {
      const { data, error } = await supabase
        .from('suppliers')
        .select(`
          *,
          supplier_errors(
            error_types(type, count)
          ),
          performance_trends(month, accuracy, errors)
        `)
        .eq('id', id)
        .single();
      
      if (error) throw error;
      return data;
    }
  },

  recommendations: {
    async getAll(): Promise<Recommendation[]> {
      const { data, error } = await supabase
        .from('recommendations')
        .select('*');
      
      if (error) throw error;
      return data;
    }
  },

  trends: {
    async getBySupplier(supplierId: string): Promise<PerformanceTrend[]> {
      const { data, error } = await supabase
        .from('performance_trends')
        .select('*')
        .eq('supplier_id', supplierId)
        .order('month', { ascending: true });
      
      if (error) throw error;
      return data;
    }
  }
};