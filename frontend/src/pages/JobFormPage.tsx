import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import type { Material, Job, CalculateResponse } from '@/types';

export default function JobFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: materials } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const { data: existingJob } = useQuery<Job>({
    queryKey: ['job', id],
    queryFn: () => api.get(`/jobs/${id}`).then((r) => r.data),
    enabled: isEdit,
  });

  const [form, setForm] = useState({
    job_number: '',
    date: new Date().toISOString().slice(0, 10),
    customer_name: '',
    product_name: '',
    qty_per_plate: 1,
    num_plates: 1,
    material_id: '',
    material_per_plate_g: 0,
    print_time_per_plate_hrs: 0,
    labor_mins: 0,
    design_time_hrs: 0,
    shipping_cost: 0,
    target_margin_pct: 40,
    status: 'completed',
  });

  const [preview, setPreview] = useState<CalculateResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (existingJob) {
      setForm({
        job_number: existingJob.job_number,
        date: existingJob.date,
        customer_name: existingJob.customer_name || '',
        product_name: existingJob.product_name,
        qty_per_plate: existingJob.qty_per_plate,
        num_plates: existingJob.num_plates,
        material_id: existingJob.material_id,
        material_per_plate_g: existingJob.material_per_plate_g,
        print_time_per_plate_hrs: existingJob.print_time_per_plate_hrs,
        labor_mins: existingJob.labor_mins,
        design_time_hrs: existingJob.design_time_hrs || 0,
        shipping_cost: existingJob.shipping_cost,
        target_margin_pct: existingJob.target_margin_pct,
        status: existingJob.status,
      });
    }
  }, [existingJob]);

  // Live cost preview
  useEffect(() => {
    if (!form.material_id || form.material_per_plate_g <= 0 || form.print_time_per_plate_hrs <= 0) {
      setPreview(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const { data } = await api.post('/jobs/calculate', {
          qty_per_plate: form.qty_per_plate,
          num_plates: form.num_plates,
          material_id: form.material_id,
          material_per_plate_g: form.material_per_plate_g,
          print_time_per_plate_hrs: form.print_time_per_plate_hrs,
          labor_mins: form.labor_mins,
          design_time_hrs: form.design_time_hrs,
          shipping_cost: form.shipping_cost,
          target_margin_pct: form.target_margin_pct,
        });
        setPreview(data);
      } catch {
        setPreview(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [form.material_id, form.qty_per_plate, form.num_plates, form.material_per_plate_g, form.print_time_per_plate_hrs, form.labor_mins, form.design_time_hrs, form.shipping_cost, form.target_margin_pct]);

  const update = (field: string, value: string | number) => {
    setForm((f) => ({ ...f, [field]: value }));
    setErrors((e) => ({ ...e, [field]: '' }));
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.job_number) errs.job_number = 'Required';
    if (!form.product_name) errs.product_name = 'Required';
    if (!form.material_id) errs.material_id = 'Select a material';
    if (form.qty_per_plate < 1) errs.qty_per_plate = 'Must be at least 1';
    if (form.num_plates < 1) errs.num_plates = 'Must be at least 1';
    if (form.material_per_plate_g <= 0) errs.material_per_plate_g = 'Must be greater than 0';
    if (form.print_time_per_plate_hrs <= 0) errs.print_time_per_plate_hrs = 'Must be greater than 0';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        customer_name: form.customer_name || null,
        design_time_hrs: form.design_time_hrs || 0,
      };
      if (isEdit) {
        await api.put(`/jobs/${id}`, payload);
        toast.success('Job updated');
      } else {
        await api.post('/jobs', payload);
        toast.success('Job created');
      }
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate('/jobs');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to save job';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const Field = ({ label, field, type = 'text', ...rest }: { label: string; field: string; type?: string; [k: string]: any }) => (
    <div>
      <label className="block text-sm font-medium mb-1.5">{label}</label>
      <input
        type={type}
        value={(form as any)[field]}
        onChange={(e) => update(field, type === 'number' ? Number(e.target.value) : e.target.value)}
        className={`w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring ${errors[field] ? 'border-destructive' : 'border-input'}`}
        {...rest}
      />
      {errors[field] && <p className="text-destructive text-xs mt-1">{errors[field]}</p>}
    </div>
  );

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-3xl font-bold mb-8">{isEdit ? 'Edit Job' : 'New Job'}</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-6">
          {/* Job Info */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Job Info</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Job Number" field="job_number" placeholder="2026.3.4.001" />
              <Field label="Date" field="date" type="date" />
              <Field label="Customer" field="customer_name" placeholder="Optional" />
              <Field label="Product Name" field="product_name" placeholder="Phone Stand" />
              <div>
                <label className="block text-sm font-medium mb-1.5">Status</label>
                <select
                  value={form.status}
                  onChange={(e) => update('status', e.target.value)}
                  className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="draft">Draft</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
            </div>
          </div>

          {/* Print Details */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Print Details</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1.5">Material</label>
                <select
                  value={form.material_id}
                  onChange={(e) => update('material_id', e.target.value)}
                  className={`w-full px-3 py-2 border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring ${errors.material_id ? 'border-destructive' : 'border-input'}`}
                >
                  <option value="">Select material...</option>
                  {materials?.map((m) => (
                    <option key={m.id} value={m.id}>{m.name} ({m.brand}) — ${Number(m.cost_per_g).toFixed(4)}/g</option>
                  ))}
                </select>
                {errors.material_id && <p className="text-destructive text-xs mt-1">{errors.material_id}</p>}
              </div>
              <Field label="Qty per Plate" field="qty_per_plate" type="number" min={1} />
              <Field label="Number of Plates" field="num_plates" type="number" min={1} />
              <Field label="Material per Plate (g)" field="material_per_plate_g" type="number" min={0} step="0.01" />
              <Field label="Print Time per Plate (hrs)" field="print_time_per_plate_hrs" type="number" min={0} step="0.01" />
            </div>
          </div>

          {/* Labor & Costs */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-4">Labor & Additional Costs</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Labor Time (mins)" field="labor_mins" type="number" min={0} />
              <Field label="Design Time (hrs)" field="design_time_hrs" type="number" min={0} step="0.01" />
              <Field label="Shipping Cost ($)" field="shipping_cost" type="number" min={0} step="0.01" />
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

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="bg-primary text-primary-foreground px-6 py-2.5 rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
            >
              {saving ? 'Saving...' : isEdit ? 'Update Job' : 'Create Job'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/jobs')}
              className="px-6 py-2.5 border border-border rounded-lg font-medium hover:bg-accent transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>

        {/* Live Cost Preview */}
        <div className="lg:col-span-1">
          <div className="bg-card border border-border rounded-lg p-6 sticky top-24">
            <h3 className="text-lg font-semibold mb-4">Cost Preview</h3>
            {preview ? (
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Pieces</span><span className="font-medium">{preview.total_pieces}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Material</span><span>{formatCurrency(preview.material_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Labor</span><span>{formatCurrency(preview.labor_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Design</span><span>{formatCurrency(preview.design_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Machine</span><span>{formatCurrency(preview.machine_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Electricity</span><span>{formatCurrency(preview.electricity_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Packaging</span><span>{formatCurrency(preview.packaging_cost)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Failure Buffer</span><span>{formatCurrency(preview.failure_buffer)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Overhead</span><span>{formatCurrency(preview.overhead)}</span></div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between font-bold">
                  <span>Total Cost</span><span>{formatCurrency(preview.total_cost)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Cost/piece</span><span>{formatCurrency(preview.cost_per_piece)}</span>
                </div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between">
                  <span className="text-muted-foreground">Price/piece</span><span className="font-bold">{formatCurrency(preview.price_per_piece)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Revenue</span><span className="font-bold">{formatCurrency(preview.total_revenue)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Platform fees</span><span>-{formatCurrency(preview.platform_fees)}</span>
                </div>
                <div className="border-t-2 border-border pt-2 mt-2 flex justify-between font-bold text-lg">
                  <span>Net Profit</span>
                  <span className={preview.net_profit >= 0 ? 'text-green-600 dark:text-green-400' : 'text-destructive'}>
                    {formatCurrency(preview.net_profit)}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground text-right">
                  {formatCurrency(preview.profit_per_piece)} per piece
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm py-8 text-center">
                Fill in print details to see cost preview
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
