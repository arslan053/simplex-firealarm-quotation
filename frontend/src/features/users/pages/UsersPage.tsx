import { useEffect, useState } from 'react';
import { UserPlus, Users, X, Shield } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { usersApi } from '../api/users.api';
import type { TenantUser } from '../types';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { useTenant } from '@/features/tenants/hooks/useTenant';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { Badge } from '@/shared/ui/Badge';
import { normalizeError } from '@/shared/api/errors';

const inviteSchema = z.object({
  email: z.string().email('Valid email is required'),
  role: z.enum(['admin', 'employee']),
});

type InviteForm = z.infer<typeof inviteSchema>;

export function UsersPage() {
  const { user: currentUser } = useAuth();
  const { tenant } = useTenant();
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteForm>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: 'employee' },
  });

  const fetchUsers = async () => {
    try {
      const { data } = await usersApi.list();
      setUsers(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const onInvite = async (formData: InviteForm) => {
    setSubmitError('');
    setSuccessMsg('');
    try {
      await usersApi.invite(formData);
      setSuccessMsg(`Invitation sent to ${formData.email}! They will receive their login credentials via email.`);
      reset();
      setShowForm(false);
      fetchUsers();
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  const handleRoleChange = async (userId: string, newRole: 'admin' | 'employee') => {
    setActionLoading(userId);
    try {
      await usersApi.updateRole(userId, { role: newRole });
      setSuccessMsg(`Role updated to ${newRole}.`);
      fetchUsers();
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeactivate = async (userId: string, email: string) => {
    if (!window.confirm(`Are you sure you want to deactivate ${email}? They will no longer be able to log in.`)) {
      return;
    }
    setActionLoading(userId);
    try {
      await usersApi.deactivate(userId);
      setSuccessMsg(`${email} has been deactivated.`);
      fetchUsers();
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    } finally {
      setActionLoading(null);
    }
  };

  const adminCount = users.filter((u) => u.role === 'admin').length;
  const employeeCount = users.filter((u) => u.role === 'employee').length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Team Members</h1>
          <p className="text-sm text-gray-500">
            Manage users for {tenant?.name || 'your company'}
          </p>
        </div>
        <Button onClick={() => { setShowForm(true); setSuccessMsg(''); setSubmitError(''); }}>
          <UserPlus className="mr-2 h-4 w-4" />
          Invite User
        </Button>
      </div>

      {successMsg && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          {successMsg}
        </div>
      )}
      {submitError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {submitError}
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
              <Users className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Members</p>
              <p className="text-xl font-semibold text-gray-900">{total}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
              <Shield className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Admins</p>
              <p className="text-xl font-semibold text-gray-900">{adminCount}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
              <Users className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Employees</p>
              <p className="text-xl font-semibold text-gray-900">{employeeCount}</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Invite User Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Invite New User</h2>
              <button onClick={() => { setShowForm(false); setSubmitError(''); reset(); }}>
                <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            <form onSubmit={handleSubmit(onInvite)} className="space-y-4">
              <Input
                label="Email Address"
                type="email"
                placeholder="user@company.com"
                error={errors.email?.message}
                {...register('email')}
              />

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Role</label>
                <select
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  {...register('role')}
                >
                  <option value="employee">Employee</option>
                  <option value="admin">Admin</option>
                </select>
                {errors.role && <p className="mt-1 text-sm text-red-600">{errors.role.message}</p>}
                <p className="mt-1 text-xs text-gray-500">
                  Admins can manage team members and have full access. Employees have standard access.
                </p>
              </div>

              {submitError && showForm && (
                <p className="text-sm text-red-600">{submitError}</p>
              )}

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1"
                  onClick={() => { setShowForm(false); setSubmitError(''); reset(); }}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" isLoading={isSubmitting}>
                  Send Invitation
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Users Table */}
      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="py-12 text-center text-gray-500">Loading team members...</div>
        ) : users.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            No team members yet. Invite your first user above.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-6 py-3 font-medium text-gray-500">Email</th>
                <th className="px-6 py-3 font-medium text-gray-500">Role</th>
                <th className="px-6 py-3 font-medium text-gray-500">Status</th>
                <th className="px-6 py-3 font-medium text-gray-500">Joined</th>
                <th className="px-6 py-3 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                const isLoading = actionLoading === u.id;
                return (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 font-medium text-gray-900">
                      {u.email}
                      {isSelf && <span className="ml-2 text-xs text-gray-400">(you)</span>}
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={u.role === 'admin' ? 'warning' : 'default'}>
                        {u.role}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant={u.is_active ? 'success' : 'danger'}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-gray-500">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      {isSelf ? (
                        <span className="text-xs text-gray-400">—</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <button
                            disabled={isLoading}
                            onClick={() =>
                              handleRoleChange(u.id, u.role === 'admin' ? 'employee' : 'admin')
                            }
                            className="text-xs text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                            title={u.role === 'admin' ? 'Demote to Employee' : 'Promote to Admin'}
                          >
                            {u.role === 'admin' ? 'Make Employee' : 'Make Admin'}
                          </button>
                          <span className="text-gray-300">|</span>
                          <button
                            disabled={isLoading}
                            onClick={() => handleDeactivate(u.id, u.email)}
                            className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                          >
                            Deactivate
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
