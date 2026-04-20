import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import PageHeader from '@/components/layout/PageHeader';
import { formatCurrency } from '@/lib/utils';
import type { Material, Job, CalculateResponse, PaginatedProducts, PaginatedPrinters, Product } from '@/types';

interface FieldProps {
  label: string;
  field: string;
  type?: string;
  value: string | number;
  error?: string;
  onChange: (field: string, value: string | number) => void;
  [k: string]: any;
}

function Field({ label, field, type = 'text', value, error, onChange, ...rest }: FieldProps) {
  const id = `job-${field}`;
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(field, type === 'number' ? Number(e.target.value) : e.target.value)}
        invalid={Boolean(error)}
        {...rest}
      />
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}

export default function JobFormPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const emptyProductForm = {
    name: '',
    description: '',
    material_id: '',
    unit_cost: 0,
    unit_price: 0,
    reorder_point: 5,
    upc: '',
  };

  const { data: materials } = useQuery<Material[]>({
    queryKey: ['materials', 'active'],
    queryFn: () => api.get('/materials?active=true').then((r) => r.data),
  });

  const { data: productsData } = useQuery<PaginatedProducts>({
    queryKey: ['products', 'active'],
    queryFn: () => api.get('/products?is_active=true&limit=100').then((r) => r.data),
  });

  const { data: printersData } = useQuery<PaginatedPrinters>({
    queryKey: ['printers', 'active'],
    queryFn: () => api.get('/printers?is_active=true&limit=100').then((r) => r.data),
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
    product_id: '',
    printer_id: '',
    status: 'completed',
  });

  const [preview, setPreview] = useState<CalculateResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [jobNumberTouched, setJobNumberTouched] = useState(false);
  const [showCreateProduct, setShowCreateProduct] = useState(false);
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [productForm, setProductForm] = useState(emptyProductForm);
  const [productErrors, setProductErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (existingJob) {
      setJobNumberTouched(true);
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
        product_id: existingJob.product_id || '',
        printer_id: existingJob.printer_id || '',
        status: existingJob.status,
      });
    }
  }, [existingJob]);

  useEffect(() => {
    if (isEdit || jobNumberTouched || !form.date) return;

    const timer = setTimeout(async () => {
      try {
        const { data } = await api.get('/jobs/next-number', { params: { date: form.date } });
        setForm((current) => {
          if (current.job_number && jobNumberTouched) return current;
          return { ...current, job_number: data.job_number };
        });
      } catch {
        // ignore preview fetch failures; backend still generates on create
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [isEdit, jobNumberTouched, form.date]);

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
    if (field === 'job_number') setJobNumberTouched(true);
    setErrors((e) => ({ ...e, [field]: '' }));
  };

  const openCreateProduct = () => {
    setProductForm({
      ...emptyProductForm,
      name: String(form.product_name || ''),
      material_id: String(form.material_id || ''),
      unit_cost: Number(preview?.cost_per_piece || 0),
      unit_price: Number(preview?.price_per_piece || 0),
    });
    setProductErrors({});
    setShowCreateProduct(true);
  };

  const updateProductForm = (field: string, value: string | number) => {
    setProductForm((f) => ({ ...f, [field]: value }));
    setProductErrors((e) => ({ ...e, [field]: '' }));
  };

  const validateProductForm = () => {
    const errs: Record<string, string> = {};
    if (!String(productForm.name).trim()) errs.name = 'Name is required';
    if (!productForm.material_id) errs.material_id = 'Select a material';
    setProductErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleCreateProduct = async () => {
    if (!validateProductForm()) return;
    setCreatingProduct(true);
    try {
      const payload = {
        name: String(productForm.name).trim(),
        description: String(productForm.description || '') || null,
        material_id: productForm.material_id,
        unit_cost: Number(productForm.unit_cost || 0),
        unit_price: Number(productForm.unit_price || 0),
        reorder_point: Number(productForm.reorder_point || 0),
        upc: String(productForm.upc || '') || null,
      };
      const { data } = await api.post<Product>('/products', payload);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setForm((f) => ({
        ...f,
        product_id: data.id,
        product_name: f.product_name || data.name,
      }));
      setShowCreateProduct(false);
      toast.success('Product created and linked to job');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to create product');
    } finally {
      setCreatingProduct(false);
    }
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (isEdit && !form.job_number) errs.job_number = 'Required';
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
        product_id: form.product_id || null,
        printer_id: form.printer_id || null,
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

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <PageHeader
        title={isEdit ? 'Edit Job' : 'New Job'}
        description="Configure materials, labor, and pricing. Live cost preview updates as you type."
      />

      <Dialog open={showCreateProduct} onOpenChange={(open) => !open && setShowCreateProduct(false)}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>Create and link product</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="create-product-name" required>Name</Label>
              <Input
                id="create-product-name"
                value={productForm.name}
                onChange={(e) => updateProductForm('name', e.target.value)}
                error={productErrors.name}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-product-description">Description</Label>
              <Input
                id="create-product-description"
                value={productForm.description}
                onChange={(e) => updateProductForm('description', e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="create-product-material" required>Material</Label>
              <select
                id="create-product-material"
                value={productForm.material_id}
                onChange={(e) => updateProductForm('material_id', e.target.value)}
                className={`flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${productErrors.material_id ? 'border-destructive' : 'border-input'}`}
              >
                <option value="">Select material...</option>
                {materials?.map((m) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.brand})</option>
                ))}
              </select>
              {productErrors.material_id && <p className="text-destructive text-xs">{productErrors.material_id}</p>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="create-product-unit-cost">Unit Cost ($)</Label>
                <Input id="create-product-unit-cost" type="number" min="0" step="0.01" value={productForm.unit_cost} onChange={(e) => updateProductForm('unit_cost', Number(e.target.value))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="create-product-unit-price">Unit Price ($)</Label>
                <Input id="create-product-unit-price" type="number" min="0" step="0.01" value={productForm.unit_price} onChange={(e) => updateProductForm('unit_price', Number(e.target.value))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="create-product-reorder">Reorder Point</Label>
                <Input id="create-product-reorder" type="number" min="0" value={productForm.reorder_point} onChange={(e) => updateProductForm('reorder_point', Number(e.target.value))} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="create-product-upc">UPC/EAN</Label>
                <Input id="create-product-upc" value={productForm.upc} onChange={(e) => updateProductForm('upc', e.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateProduct(false)}>Cancel</Button>
            <Button onClick={handleCreateProduct} disabled={creatingProduct}>
              {creatingProduct ? 'Creating…' : 'Create & link'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-6">
          {/* Job Info */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-semibold mb-4">Job Info</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Field label="Job Number" field="job_number" value={form.job_number} error={errors.job_number} onChange={update} placeholder="2026.03.24.001" />
                {!isEdit && (
                  <p className="text-xs text-muted-foreground mt-1">
                    {jobNumberTouched ? 'Manual override enabled' : 'Auto-generated from selected date'}
                  </p>
                )}
              </div>
              <Field label="Date" field="date" type="date" value={form.date} error={errors.date} onChange={update} />
              <Field label="Customer" field="customer_name" value={form.customer_name} error={errors.customer_name} onChange={update} placeholder="Optional" />
              <Field label="Product Name" field="product_name" value={form.product_name} error={errors.product_name} onChange={update} placeholder="Phone Stand" />
              <div className="space-y-1.5">
                <Label htmlFor="job-status">Status</Label>
                <select
                  id="job-status"
                  value={form.status}
                  onChange={(e) => update('status', e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="draft">Draft</option>
                  <option value="in_progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="job-printer">Assign Printer (optional)</Label>
                <select
                  id="job-printer"
                  value={form.printer_id}
                  onChange={(e) => update('printer_id', e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">Unassigned</option>
                  {printersData?.items?.map((printer) => (
                    <option key={printer.id} value={printer.id}>
                      {printer.name} ({printer.status}){printer.location ? ` — ${printer.location}` : ''}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">Optional printer assignment for the physical machine running this job.</p>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="job-product">Link to Product (optional)</Label>
                  <button
                    type="button"
                    onClick={openCreateProduct}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <Plus className="w-3.5 h-3.5" /> Create product
                  </button>
                </div>
                <select
                  id="job-product"
                  value={form.product_id}
                  onChange={(e) => update('product_id', e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  <option value="">None</option>
                  {productsData?.items?.map((p) => (
                    <option key={p.id} value={p.id}>{p.name} ({p.sku})</option>
                  ))}
                </select>
                {form.product_id && form.status === 'completed' && (
                  <p className="text-xs text-muted-foreground">Inventory will be auto-updated when job is completed</p>
                )}
              </div>
            </div>
          </div>

          {/* Print Details */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-semibold mb-4">Print Details</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="job-material">Material</Label>
                <select
                  id="job-material"
                  value={form.material_id}
                  onChange={(e) => update('material_id', e.target.value)}
                  className={`flex h-9 w-full rounded-md border bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring ${errors.material_id ? 'border-destructive' : 'border-input'}`}
                >
                  <option value="">Select material...</option>
                  {materials?.map((m) => (
                    <option key={m.id} value={m.id}>{m.name} ({m.brand}) — ${Number(m.cost_per_g).toFixed(4)}/g</option>
                  ))}
                </select>
                {errors.material_id && <p className="text-destructive text-xs">{errors.material_id}</p>}
              </div>
              <Field label="Qty per Plate" field="qty_per_plate" type="number" value={form.qty_per_plate} error={errors.qty_per_plate} onChange={update} min={1} />
              <Field label="Number of Plates" field="num_plates" type="number" value={form.num_plates} error={errors.num_plates} onChange={update} min={1} />
              <Field label="Material per Plate (g)" field="material_per_plate_g" type="number" value={form.material_per_plate_g} error={errors.material_per_plate_g} onChange={update} min={0} step="0.01" />
              <Field label="Print Time per Plate (hrs)" field="print_time_per_plate_hrs" type="number" value={form.print_time_per_plate_hrs} error={errors.print_time_per_plate_hrs} onChange={update} min={0} step="0.01" />
            </div>
          </div>

          {/* Labor & Costs */}
          <div className="bg-card border border-border rounded-lg p-6">
            <h3 className="text-base font-semibold mb-4">Labor & Additional Costs</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Labor Time (mins)" field="labor_mins" type="number" value={form.labor_mins} error={errors.labor_mins} onChange={update} min={0} />
              <Field label="Design Time (hrs)" field="design_time_hrs" type="number" value={form.design_time_hrs} error={errors.design_time_hrs} onChange={update} min={0} step="0.01" />
              <Field label="Shipping Cost ($)" field="shipping_cost" type="number" value={form.shipping_cost} error={errors.shipping_cost} onChange={update} min={0} step="0.01" />
              <div className="space-y-1.5">
                <Label htmlFor="job-target-margin">Target Margin: {form.target_margin_pct}%</Label>
                <input
                  id="job-target-margin"
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
            <Button type="submit" disabled={saving} size="lg">
              {saving ? 'Saving...' : isEdit ? 'Update Job' : 'Create Job'}
            </Button>
            <Button type="button" variant="outline" size="lg" onClick={() => navigate('/jobs')}>
              Cancel
            </Button>
          </div>
        </form>

        {/* Live Cost Preview */}
        <div className="lg:col-span-1">
          <div className="bg-card border border-border rounded-lg p-6 sticky top-24">
            <h3 className="text-base font-semibold mb-4">Cost Preview</h3>
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
                <div className="border-t border-border pt-2 mt-2 flex justify-between font-semibold">
                  <span>Total Cost</span><span>{formatCurrency(preview.total_cost)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Cost/piece</span><span>{formatCurrency(preview.cost_per_piece)}</span>
                </div>
                <div className="border-t border-border pt-2 mt-2 flex justify-between">
                  <span className="text-muted-foreground">Price/piece</span><span className="font-semibold">{formatCurrency(preview.price_per_piece)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Revenue</span><span className="font-semibold">{formatCurrency(preview.total_revenue)}</span>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Platform fees</span><span>-{formatCurrency(preview.platform_fees)}</span>
                </div>
                <div className="border-t-2 border-border pt-2 mt-2 flex justify-between font-semibold text-lg">
                  <span>Net Profit</span>
                  <span className={preview.net_profit >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-destructive'}>
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
