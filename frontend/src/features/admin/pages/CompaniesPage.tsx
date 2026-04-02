import { useEffect, useState } from 'react';
import { Building2, ExternalLink, Plus, Trash2, Users, X } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { adminApi } from '../api/admin.api';
import type { Tenant } from '../types';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { Badge } from '@/shared/ui/Badge';
import { normalizeError } from '@/shared/api/errors';

const createSchema = z.object({
  name: z.string().min(1, 'Company name is required'),
  slug: z
    .string()
    .min(1, 'Domain prefix is required')
    .regex(/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/, 'Only lowercase letters, numbers, and hyphens'),
  admin_email: z.string().email('Valid email is required'),
});

type CreateForm = z.infer<typeof createSchema>;

export function CompaniesPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<Tenant | null>(null);
  const [deleting, setDeleting] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<CreateForm>({ resolver: zodResolver(createSchema) });

  const slugValue = watch('slug');

  const fetchTenants = async () => {
    try {
      const { data } = await adminApi.listTenants();
      setTenants(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load companies', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const onSubmit = async (formData: CreateForm) => {
    setSubmitError('');
    setSuccessMsg('');
    try {
      const { data } = await adminApi.createTenant(formData);
      setSuccessMsg(
        `Company "${data.tenant.name}" created! Credentials sent to ${formData.admin_email}.`
      );
      reset();
      setShowForm(false);
      fetchTenants();
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    try {
      await adminApi.deleteTenant(deleteConfirm.id);
      setSuccessMsg(`Company "${deleteConfirm.name}" deleted.`);
      setDeleteConfirm(null);
      fetchTenants();
    } catch (err) {
      setSubmitError(normalizeError(err).message);
      setDeleteConfirm(null);
    } finally {
      setDeleting(false);
    }
  };

  const totalUsers = tenants.reduce((sum, t) => sum + t.user_count, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Companies</h1>
          <p className="text-sm text-gray-500">Manage all registered companies</p>
        </div>
        <Button onClick={() => { setShowForm(true); setSuccessMsg(''); }}>
          <Plus className="mr-2 h-4 w-4" />
          Create Company
        </Button>
      </div>

      {successMsg && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-700">
          {successMsg}
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-100">
              <Building2 className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Companies</p>
              <p className="text-xl font-semibold text-gray-900">{total}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-100">
              <Users className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Total Users</p>
              <p className="text-xl font-semibold text-gray-900">{totalUsers}</p>
            </div>
          </div>
        </Card>
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100">
              <Building2 className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500">Active Companies</p>
              <p className="text-xl font-semibold text-gray-900">
                {tenants.filter((t) => t.status === 'active').length}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Create Company Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">Create New Company</h2>
              <button onClick={() => { setShowForm(false); setSubmitError(''); reset(); }}>
                <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
              </button>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <Input
                label="Company Name"
                placeholder="Acme Corporation"
                error={errors.name?.message}
                {...register('name')}
              />
              <div>
                <Input
                  label="Domain Prefix (slug)"
                  placeholder="acme"
                  error={errors.slug?.message}
                  {...register('slug')}
                />
                {slugValue && !errors.slug && (
                  <p className="mt-1 text-xs text-gray-500">
                    URL: https://{slugValue}.{window.location.hostname}
                  </p>
                )}
              </div>
              <Input
                label="Admin Email"
                type="email"
                placeholder="admin@company.com"
                error={errors.admin_email?.message}
                {...register('admin_email')}
              />

              {submitError && (
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
                  Create Company
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Companies Table */}
      <Card className="overflow-hidden p-0">
        {loading ? (
          <div className="py-12 text-center text-gray-500">Loading companies...</div>
        ) : tenants.length === 0 ? (
          <div className="py-12 text-center text-gray-500">
            No companies yet. Create your first company above.
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50">
              <tr>
                <th className="px-6 py-3 font-medium text-gray-500">Company</th>
                <th className="px-6 py-3 font-medium text-gray-500">Domain</th>
                <th className="px-6 py-3 font-medium text-gray-500">Users</th>
                <th className="px-6 py-3 font-medium text-gray-500">Status</th>
                <th className="px-6 py-3 font-medium text-gray-500">Created</th>
                <th className="px-6 py-3 font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {tenants.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900">{t.name}</td>
                  <td className="px-6 py-4">
                    <a
                      href={`https://${t.slug}.${window.location.hostname}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-500"
                    >
                      {t.slug}.{window.location.hostname}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </td>
                  <td className="px-6 py-4 text-gray-600">{t.user_count}</td>
                  <td className="px-6 py-4">
                    <Badge variant={t.status === 'active' ? 'success' : 'warning'}>
                      {t.status}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 text-gray-500">
                    {t.created_at ? new Date(t.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td className="px-6 py-4">
                    <button
                      onClick={() => setDeleteConfirm(t)}
                      className="rounded p-1 text-red-400 hover:bg-red-50 hover:text-red-600"
                      title="Delete company"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
            <h2 className="text-lg font-semibold text-gray-900">Delete Company</h2>
            <p className="mt-2 text-sm text-gray-600">
              Are you sure you want to permanently delete <strong>{deleteConfirm.name}</strong>? This
              will remove all users, projects, documents, and data associated with this company. This
              action cannot be undone.
            </p>
            <div className="mt-4 flex gap-3">
              <Button
                type="button"
                variant="outline"
                className="flex-1"
                onClick={() => setDeleteConfirm(null)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                className="flex-1 bg-red-600 hover:bg-red-700"
                isLoading={deleting}
                onClick={handleDelete}
              >
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
