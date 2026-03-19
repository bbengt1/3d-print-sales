import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Calculator } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Material, CalculateResponse } from '@/types';

export default function CalculatorPage() {
  const navigate = useNavigate();

  const { data: materials } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const [form, setForm] = useState({
    qty_per_plate: 1,
    num_plates: 1,
    material_id: '',
    material_per_plate_g: 0,
    print_time_per_plate_hrs: 0,
    labor_mins: 0,
    design_time_hrs: 0,
    shipping_cost: 0,
    target_margin_pct: 40,
  });

  const [result, setResult] = useState<CalculateResponse | null>(null);

  useEffect(() => {
    if (!form.material_id || form.material_per_plate_g <= 0 || form.print_time_per_plate_hrs <= 0) {
      setResult(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.post('/jobs/calculate', form);
        setResult(data);
      } catch {
        setResult(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [form]);

  const update = (field: string, value: number | string) => setForm((f) => ({ ...f, [field]: value }));

  const saveAsJob = () => {
    const params = new URLSearchParams();
    params.set('from_calc', '1');
    Object.entries(form).forEach(([k, v]) => params.set(k, String(v)));
    navigate(`/jobs/new?${params}`);
    toast.info('Fill in job number and details to save');
  };

  const Field = ({ label, field, ...rest }: { label: string; field: string; [k: string]: any }) => (
    <div>
      <label className="block text-sm font-medium mb-1.5">{label}</label>
      <input
        type="number"
        value={(form as any)[field]}
        onChange={(e) => update(field, Number(e.target.value))}
        className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        {...rest}
      />
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Calculator className="w-8 h-8 text-primary" />
        <h1 className="text-3xl font-bold">Cost Calculator</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Print Parameters</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Material</label>
                <select
                  value={form.material_id}
                  onChange={(e) => update('material_id', e.target.value)}
                  className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Select material...</option>
                  {materials?.map((m) => (
                    <option key={m.id} value={m.id}>{m.name} ({m.brand}) — ${Number(m.cost_per_g).toFixed(4)}/g</option>
                  ))}
                </select>
              </div>
              <Field label="Qty per Plate" field="qty_per_plate" min={1} />
              <Field label="Number of Plates" field="num_plates" min={1} />
              <Field label="Material per Plate (g)" field="material_per_plate_g" min={0} step="0.01" />
              <Field label="Print Time per Plate (hrs)" field="print_time_per_plate_hrs" min={0} step="0.01" />
            </div>
          </div>

          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Labor & Costs</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Labor Time (mins)" field="labor_mins" min={0} />
              <Field label="Design Time (hrs)" field="design_time_hrs" min={0} step="0.01" />
              <Field label="Shipping Cost ($)" field="shipping_cost" min={0} step="0.01" />
              <div>
                <label className="block text-sm font-medium mb-1.5">Target Margin: {form.target_margin_pct}%</label>
                <input
                  type="range"
                  min={0}
                  max={90}
                  value={form.target_margin_pct}
                  onChange={(e) => update('target_margin_pct', Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-1">
          <div className="bg-card border border-border rounded-lg p-6 sticky top-24">
            <h3 className="text-lg font-semibold mb-4">Results</h3>
            {result ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Total Pieces</span><span className="font-medium">{result.total_pieces}</span></div>
                <div className="border-t border-border pt-2 mt-2" />
                <div className="flex justify-between"><span className="text-muted-foreground">Material</span><span>{formatCurrency(result.material_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Labor</span><span>{formatCurrency(result.labor_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Design</span><span>{formatCurrency(result.design_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Machine</span><span>{formatCurrency(result.machine_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Electricity</span><span>{formatCurrency(result.electricity_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Packaging</span><span>{formatCurrency(result.packaging_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Failure Buffer</span><span>{formatCurrency(result.failure_buffer)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Overhead</span><span>{formatCurrency(result.overhead)}</span></div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between font-bold">
                  <span>Total Cost</span><span>{formatCurrency(result.total_cost)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Cost/piece</span><span>{formatCurrency(result.cost_per_piece)}</span>
                </div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between">
                  <span className="text-muted-foreground">Price/piece</span><span className="font-bold">{formatCurrency(result.price_per_piece)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Revenue</span><span className="font-bold">{formatCurrency(result.total_revenue)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Platform fees</span><span>-{formatCurrency(result.platform_fees)}</span>
                </div>
                <div className="border-t-2 border-border pt-2 mt-2 flex justify-between font-bold text-lg">
                  <span>Net Profit</span>
                  <span className={result.net_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-destructive'}>
                    {formatCurrency(result.net_profit)}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground text-right">
                  {formatCurrency(result.profit_per_piece)} per piece
                </div>
                <button
                  onClick={saveAsJob}
                  className="w-full mt-4 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 transition-opacity cursor-pointer"
                >
                  Save as Job
                </button>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm py-8 text-center">
                Fill in parameters to calculate costs
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
