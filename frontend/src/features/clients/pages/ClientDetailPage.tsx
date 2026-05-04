import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Pencil, Save, X, Plus } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { clientsApi } from '../api/clients.api';
import type { Client } from '../types';
import type { Project } from '@/features/projects/types';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { Badge } from '@/shared/ui/Badge';
import { normalizeError } from '@/shared/api/errors';

const editSchema = z.object({
  name: z.string().min(1, 'Required'),
  company_name: z.string().min(1, 'Required'),
  email: z.string().email('Invalid email').or(z.literal('')).optional(),
  phone: z.string().optional(),
  address: z.string().optional(),
});

type EditForm = z.infer<typeof editSchema>;

const statusVariant: Record<string, 'default' | 'warning' | 'success'> = {
  IN_PROGRESS: 'default',
  IN_REVIEW: 'warning',
  COMPLETED: 'success',
};

const statusLabel: Record<string, string> = {
  IN_PROGRESS: 'In Progress',
  IN_REVIEW: 'In Review',
  COMPLETED: 'Completed',
};

export function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const navigate = useNavigate();

  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [submitError, setSubmitError] = useState('');

  // Projects
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [projectPage, setProjectPage] = useState(1);
  const [projectTotalPages, setProjectTotalPages] = useState(1);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditForm>({ resolver: zodResolver(editSchema) });

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    clientsApi
      .get(clientId)
      .then(({ data }) => {
        setClient(data);
        reset({
          name: data.name,
          company_name: data.company_name,
          email: data.email || '',
          phone: data.phone || '',
          address: data.address || '',
        });
      })
      .catch(() => navigate('/clients'))
      .finally(() => setLoading(false));
  }, [clientId, navigate, reset]);

  useEffect(() => {
    if (!clientId) return;
    setProjectsLoading(true);
    clientsApi
      .listProjects(clientId, { page: projectPage, limit: 10 })
      .then(({ data }) => {
        setProjects(data.data);
        setProjectTotalPages(data.pagination.total_pages);
      })
      .catch(() => {})
      .finally(() => setProjectsLoading(false));
  }, [clientId, projectPage]);

  const onSave = async (formData: EditForm) => {
    if (!clientId) return;
    setSubmitError('');
    try {
      const { data } = await clientsApi.update(clientId, {
        name: formData.name,
        company_name: formData.company_name,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
      });
      setClient(data);
      setEditing(false);
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading client...
      </div>
    );
  }

  if (!client) return null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/clients')}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
          >
            <ArrowLeft className="h-4 w-4 text-gray-500" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{client.company_name}</h1>
            <p className="text-sm text-gray-500">{client.name}</p>
          </div>
        </div>
        {!editing && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => navigate(`/projects/new?clientId=${client.id}`)}
            >
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Button>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </div>
        )}
      </div>

      {/* Edit Mode */}
      {editing && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Edit Client</h2>
            <button onClick={() => { setEditing(false); setSubmitError(''); }}>
              <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
            </button>
          </div>
          <form onSubmit={handleSubmit(onSave)} className="space-y-4">
            <Input label="Contact Name" error={errors.name?.message} {...register('name')} />
            <Input label="Company Name" error={errors.company_name?.message} {...register('company_name')} />
            <Input label="Email" type="email" error={errors.email?.message} {...register('email')} />
            <Input label="Phone" error={errors.phone?.message} {...register('phone')} />
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Address</label>
              <textarea
                rows={2}
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                {...register('address')}
              />
            </div>
            {submitError && <p className="text-sm text-red-600">{submitError}</p>}
            <div className="flex gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => { setEditing(false); setSubmitError(''); }}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isSubmitting}>
                <Save className="mr-2 h-4 w-4" />
                Save Changes
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Client Info (read mode) */}
      {!editing && (
        <Card>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Client Information</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoItem label="Company Name" value={client.company_name} />
            <InfoItem label="Contact Name" value={client.name} />
            <InfoItem label="Email" value={client.email || '\u2014'} />
            <InfoItem label="Phone" value={client.phone || '\u2014'} />
            <div className="sm:col-span-2">
              <InfoItem label="Address" value={client.address || '\u2014'} />
            </div>
            <InfoItem
              label="Created"
              value={client.created_at ? new Date(client.created_at).toLocaleDateString() : '\u2014'}
            />
          </div>
        </Card>
      )}

      {/* Projects */}
      <Card className="overflow-hidden !p-0">
        <div className="border-b px-4 py-3">
          <h2 className="text-lg font-semibold text-gray-900">Projects</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
              <tr>
                <th className="px-4 py-3">Project Name</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {projectsLoading ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                    Loading...
                  </td>
                </tr>
              ) : projects.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                    No projects for this client
                  </td>
                </tr>
              ) : (
                projects.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/projects/${p.id}/setup`)}
                    className="cursor-pointer hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-gray-900">{p.project_name}</td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant[p.status] || 'default'}>
                        {statusLabel[p.status] || p.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {p.created_at ? new Date(p.created_at).toLocaleDateString() : '\u2014'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {projectTotalPages > 1 && (
          <div className="flex items-center justify-between border-t px-4 py-3">
            <Button
              variant="outline"
              size="sm"
              disabled={projectPage <= 1}
              onClick={() => setProjectPage((p) => p - 1)}
            >
              Previous
            </Button>
            <span className="text-sm text-gray-500">
              Page {projectPage} of {projectTotalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={projectPage >= projectTotalPages}
              onClick={() => setProjectPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase text-gray-400">{label}</p>
      <p className="mt-1 text-sm text-gray-900">{value}</p>
    </div>
  );
}
