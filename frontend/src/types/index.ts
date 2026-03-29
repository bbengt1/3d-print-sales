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
  spools_in_stock: number;
  reorder_point: number;
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

export interface Printer {
  id: string;
  name: string;
  slug: string;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  location: string | null;
  status: string;
  is_active: boolean;
  notes: string | null;
  monitor_enabled: boolean;
  monitor_provider: string | null;
  monitor_base_url: string | null;
  monitor_api_key: string | null;
  monitor_poll_interval_seconds: number;
  monitor_online: boolean | null;
  monitor_status: string | null;
  monitor_progress_percent: number | null;
  current_print_name: string | null;
  monitor_last_message: string | null;
  monitor_last_error: string | null;
  monitor_bed_temp_c: number | null;
  monitor_tool_temp_c: number | null;
  monitor_last_seen_at: string | null;
  monitor_last_updated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PrinterConnectionTestResult {
  ok: boolean;
  provider: string;
  normalized_status: string | null;
  online: boolean | null;
  message: string | null;
}

export interface PaginatedPrinters {
  items: Printer[];
  total: number;
  skip: number;
  limit: number;
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
  product_id: string | null;
  printer_id: string | null;
  printer: Printer | null;
  inventory_added: boolean;
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

export interface FinanceDashboardSummary {
  cash_on_hand: number;
  unpaid_invoices: number;
  unpaid_bills: number;
  current_month_net_income: number;
  inventory_asset_value: number;
  tax_payable: number;
  payouts_in_transit: number;
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

export interface Product {
  id: string;
  sku: string;
  upc: string | null;
  name: string;
  description: string | null;
  material_id: string;
  unit_cost: number;
  unit_price: number;
  stock_qty: number;
  reorder_point: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface PaginatedProducts {
  items: Product[];
  total: number;
  skip: number;
  limit: number;
}

export interface InventoryTransaction {
  id: string;
  product_id: string;
  product_name: string | null;
  product_sku: string | null;
  job_id: string | null;
  type: string;
  quantity: number;
  unit_cost: number;
  notes: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string | null;
}

export interface PaginatedTransactions {
  items: InventoryTransaction[];
  total: number;
  skip: number;
  limit: number;
}

export interface InventoryReconcileResponse {
  product_id: string;
  current_qty: number;
  counted_qty: number;
  variance: number;
  approval_required: boolean;
  detail: string;
  transaction: InventoryTransaction | null;
}

export interface InventoryAlert {
  type: string;
  id: string;
  name: string;
  sku: string | null;
  current_stock: number;
  reorder_point: number;
}

export interface SalesChannel {
  id: string;
  name: string;
  platform_fee_pct: number;
  fixed_fee: number;
  is_active: boolean;
  created_at: string | null;
}

export interface SaleItem {
  id: string;
  sale_id: string;
  product_id: string | null;
  job_id: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
  unit_cost: number;
  created_at: string | null;
}

export interface Sale {
  id: string;
  sale_number: string;
  date: string;
  customer_id: string | null;
  customer_name: string | null;
  channel_id: string | null;
  status: string;
  subtotal: number;
  shipping_charged: number;
  shipping_cost: number;
  platform_fees: number;
  tax_collected: number;
  total: number;
  item_cogs: number;
  gross_profit: number;
  contribution_margin: number;
  payment_method: string | null;
  tracking_number: string | null;
  notes: string | null;
  items: SaleItem[];
  created_at: string | null;
  updated_at: string | null;
}

export interface SaleListItem {
  id: string;
  sale_number: string;
  date: string;
  customer_name: string | null;
  channel_id: string | null;
  status: string;
  total: number;
  gross_profit: number;
  contribution_margin: number;
  item_count: number;
  created_at: string | null;
}

export interface PaginatedSales {
  items: SaleListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface SalesMetrics {
  total_sales: number;
  gross_sales: number;
  item_cogs: number;
  gross_profit: number;
  platform_fees: number;
  shipping_costs: number;
  contribution_margin: number;
  net_profit: number | null;
  total_units_sold: number;
  avg_order_value: number;
  refund_count: number;
  refund_rate: number;
  revenue_by_channel: {
    channel_id: string | null;
    channel_name: string;
    gross_sales: number;
    item_cogs: number;
    gross_profit: number;
    platform_fees: number;
    shipping_costs: number;
    contribution_margin: number;
    order_count: number;
  }[];
}

// ── Reports ──────────────────────────────────────────────────────

export interface StockLevelRow {
  product_id: string;
  sku: string;
  name: string;
  stock_qty: number;
  unit_cost: number;
  stock_value: number;
  reorder_point: number;
  is_low_stock: boolean;
}

export interface InventoryReport {
  stock_levels: StockLevelRow[];
  total_stock_value: number;
  total_products: number;
  low_stock_count: number;
  material_usage: { material: string; total_consumed_g: number; spool_cost: number }[];
  turnover: { product: string; sku: string; sold_qty: number; stock_qty: number; turnover_rate: number }[];
}

export interface SalesReportRow {
  period: string;
  order_count: number;
  gross_sales: number;
  item_cogs: number;
  gross_profit: number;
  platform_fees: number;
  shipping_costs: number;
  contribution_margin: number;
}

export interface ProductRanking {
  product_id: string | null;
  description: string;
  units_sold: number;
  gross_sales: number;
  item_cogs: number;
  gross_profit: number;
  platform_fees: number;
  shipping_costs: number;
  contribution_margin: number;
}

export interface ChannelBreakdown {
  channel_name: string;
  order_count: number;
  gross_sales: number;
  item_cogs: number;
  gross_profit: number;
  platform_fees: number;
  shipping_costs: number;
  contribution_margin: number;
}

export interface SalesReport {
  period_data: SalesReportRow[];
  top_products: ProductRanking[];
  channel_breakdown: ChannelBreakdown[];
  total_orders: number;
  gross_sales: number;
  item_cogs: number;
  gross_profit: number;
  platform_fees: number;
  shipping_costs: number;
  contribution_margin: number;
  net_profit: number | null;
}

export interface PLRow {
  period: string;
  sales_revenue: number;
  operational_production_estimate: number;
  material_costs: number;
  labor_costs: number;
  machine_costs: number;
  overhead_costs: number;
  platform_fees: number;
  shipping_costs: number;
  total_costs: number;
  gross_profit: number;
  notes: string;
}

export interface PLSummary {
  sales_revenue: number;
  operational_production_estimate: number;
  total_revenue: number;
  material_costs: number;
  labor_costs: number;
  machine_costs: number;
  overhead_costs: number;
  platform_fees: number;
  shipping_costs: number;
  total_costs: number;
  gross_profit: number;
  profit_margin_pct: number;
  reporting_basis: string;
  production_estimate_note: string;
}

export interface PLReport {
  summary: PLSummary;
  period_data: PLRow[];
}
