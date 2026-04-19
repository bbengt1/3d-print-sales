import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus, Trash2, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import PageHeader from '@/components/layout/PageHeader';
import DataTable, { type Column } from '@/components/data/DataTable';
import TableToolbar from '@/components/data/TableToolbar';
import SearchInput from '@/components/data/SearchInput';
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
    if (!confirm(`Delete ${c.name}?`)) return;
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
          <button
            type="button"
            onClick={() => openEdit(c)}
            aria-label={`Edit ${c.name}`}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Edit className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => deleteCustomer(c)}
            aria-label={`Delete ${c.name}`}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="h-4 w-4" />
          </button>
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
          <button
            type="button"
            onClick={openNew}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
          >
            <Plus className="h-4 w-4" /> Add customer
          </button>
        }
      />

      {editing !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={(e) => e.target === e.currentTarget && close()}>
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">{editing === 'new' ? 'Add Customer' : 'Edit Customer'}</h3>
              <button onClick={close} className="p-1 hover:bg-accent rounded-md"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div><label className="block text-sm font-medium mb-1">Name *</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div><label className="block text-sm font-medium mb-1">Email</label><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div><label className="block text-sm font-medium mb-1">Phone</label><input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
              <div><label className="block text-sm font-medium mb-1">Notes</label><textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} className="w-full px-3 py-2 border border-input rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={save} disabled={saving} className="flex-1 bg-primary text-primary-foreground py-2 rounded-md font-medium hover:opacity-90 disabled:opacity-50 cursor-pointer">{saving ? 'Saving...' : 'Save'}</button>
              <button onClick={close} className="px-4 py-2 border border-border rounded-md hover:bg-accent cursor-pointer">Cancel</button>
            </div>
          </div>
        </div>
      )}

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
    </div>
  );
}
