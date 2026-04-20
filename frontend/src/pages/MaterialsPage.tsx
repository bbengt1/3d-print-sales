import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import type { Material } from '@/types';

const emptyForm = { name: '', brand: '', spool_weight_g: 1000, spool_price: 20, net_usable_g: 950, notes: '', spools_in_stock: 0, reorder_point: 2 };

export default function MaterialsPage() {
  const queryClient = useQueryClient();
  const { data: materials, isLoading } = useQuery<Material[]>({
    queryKey: ['materials'],
    queryFn: () => api.get('/materials').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const openNew = () => { setForm(emptyForm); setFormErrors({}); setEditing('new'); };
  const openEdit = (m: Material) => {
    setForm({ name: m.name, brand: m.brand, spool_weight_g: m.spool_weight_g, spool_price: m.spool_price, net_usable_g: m.net_usable_g, notes: m.notes || '', spools_in_stock: m.spools_in_stock, reorder_point: m.reorder_point });
    setFormErrors({});
    setEditing(m.id);
  };
  const close = () => { setEditing(null); };

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (!form.brand.trim()) errs.brand = 'Brand is required';
    if (form.spool_weight_g <= 0) errs.spool_weight_g = 'Must be > 0';
    if (form.spool_price <= 0) errs.spool_price = 'Must be > 0';
    if (form.net_usable_g <= 0) errs.net_usable_g = 'Must be > 0';
    if (form.net_usable_g > form.spool_weight_g) errs.net_usable_g = 'Cannot exceed spool weight';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    try {
      if (editing === 'new') {
        await api.post('/materials', form);
        toast.success('Material created');
      } else {
        await api.put(`/materials/${editing}`, form);
        toast.success('Material updated');
      }
      queryClient.invalidateQueries({ queryKey: ['materials'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const toggleActive = async (m: Material) => {
    try {
      if (m.active) {
        await api.delete(`/materials/${m.id}`);
        toast.success(`${m.name} deactivated`);
      } else {
        await api.put(`/materials/${m.id}`, { active: true });
        toast.success(`${m.name} activated`);
      }
      queryClient.invalidateQueries({ queryKey: ['materials'] });
    } catch { toast.error('Failed to update'); }
  };

  const columns: Column<Material>[] = [
    { key: 'name', header: 'Name', cell: (m) => <span className="font-medium">{m.name}</span> },
    { key: 'brand', header: 'Brand', cell: (m) => m.brand },
    { key: 'spool_weight_g', header: 'Spool (g)', numeric: true, cell: (m) => m.spool_weight_g },
    { key: 'spool_price', header: 'Price', numeric: true, cell: (m) => formatCurrency(m.spool_price) },
    {
      key: 'net_usable_g',
      header: 'Usable (g)',
      numeric: true,
      colClassName: 'hidden lg:table-cell',
      cell: (m) => m.net_usable_g,
    },
    {
      key: 'cost_per_g',
      header: 'Cost/g',
      numeric: true,
      cell: (m) => `$${Number(m.cost_per_g).toFixed(4)}`,
    },
    {
      key: 'spools_in_stock',
      header: 'Spools',
      numeric: true,
      cell: (m) => (
        <span className={m.spools_in_stock <= m.reorder_point ? 'text-amber-600 dark:text-amber-400 font-medium' : ''}>
          {m.spools_in_stock}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (m) => (
        <button
          type="button"
          onClick={() => toggleActive(m)}
          aria-label={m.active ? `Deactivate ${m.name}` : `Activate ${m.name}`}
        >
          <StatusBadge tone={m.active ? 'success' : 'destructive'}>
            {m.active ? 'Active' : 'Inactive'}
          </StatusBadge>
        </button>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '48px',
      cell: (m) => (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => openEdit(m)}
              aria-label={`Edit ${m.name}`}
            >
              <Edit className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Edit</TooltipContent>
        </Tooltip>
      ),
    },
  ];

  const total = materials?.length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Materials"
        description={`${total.toLocaleString()} ${total === 1 ? 'material' : 'materials'}`}
        actions={
          <Button type="button" onClick={openNew}>
            <Plus className="h-4 w-4" /> Add material
          </Button>
        }
      />

      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add material' : 'Edit material'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="mat-name" required>Name</Label>
              <Input
                id="mat-name"
                value={form.name}
                onChange={(e) => {
                  setForm({ ...form, name: e.target.value });
                  setFormErrors({ ...formErrors, name: '' });
                }}
                error={formErrors.name}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="mat-brand" required>Brand</Label>
              <Input
                id="mat-brand"
                value={form.brand}
                onChange={(e) => {
                  setForm({ ...form, brand: e.target.value });
                  setFormErrors({ ...formErrors, brand: '' });
                }}
                error={formErrors.brand}
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="mat-weight" required>Spool (g)</Label>
                <Input
                  id="mat-weight"
                  type="number"
                  value={form.spool_weight_g}
                  onChange={(e) => setForm({ ...form, spool_weight_g: Number(e.target.value) })}
                  error={formErrors.spool_weight_g}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mat-price" required>Price ($)</Label>
                <Input
                  id="mat-price"
                  type="number"
                  step="0.01"
                  value={form.spool_price}
                  onChange={(e) => setForm({ ...form, spool_price: Number(e.target.value) })}
                  error={formErrors.spool_price}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mat-usable" required>Usable (g)</Label>
                <Input
                  id="mat-usable"
                  type="number"
                  value={form.net_usable_g}
                  onChange={(e) => setForm({ ...form, net_usable_g: Number(e.target.value) })}
                  error={formErrors.net_usable_g}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="mat-stock">Spools in stock</Label>
                <Input
                  id="mat-stock"
                  type="number"
                  min="0"
                  value={form.spools_in_stock}
                  onChange={(e) => setForm({ ...form, spools_in_stock: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mat-reorder">Reorder point</Label>
                <Input
                  id="mat-reorder"
                  type="number"
                  min="0"
                  value={form.reorder_point}
                  onChange={(e) => setForm({ ...form, reorder_point: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="mat-notes">Notes</Label>
              <Input id="mat-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            {form.net_usable_g > 0 && (
              <p className="text-sm text-muted-foreground tabular-nums">
                Cost/g: ${(form.spool_price / form.net_usable_g).toFixed(4)}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Desktop table */}
      <div className="hidden md:block">
        <DataTable<Material>
          data={materials || []}
          columns={columns}
          rowKey={(m) => m.id}
          loading={isLoading}
          emptyState="No materials yet — add your first filament to start tracking costs."
          toolbar={<TableToolbar total={total} />}
        />
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-3">
        {materials?.map((m) => (
          <div key={m.id} className="rounded-md border border-border bg-card p-4">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <p className="font-semibold">{m.name}</p>
                <p className="text-xs text-muted-foreground">{m.brand}</p>
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => toggleActive(m)}>
                  <StatusBadge tone={m.active ? 'success' : 'destructive'}>{m.active ? 'Active' : 'Inactive'}</StatusBadge>
                </button>
                <button
                  type="button"
                  onClick={() => openEdit(m)}
                  aria-label={`Edit ${m.name}`}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-muted"
                >
                  <Edit className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div>
                <p className="text-xs text-muted-foreground">Spool</p>
                <p className="tabular-nums">{m.spool_weight_g}g</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Price</p>
                <p className="tabular-nums">{formatCurrency(m.spool_price)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Cost/g</p>
                <p className="tabular-nums">${Number(m.cost_per_g).toFixed(4)}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
