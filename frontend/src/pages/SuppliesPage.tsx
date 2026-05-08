import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, ArchiveRestore, Edit, Plus } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { formatCurrency } from '@/lib/utils';
import { getApiErrorMessage } from '@/lib/apiError';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import StatusBadge from '@/components/data/StatusBadge';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import { Button } from '@/components/ui/Button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Textarea } from '@/components/ui/Textarea';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import type { Supply } from '@/types';

const emptyForm = {
  name: '',
  sku: '',
  category: '',
  unit: 'each',
  unit_cost: 0,
  quantity_on_hand: 0,
  reorder_point: 0,
  supplier: '',
  supplier_url: '',
  notes: '',
};

export default function SuppliesPage() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [active, setActive] = useState('');

  const { data: supplies = [], isLoading } = useQuery<Supply[]>({
    queryKey: ['supplies', search, category, active],
    queryFn: () =>
      api
        .get('/supplies', {
          params: {
            limit: 200,
            ...(search ? { search } : {}),
            ...(category ? { category } : {}),
            ...(active ? { active: active === 'active' } : {}),
          },
        })
        .then((r) => r.data),
  });

  const categories = Array.from(new Set(supplies.map((supply) => supply.category).filter(Boolean))).sort();

  const openNew = () => {
    setForm(emptyForm);
    setFormErrors({});
    setEditing('new');
  };

  const openEdit = (supply: Supply) => {
    setForm({
      name: supply.name,
      sku: supply.sku || '',
      category: supply.category || '',
      unit: supply.unit,
      unit_cost: Number(supply.unit_cost),
      quantity_on_hand: Number(supply.quantity_on_hand),
      reorder_point: Number(supply.reorder_point),
      supplier: supply.supplier || '',
      supplier_url: supply.supplier_url || '',
      notes: supply.notes || '',
    });
    setFormErrors({});
    setEditing(supply.id);
  };

  const close = () => setEditing(null);

  const validate = () => {
    const errs: Record<string, string> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (!form.unit.trim()) errs.unit = 'Unit is required';
    if (Number(form.unit_cost) < 0) errs.unit_cost = 'Unit cost cannot be negative';
    if (Number(form.quantity_on_hand) < 0) errs.quantity_on_hand = 'Quantity cannot be negative';
    if (Number(form.reorder_point) < 0) errs.reorder_point = 'Reorder point cannot be negative';
    setFormErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const save = async () => {
    if (!validate()) return;
    setSaving(true);
    const payload = {
      ...form,
      name: form.name.trim(),
      sku: form.sku.trim() || null,
      category: form.category.trim() || null,
      unit: form.unit.trim(),
      unit_cost: Number(form.unit_cost || 0),
      quantity_on_hand: Number(form.quantity_on_hand || 0),
      reorder_point: Number(form.reorder_point || 0),
      supplier: form.supplier.trim() || null,
      supplier_url: form.supplier_url.trim() || null,
      notes: form.notes.trim() || null,
    };
    try {
      if (editing === 'new') {
        await api.post('/supplies', payload);
        toast.success('Supply created');
      } else {
        await api.put(`/supplies/${editing}`, payload);
        toast.success('Supply updated');
      }
      queryClient.invalidateQueries({ queryKey: ['supplies'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
      queryClient.invalidateQueries({ queryKey: ['product-bom'] });
      close();
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to save supply'));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (supply: Supply) => {
    try {
      if (supply.active) {
        await api.delete(`/supplies/${supply.id}`);
        toast.success(`${supply.name} archived`);
      } else {
        await api.put(`/supplies/${supply.id}`, { active: true });
        toast.success(`${supply.name} restored`);
      }
      queryClient.invalidateQueries({ queryKey: ['supplies'] });
      queryClient.invalidateQueries({ queryKey: ['inventory-alerts'] });
    } catch (err) {
      toast.error(getApiErrorMessage(err, 'Failed to update supply'));
    }
  };

  const columns: Column<Supply>[] = [
    { key: 'name', header: 'Name', cell: (s) => <span className="font-medium">{s.name}</span> },
    { key: 'sku', header: 'SKU', cell: (s) => <span className="font-mono text-xs">{s.sku || '-'}</span> },
    { key: 'category', header: 'Category', cell: (s) => s.category || '-' },
    { key: 'unit_cost', header: 'Cost', numeric: true, cell: (s) => formatCurrency(s.unit_cost) },
    {
      key: 'quantity_on_hand',
      header: 'On hand',
      numeric: true,
      cell: (s) => (
        <span className={Number(s.quantity_on_hand) <= Number(s.reorder_point) ? 'font-medium text-warning' : ''}>
          {Number(s.quantity_on_hand).toLocaleString()} {s.unit}
        </span>
      ),
    },
    {
      key: 'reorder_point',
      header: 'Reorder',
      numeric: true,
      colClassName: 'hidden md:table-cell',
      cell: (s) => Number(s.reorder_point).toLocaleString(),
    },
    {
      key: 'status',
      header: 'Status',
      cell: (s) => (
        <button type="button" onClick={() => toggleActive(s)}>
          <StatusBadge tone={s.active ? 'success' : 'warning'}>{s.active ? 'Active' : 'Archived'}</StatusBadge>
        </button>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '88px',
      cell: (s) => (
        <div className="flex justify-end gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(s)}>
                <Edit className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Edit</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => toggleActive(s)}>
                {s.active ? <Archive className="h-4 w-4" /> : <ArchiveRestore className="h-4 w-4" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{s.active ? 'Archive' : 'Restore'}</TooltipContent>
          </Tooltip>
        </div>
      ),
    },
  ];

  const total = supplies.length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Supplies"
        description={`${total.toLocaleString()} ${total === 1 ? 'supply item' : 'supply items'}`}
        actions={
          <Button type="button" onClick={openNew}>
            <Plus className="h-4 w-4" /> Add supply
          </Button>
        }
      />

      <DataTable<Supply>
        data={supplies}
        columns={columns}
        rowKey={(s) => s.id}
        loading={isLoading}
        emptyState="No supplies yet. Add reusable BOM parts like magnets, screws, LED strips, or inserts."
        toolbar={
          <TableToolbar
            total={total}
            activeFilters={[search, category, active].filter(Boolean).length}
            onClearFilters={() => {
              setSearch('');
              setCategory('');
              setActive('');
            }}
          >
            <SearchInput value={search} onChange={setSearch} placeholder="Search supplies..." />
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">All categories</option>
              {categories.map((value) => (
                <option key={value} value={value || ''}>{value}</option>
              ))}
            </select>
            <select
              value={active}
              onChange={(event) => setActive(event.target.value)}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </TableToolbar>
        }
      />

      <Dialog open={editing !== null} onOpenChange={(open) => !open && close()}>
        <DialogContent size="lg">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add supply' : 'Edit supply'}</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="supply-name" required>Name</Label>
              <Input
                id="supply-name"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                error={formErrors.name}
                placeholder="10x3mm magnet, M3 screw, LED strip..."
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-sku">SKU / part number</Label>
              <Input
                id="supply-sku"
                value={form.sku}
                onChange={(event) => setForm((current) => ({ ...current, sku: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-category">Category</Label>
              <Input
                id="supply-category"
                value={form.category}
                onChange={(event) => setForm((current) => ({ ...current, category: event.target.value }))}
                placeholder="hardware, electronics, adhesive"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-unit" required>Unit</Label>
              <Input
                id="supply-unit"
                value={form.unit}
                onChange={(event) => setForm((current) => ({ ...current, unit: event.target.value }))}
                error={formErrors.unit}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-cost">Unit cost</Label>
              <Input
                id="supply-cost"
                type="number"
                min="0"
                step="0.0001"
                value={form.unit_cost}
                onChange={(event) => setForm((current) => ({ ...current, unit_cost: Number(event.target.value) }))}
                error={formErrors.unit_cost}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-stock">Quantity on hand</Label>
              <Input
                id="supply-stock"
                type="number"
                min="0"
                step="0.0001"
                value={form.quantity_on_hand}
                onChange={(event) =>
                  setForm((current) => ({ ...current, quantity_on_hand: Number(event.target.value) }))
                }
                error={formErrors.quantity_on_hand}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-reorder">Reorder point</Label>
              <Input
                id="supply-reorder"
                type="number"
                min="0"
                step="0.0001"
                value={form.reorder_point}
                onChange={(event) => setForm((current) => ({ ...current, reorder_point: Number(event.target.value) }))}
                error={formErrors.reorder_point}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-supplier">Supplier</Label>
              <Input
                id="supply-supplier"
                value={form.supplier}
                onChange={(event) => setForm((current) => ({ ...current, supplier: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="supply-url">Supplier URL</Label>
              <Input
                id="supply-url"
                value={form.supplier_url}
                onChange={(event) => setForm((current) => ({ ...current, supplier_url: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5 md:col-span-2">
              <Label htmlFor="supply-notes">Notes</Label>
              <Textarea
                id="supply-notes"
                value={form.notes}
                onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save supply'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
