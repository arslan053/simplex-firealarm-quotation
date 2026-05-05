import { useEffect, useState } from 'react';
import { Pencil, Save, X } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { projectsApi } from '../api/projects.api';
import type { Project, ProjectAdmin } from '../types';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { Badge } from '@/shared/ui/Badge';
import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/Card';
import { Input } from '@/shared/ui/Input';
import { normalizeError } from '@/shared/api/errors';

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

const editSchema = z.object({
  project_name: z.string().min(1, 'Required'),
  country: z.string().min(1, 'Required'),
  city: z.string().min(1, 'Required'),
  due_date: z.string().min(1, 'Required'),
});

type EditForm = z.infer<typeof editSchema>;

interface ProjectInfoEditorProps {
  projectId: string;
  onClientClick?: (clientId: string) => void;
  onEditClick?: () => void;
  onCancel?: () => void;
  onProjectUpdated?: (project: Project) => void;
  initialEditing?: boolean;
}

export function ProjectInfoEditor({
  projectId,
  onClientClick,
  onEditClick,
  onCancel,
  onProjectUpdated,
  initialEditing = false,
}: ProjectInfoEditorProps) {
  const { user } = useAuth();
  const [project, setProject] = useState<Project | ProjectAdmin | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(initialEditing);
  const [submitError, setSubmitError] = useState('');
  const [countries, setCountries] = useState<string[]>([]);

  const isAdmin = user?.role === 'admin';
  const isOwner = project && 'owner_user_id' in project && project.owner_user_id === user?.id;
  const isFullView = project && 'country' in project;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditForm>({ resolver: zodResolver(editSchema) });

  useEffect(() => {
    setLoading(true);
    projectsApi
      .get(projectId)
      .then(({ data }) => {
        setProject(data);
        if ('country' in data) {
          reset({
            project_name: data.project_name,
            country: data.country,
            city: data.city,
            due_date: data.due_date,
          });
        }
      })
      .finally(() => setLoading(false));
  }, [projectId, reset]);

  useEffect(() => {
    projectsApi.getCountries().then(({ data }) => setCountries(data)).catch(() => {});
  }, []);

  const onSave = async (formData: EditForm) => {
    setSubmitError('');
    try {
      const { data } = await projectsApi.update(projectId, formData);
      setProject(data);
      onProjectUpdated?.(data);
      setEditing(false);
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-gray-500">
        Loading project...
      </div>
    );
  }

  if (!project) return null;

  const fullProject = project as Project;
  const canEdit = Boolean(isOwner && isFullView);

  const handleCancel = () => {
    setEditing(false);
    setSubmitError('');
    onCancel?.();
  };

  const handleEdit = () => {
    if (onEditClick) {
      onEditClick();
      return;
    }
    setEditing(true);
  };

  return (
    <div className="space-y-6">
      {editing && canEdit && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Edit Project</h2>
            <button onClick={handleCancel}>
              <X className="h-5 w-5 text-gray-400 hover:text-gray-600" />
            </button>
          </div>
          <form onSubmit={handleSubmit(onSave)} className="space-y-4">
            <Input
              label="Project Name"
              error={errors.project_name?.message}
              {...register('project_name')}
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Country</label>
                <select
                  className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  {...register('country')}
                >
                  {countries.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              </div>
              <Input
                label="City"
                error={errors.city?.message}
                {...register('city')}
              />
            </div>
            <Input
              label="Due Date"
              type="date"
              error={errors.due_date?.message}
              {...register('due_date')}
            />

            {submitError && <p className="text-sm text-red-600">{submitError}</p>}

            <div className="flex gap-3 pt-2">
              <Button type="button" variant="outline" onClick={handleCancel}>
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

      {!editing && (
        <Card>
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-lg font-semibold text-gray-900">Project Information</h2>
            {canEdit && (
              <Button variant="outline" size="sm" onClick={handleEdit}>
                <Pencil className="mr-2 h-4 w-4" />
                Edit
              </Button>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoItem label="Project Name" value={project.project_name} />
            {'client_id' in project && fullProject.client_id ? (
              <div>
                <p className="text-xs font-medium uppercase text-gray-400">Client</p>
                <button
                  onClick={() => onClientClick?.(fullProject.client_id!)}
                  className="mt-1 text-sm font-medium text-indigo-600 hover:text-indigo-800"
                >
                  {project.client_name || '-'}
                </button>
              </div>
            ) : (
              <InfoItem label="Client" value={project.client_name || '-'} />
            )}
            <div>
              <p className="text-xs font-medium uppercase text-gray-400">Status</p>
              <div className="mt-1">
                <Badge variant={statusVariant[project.status] || 'default'}>
                  {statusLabel[project.status] || project.status}
                </Badge>
              </div>
            </div>
            <InfoItem
              label="Created"
              value={project.created_at ? new Date(project.created_at).toLocaleDateString() : '-'}
            />
            {isFullView && (
              <>
                <InfoItem label="Country" value={fullProject.country} />
                <InfoItem label="City" value={fullProject.city} />
                <InfoItem label="Due Date" value={fullProject.due_date} />
                <InfoItem label="Panel Family" value={fullProject.panel_family || 'Not assigned'} />
              </>
            )}
            {isAdmin && 'created_by_name' in project && (
              <InfoItem label="Created By" value={(project as ProjectAdmin).created_by_name || '-'} />
            )}
          </div>
        </Card>
      )}
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
