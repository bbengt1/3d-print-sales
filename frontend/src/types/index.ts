export interface Setting {
  key: string;
  value: string;
  notes: string | null;
}

export interface Material {
  id: string;
  name: string;
  brand: string;
  spool_weight_g: number;
  spool_price: number;
  net_usable_g: number;
  cost_per_g: number;
  notes: string | null;
  active: boolean;
}

export interface Rate {
  id: string;
  name: string;
  value: number;
  unit: string;
  notes: string | null;
  active: boolean;
}

export interface Customer {
  id: string;
  name: string;
  email: string | null;
  phone: string | null;
  notes: string | null;
  job_count: number;
}

export interface Job {
  id: string;
  job_number: string;
  date: string;
  customer_id: string | null;
  customer_name: string | null;
  product_name: string;
  qty_per_plate: number;
  num_plates: number;
  material_id: string;
  total_pieces: number;
  material_per_plate_g: number;
  print_time_per_plate_hrs: number;
  labor_mins: number;
  design_time_hrs: number | null;
  electricity_cost: number;
  material_cost: number;
  labor_cost: number;
  design_cost: number;
  machine_cost: number;
  packaging_cost: number;
  shipping_cost: number;
  failure_buffer: number;
  subtotal_cost: number;
  overhead: number;
  total_cost: number;
  cost_per_piece: number;
  target_margin_pct: number;
  price_per_piece: number;
  total_revenue: number;
  platform_fees: number;
  net_profit: number;
  profit_per_piece: number;
  status: string;
}

export interface PaginatedJobs {
  items: Job[];
  total: number;
  skip: number;
  limit: number;
}

export interface DashboardSummary {
  total_jobs: number;
  total_pieces: number;
  total_revenue: number;
  total_costs: number;
  total_platform_fees: number;
  total_net_profit: number;
  avg_profit_per_piece: number;
  avg_margin_pct: number;
  top_material: string | null;
}

export interface RevenueDataPoint {
  date: string;
  revenue: number;
}

export interface MaterialUsageDataPoint {
  material: string;
  count: number;
}

export interface ProfitMarginDataPoint {
  date: string;
  job: string;
  product: string;
  margin: number;
}

export interface CalculateResponse {
  total_pieces: number;
  electricity_cost: number;
  material_cost: number;
  labor_cost: number;
  design_cost: number;
  machine_cost: number;
  packaging_cost: number;
  shipping_cost: number;
  failure_buffer: number;
  subtotal_cost: number;
  overhead: number;
  total_cost: number;
  cost_per_piece: number;
  price_per_piece: number;
  total_revenue: number;
  platform_fees: number;
  net_profit: number;
  profit_per_piece: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}
