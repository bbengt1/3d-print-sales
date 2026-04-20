import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Edit, Plus, UserX, Users } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/api/client';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/Tooltip';
import StatusBadge from '@/components/data/StatusBadge';
import DataTable, { type Column } from '@/components/data/DataTable';

interface UserRecord {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const emptyForm = { email: '', password: '', full_name: '', role: 'user' };

export default function UsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuthStore();

  const { data: users, isLoading } = useQuery<UserRecord[]>({
    queryKey: ['users'],
    queryFn: () => api.get('/auth/users').then((r) => r.data),
  });

  const [editing, setEditing] = useState<string | 'new' | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [pendingDeactivate, setPendingDeactivate] = useState<UserRecord | null>(null);

  const openNew = () => { setForm(emptyForm); setEditing('new'); };
  const openEdit = (u: UserRecord) => {
    setForm({ email: u.email, password: '', full_name: u.full_name, role: u.role });
    setEditing(u.id);
  };
  const close = () => setEditing(null);

  const save = async () => {
    if (!form.email || !form.full_name) { toast.error('Email and name are required'); return; }
    setSaving(true);
    try {
      if (editing === 'new') {
        if (!form.password || form.password.length < 6) {
          toast.error('Password must be at least 6 characters');
          setSaving(false);
          return;
        }
        await api.post('/auth/register', form);
        toast.success('User created');
      } else {
        const payload: Record<string, string | boolean> = { email: form.email, full_name: form.full_name, role: form.role };
        await api.put(`/auth/users/${editing}`, payload);
        toast.success('User updated');
      }
      queryClient.invalidateQueries({ queryKey: ['users'] });
      close();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save');
    } finally { setSaving(false); }
  };

  const deactivate = async (u: UserRecord) => {
    try {
      await api.delete(`/auth/users/${u.id}`);
      toast.success(`${u.full_name} deactivated`);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to deactivate');
    }
  };

  const reactivate = async (u: UserRecord) => {
    try {
      await api.put(`/auth/users/${u.id}`, { is_active: true });
      toast.success(`${u.full_name} reactivated`);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to reactivate');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Users className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-semibold">User Management</h1>
            <p className="text-sm text-muted-foreground">Manage user accounts and roles</p>
          </div>
        </div>
        <Button onClick={openNew}>
          <Plus className="h-4 w-4" /> Add User
        </Button>
      </div>

      <Dialog open={editing !== null} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editing === 'new' ? 'Add user' : 'Edit user'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="user-name">Full name *</Label>
              <Input id="user-name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="user-email">Email *</Label>
              <Input id="user-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            {editing === 'new' && (
              <div className="space-y-1.5">
                <Label htmlFor="user-password">Password *</Label>
                <Input
                  id="user-password"
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  placeholder="Min 6 characters"
                />
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="user-role">Role</Label>
              <select
                id="user-role"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close}>Cancel</Button>
            <Button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <UsersTable
        users={users || []}
        isLoading={isLoading}
        currentUserId={currentUser?.id}
        onEdit={openEdit}
        onDeactivate={setPendingDeactivate}
        onReactivate={reactivate}
      />

      <ConfirmDialog
        open={pendingDeactivate !== null}
        onOpenChange={(open) => !open && setPendingDeactivate(null)}
        title="Deactivate user?"
        description={
          pendingDeactivate
            ? `${pendingDeactivate.full_name} will lose access to the app. You can reactivate them later.`
            : undefined
        }
        confirmLabel="Deactivate"
        tone="destructive"
        onConfirm={async () => {
          if (pendingDeactivate) await deactivate(pendingDeactivate);
        }}
      />
    </div>
  );
}

interface UsersTableProps {
  users: UserRecord[];
  isLoading: boolean;
  currentUserId?: string;
  onEdit: (u: UserRecord) => void;
  onDeactivate: (u: UserRecord) => void;
  onReactivate: (u: UserRecord) => void;
}

function UsersTable({ users, isLoading, currentUserId, onEdit, onDeactivate, onReactivate }: UsersTableProps) {
  const columns: Column<UserRecord>[] = [
    {
      key: 'full_name',
      header: 'Name',
      cell: (u) => (
        <div className="font-medium">
          {u.full_name}
          {u.id === currentUserId && (
            <span className="ml-2 text-xs text-muted-foreground">(you)</span>
          )}
        </div>
      ),
    },
    {
      key: 'email',
      header: 'Email',
      cell: (u) => <span className="text-muted-foreground">{u.email}</span>,
    },
    {
      key: 'role',
      header: 'Role',
      cell: (u) => <StatusBadge tone={u.role === 'admin' ? 'info' : 'neutral'}>{u.role}</StatusBadge>,
    },
    {
      key: 'status',
      header: 'Status',
      cell: (u) => (
        <StatusBadge tone={u.is_active ? 'success' : 'destructive'}>
          {u.is_active ? 'Active' : 'Inactive'}
        </StatusBadge>
      ),
    },
    {
      key: 'created_at',
      header: 'Created',
      cell: (u) => (
        <span className="text-xs text-muted-foreground">
          {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: <span className="sr-only">Actions</span>,
      width: '96px',
      cell: (u) => (
        <div className="flex gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => onEdit(u)}
                aria-label={`Edit ${u.full_name}`}
              >
                <Edit className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Edit</TooltipContent>
          </Tooltip>
          {u.id !== currentUserId && (
            u.is_active ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onDeactivate(u)}
                    aria-label={`Deactivate ${u.full_name}`}
                  >
                    <UserX className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Deactivate</TooltipContent>
              </Tooltip>
            ) : (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onReactivate(u)}
                    aria-label={`Reactivate ${u.full_name}`}
                  >
                    <Users className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Reactivate</TooltipContent>
              </Tooltip>
            )
          )}
        </div>
      ),
    },
  ];

  return (
    <DataTable<UserRecord>
      data={users}
      columns={columns}
      rowKey={(u) => u.id}
      loading={isLoading}
      emptyState="No users yet."
    />
  );
}
