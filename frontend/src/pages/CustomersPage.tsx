import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, Edit, Trash2, X, Search } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">Customers</h1>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity cursor-pointer">
          <Plus className="w-4 h-4" /> Add Customer
        </button>
      </div>

      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search customers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-10 pr-3 py-2 border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

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

      {isLoading ? (
        <div className="bg-card border border-border rounded-lg p-4 h-48 animate-pulse" />
      ) : (
        <div className="overflow-x-auto bg-card border border-border rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium text-right">Jobs</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {customers?.map((c) => (
                <tr key={c.id} className="border-b border-border last:border-0 hover:bg-accent/50">
                  <td className="px-4 py-3 font-medium">{c.name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{c.email || '—'}</td>
                  <td className="px-4 py-3 text-muted-foreground">{c.phone || '—'}</td>
                  <td className="px-4 py-3 text-right">{c.job_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button onClick={() => openEdit(c)} className="p-1.5 hover:bg-accent rounded-md text-muted-foreground cursor-pointer" title="Edit"><Edit className="w-4 h-4" /></button>
                      <button onClick={() => deleteCustomer(c)} className="p-1.5 hover:bg-destructive/10 rounded-md text-muted-foreground hover:text-destructive cursor-pointer" title="Delete"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
              {customers?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-muted-foreground">
                    No customers found. Add your first customer to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
