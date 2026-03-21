import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import ReportControls from '@/components/ui/ReportControls';
import { SkeletonTable } from '@/components/ui/Skeleton';
import type { InventoryReport } from '@/types';

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe', '#e0e7ff'];
const formatTooltipCurrency = (value: string | number | readonly (string | number)[] | undefined) => {
  const normalized = Array.isArray(value) ? value[0] : value;
  return formatCurrency(Number(normalized ?? 0));
};

export default function InventoryReportPage() {
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const { data, isLoading } = useQuery<InventoryReport>({
    queryKey: ['report', 'inventory', dateFrom, dateTo],
    queryFn: () =>
      api
        .get('/reports/inventory', {
          params: {
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
          },
        })
        .then((r) => r.data),
  });

  return (
    <div>
      <h2 className="text-2xl font-bold mb-6">Inventory Report</h2>

      <ReportControls
        dateFrom={dateFrom}
        dateTo={dateTo}
        showPeriod={false}
        csvUrl="/reports/inventory/csv"
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      {isLoading ? (
        <SkeletonTable rows={5} cols={6} />
      ) : !data ? null : (
        <div className="space-y-8">
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Total Products</p>
              <p className="text-3xl font-bold mt-1">{data.total_products}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Stock Value</p>
              <p className="text-3xl font-bold mt-1">{formatCurrency(data.total_stock_value)}</p>
            </div>
            <div className="bg-card border border-border rounded-lg p-6 text-center">
              <p className="text-sm text-muted-foreground">Low Stock Items</p>
              <p className={`text-3xl font-bold mt-1 ${data.low_stock_count > 0 ? 'text-amber-600 dark:text-amber-400' : ''}`}>
                {data.low_stock_count}
              </p>
            </div>
          </div>

          {/* Stock levels table */}
          {data.stock_levels.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Stock Levels</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="px-4 py-2 font-medium">SKU</th>
                      <th className="px-4 py-2 font-medium">Product</th>
                      <th className="px-4 py-2 font-medium text-right">Stock</th>
                      <th className="px-4 py-2 font-medium text-right">Unit Cost</th>
                      <th className="px-4 py-2 font-medium text-right">Value</th>
                      <th className="px-4 py-2 font-medium text-right">Reorder</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.stock_levels.map((row) => (
                      <tr key={row.product_id} className="border-b border-border last:border-0 hover:bg-accent/50">
                        <td className="px-4 py-2 font-mono text-xs">{row.sku}</td>
                        <td className="px-4 py-2">{row.name}</td>
                        <td className={`px-4 py-2 text-right ${row.is_low_stock ? 'text-amber-600 dark:text-amber-400 font-bold' : ''}`}>
                          {row.stock_qty}
                        </td>
                        <td className="px-4 py-2 text-right">{formatCurrency(row.unit_cost)}</td>
                        <td className="px-4 py-2 text-right">{formatCurrency(row.stock_value)}</td>
                        <td className="px-4 py-2 text-right text-muted-foreground">{row.reorder_point}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Turnover chart */}
            {data.turnover.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Inventory Turnover</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.turnover.slice(0, 10)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="product" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                    <YAxis tick={{ fontSize: 12 }} stroke="var(--color-muted-foreground)" />
                    <Tooltip contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                    <Bar dataKey="turnover_rate" name="Turnover Rate" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Material usage chart */}
            {data.material_usage.length > 0 && (
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-lg font-semibold mb-4">Material Usage</h3>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={data.material_usage}
                      dataKey="spool_cost"
                      nameKey="material"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={(props) => `${String(props.name ?? '')} (${formatCurrency(Number(props.value ?? 0))})`}
                    >
                      {data.material_usage.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={formatTooltipCurrency} contentStyle={{ backgroundColor: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: '8px' }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
