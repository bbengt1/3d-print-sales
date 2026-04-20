import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import type { Customer } from '@/types';

const emptyForm = { name: '', email: '', phone: '', notes: '' };

export default function CustomersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');

  const { data: customers, isLoading } = useQuery<Customer[]>({
    queryKey: ['customers', search],
    queryFn: () => {
      const params = search ? `?search=${encodeURIComponent(search)}` : '';
      return api.get(`/customers${params}`).then((r) => r.data);
    },
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<Customer | null>(null);

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (c: Customer) => {
    setForm({ name: c.name, email: c.email || '', phone: c.phone || '', notes: c.notes || '' });
    setEditing(c.id);
  };
  const close = () => setEditing(null);

  const save = async () => {
    if (!form.name) { toast.error('Name is required'); return; }
    setSaving(true);
    try {
      const payload = { ...form, email: form.email || null, phone: form.phone || null, notes: form.notes || null };
      if (editing === 'new') {
        await api.post('/customers', payload);
        toast.success('Customer created');
      } else {
        await api.put(`/customers/${editing}`, payload);
        toast.success('Customer updated');
      }
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const deleteCustomer = async (c: Customer) => {
    try {
      await api.delete(`/customers/${c.id}`);
      toast.success('Customer deleted');
      queryClient.invalidateQueries({ queryKey: ['customers'] });
    } catch { toast.error('Failed to delete'); }
  };

  const columns: Column<Customer>[] = [
    { key: 'name', header: 'Name', cell: (c) => <span className="font-medium">{c.name}</span> },
    { key: 'email', header: 'Email', colClassName: 'hidden md:table-cell', cell: (c) => c.email || <span className="text-muted-foreground">—</span> },
    { key: 'phone', header: 'Phone', colClassName: 'hidden lg:table-cell', cell: (c) => c.phone || <span className="text-muted-foreground">—</span> },
    { key: 'job_count', header: 'Jobs', numeric: true, cell: (c) => c.job_count },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '80px',
      cell: (c) => (
        <div className="flex items-center justify-end gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => openEdit(c)}
                aria-label={`Edit ${c.name}`}
              >
                <Edit className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Edit</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => setPendingDelete(c)}
                aria-label={`Delete ${c.name}`}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Delete</TooltipContent>
          </Tooltip>
        </div>
      ),
    },
  ];

  const total = customers?.length ?? 0;
  const activeFilters = search ? 1 : 0;
  const clearFilters = () => setSearch('');

  return (
    <div className="space-y-6">
      <PageHeader
        title="Customers"
        description={`${total.toLocaleString()} ${total === 1 ? 'customer' : 'customers'}`}
        actions={
          <Button type="button" onClick={openNew}>
            <Plus className="h-4 w-4" /> Add customer
          </Button>
        }
      />

      <Dialog open={editing !== null} onOpenChange={(open) => !open && close()}>
        <DialogContent size="md">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add customer' : 'Edit customer'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="cust-name" required>Name</Label>
              <Input id="cust-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-email">Email</Label>
              <Input id="cust-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-phone">Phone</Label>
              <Input id="cust-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cust-notes">Notes</Label>
              <Textarea id="cust-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DataTable<Customer>
        data={customers || []}
        columns={columns}
        rowKey={(c) => c.id}
        loading={isLoading}
        emptyState={activeFilters > 0 ? 'No customers match this search.' : 'No customers yet — add your first one to get started.'}
        toolbar={
          <TableToolbar total={total} activeFilters={activeFilters} onClearFilters={clearFilters}>
            <SearchInput value={search} onChange={setSearch} placeholder="Search customers…" />
          </TableToolbar>
        }
      />

      <ConfirmDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        title="Delete customer?"
        description={pendingDelete ? `${pendingDelete.name} will be removed. This cannot be undone.` : undefined}
        confirmLabel="Delete"
        tone="destructive"
        onConfirm={async () => {
          if (pendingDelete) await deleteCustomer(pendingDelete);
        }}
      />
    </div>
  );
}
