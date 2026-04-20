import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
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

  const update = (field: string, value: number | string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const saveAsJob = () => {
    const params = new URLSearchParams();
    params.set('from_calc', '1');
    Object.entries(form).forEach(([k, v]) => params.set(k, String(v)));
    navigate(`/jobs/new?${params}`);
    toast.info('Fill in job number and details to save');
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cost Calculator"
        description="Estimate material, labor, and machine costs for a print job before committing to production."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Print Parameters */}
          <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
            <h2 className="text-base font-semibold">Print parameters</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="calc-material">Material</Label>
                <select
                  id="calc-material"
                  value={form.material_id}
                  onChange={(e) => update('material_id', e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Select material…</option>
                  {materials?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.brand}) — ${Number(m.cost_per_g).toFixed(4)}/g
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-qty-per-plate">Qty per plate</Label>
                <Input
                  id="calc-qty-per-plate"
                  type="number"
                  min={1}
                  value={form.qty_per_plate}
                  onChange={(e) => update('qty_per_plate', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-num-plates">Number of plates</Label>
                <Input
                  id="calc-num-plates"
                  type="number"
                  min={1}
                  value={form.num_plates}
                  onChange={(e) => update('num_plates', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-material-per-plate">Material per plate (g)</Label>
                <Input
                  id="calc-material-per-plate"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.material_per_plate_g}
                  onChange={(e) => update('material_per_plate_g', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="calc-print-time">Print time per plate (hrs)</Label>
                <Input
                  id="calc-print-time"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.print_time_per_plate_hrs}
                  onChange={(e) => update('print_time_per_plate_hrs', Number(e.target.value))}
                />
              </div>
            </div>
          </section>

          {/* Labor & Costs */}
          <section className="rounded-md border border-border bg-card p-5 shadow-xs space-y-4">
            <h2 className="text-base font-semibold">Labor &amp; costs</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="calc-labor-mins">Labor time (mins)</Label>
                <Input
                  id="calc-labor-mins"
                  type="number"
                  min={0}
                  value={form.labor_mins}
                  onChange={(e) => update('labor_mins', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-design-hrs">Design time (hrs)</Label>
                <Input
                  id="calc-design-hrs"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.design_time_hrs}
                  onChange={(e) => update('design_time_hrs', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-shipping">Shipping cost ($)</Label>
                <Input
                  id="calc-shipping"
                  type="number"
                  min={0}
                  step="0.01"
                  value={form.shipping_cost}
                  onChange={(e) => update('shipping_cost', Number(e.target.value))}
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="calc-margin">Target margin: {form.target_margin_pct}%</Label>
                <input
                  id="calc-margin"
                  type="range"
                  min={0}
                  max={90}
                  value={form.target_margin_pct}
                  onChange={(e) => update('target_margin_pct', Number(e.target.value))}
                  className="w-full accent-primary"
                />
              </div>
            </div>
          </section>
        </div>

        {/* Results */}
        <div className="lg:col-span-1">
          <section className="sticky top-24 rounded-md border border-border bg-card p-5 shadow-xs space-y-3">
            <h2 className="text-base font-semibold">Results</h2>
            {result ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total pieces</span>
                  <span className="font-medium tabular-nums">{result.total_pieces}</span>
                </div>
                <div className="border-t border-border pt-2" />
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Material</span>
                  <span className="tabular-nums">{formatCurrency(result.material_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Labor</span>
                  <span className="tabular-nums">{formatCurrency(result.labor_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Design</span>
                  <span className="tabular-nums">{formatCurrency(result.design_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Machine</span>
                  <span className="tabular-nums">{formatCurrency(result.machine_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Electricity</span>
                  <span className="tabular-nums">{formatCurrency(result.electricity_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Packaging</span>
                  <span className="tabular-nums">{formatCurrency(result.packaging_cost)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Failure buffer</span>
                  <span className="tabular-nums">{formatCurrency(result.failure_buffer)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Overhead</span>
                  <span className="tabular-nums">{formatCurrency(result.overhead)}</span>
                </div>
                <div className="flex justify-between border-t border-border pt-2 font-semibold">
                  <span>Total cost</span>
                  <span className="tabular-nums">{formatCurrency(result.total_cost)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Cost/piece</span>
                  <span className="tabular-nums">{formatCurrency(result.cost_per_piece)}</span>
                </div>
                <div className="flex justify-between border-t border-border pt-2">
                  <span className="text-muted-foreground">Price/piece</span>
                  <span className="font-semibold tabular-nums">{formatCurrency(result.price_per_piece)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Revenue</span>
                  <span className="font-semibold tabular-nums">{formatCurrency(result.total_revenue)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Platform fees</span>
                  <span className="tabular-nums">-{formatCurrency(result.platform_fees)}</span>
                </div>
                <div className="flex justify-between border-t border-border pt-2 text-base font-semibold">
                  <span>Net profit</span>
                  <span
                    className={
                      result.net_profit >= 0
                        ? 'tabular-nums text-emerald-600 dark:text-emerald-400'
                        : 'tabular-nums text-destructive'
                    }
                  >
                    {formatCurrency(result.net_profit)}
                  </span>
                </div>
                <div className="text-right text-xs text-muted-foreground tabular-nums">
                  {formatCurrency(result.profit_per_piece)} per piece
                </div>
                <Button onClick={saveAsJob} className="mt-2 w-full">
                  Save as job
                </Button>
              </div>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Fill in parameters to calculate costs.
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
