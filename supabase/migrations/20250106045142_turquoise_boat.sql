/*
  # Initial Schema Setup for Pharma Track and Trace

  1. New Tables
    - `suppliers`
      - Basic supplier information
      - Performance metrics
    - `error_types`
      - Catalog of possible error types
    - `supplier_errors`
      - Track errors for each supplier
    - `performance_trends`
      - Monthly performance data
    - `recommendations`
      - System-generated recommendations

  2. Security
    - Enable RLS on all tables
    - Add policies for authenticated users
*/

-- Suppliers table
CREATE TABLE IF NOT EXISTS suppliers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  data_accuracy numeric NOT NULL DEFAULT 0,
  error_rate numeric NOT NULL DEFAULT 0,
  compliance_score numeric NOT NULL DEFAULT 0,
  response_time integer NOT NULL DEFAULT 0,
  last_submission timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Error types catalog
CREATE TABLE IF NOT EXISTS error_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL UNIQUE,
  severity text NOT NULL DEFAULT 'medium',
  description text,
  created_at timestamptz DEFAULT now()
);

-- Supplier errors tracking
CREATE TABLE IF NOT EXISTS supplier_errors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id uuid REFERENCES suppliers(id),
  error_type_id uuid REFERENCES error_types(id),
  count integer NOT NULL DEFAULT 0,
  reported_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

-- Performance trends
CREATE TABLE IF NOT EXISTS performance_trends (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id uuid REFERENCES suppliers(id),
  month date NOT NULL,
  accuracy numeric NOT NULL,
  errors integer NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Recommendations
CREATE TABLE IF NOT EXISTS recommendations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id uuid REFERENCES suppliers(id),
  type text NOT NULL,
  message text NOT NULL,
  action text NOT NULL,
  status text DEFAULT 'pending',
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable Row Level Security
ALTER TABLE suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_errors ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_trends ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Allow read access to authenticated users"
  ON suppliers FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow read access to authenticated users"
  ON error_types FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow read access to authenticated users"
  ON supplier_errors FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow read access to authenticated users"
  ON performance_trends FOR SELECT TO authenticated USING (true);

CREATE POLICY "Allow read access to authenticated users"
  ON recommendations FOR SELECT TO authenticated USING (true);