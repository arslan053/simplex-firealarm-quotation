import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Save, Pencil, X, ExternalLink } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

import { projectsApi } from '../api/projects.api';
import { pipelineApi } from '../api/pipeline.api';
import { boqApi } from '../api/boq.api';
import { specApi } from '../api/spec.api';
import type { Project, ProjectAdmin } from '../types';
import { useAuth } from '@/features/auth/hooks/useAuth';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Input } from '@/shared/ui/Input';
import { Badge } from '@/shared/ui/Badge';
import { normalizeError } from '@/shared/api/errors';
import { BoqUploadSection } from '../components/BoqUploadSection';
import { SpecUpload } from '../components/SpecUpload';
import { BoqExtractionSection } from '../components/BoqExtractionSection';
import { SpecAnalysisSection } from '../components/SpecAnalysisSection';
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

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [project, setProject] = useState<Project | ProjectAdmin | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [countries, setCountries] = useState<string[]>([]);

  // Track upload + extraction state
  const [hasBoq, setHasBoq] = useState(false);
  const [hasSpec, setHasSpec] = useState(false);
  const [hasBoqExtracted, setHasBoqExtracted] = useState(false);

  const [boqRefreshKey, setBoqRefreshKey] = useState(0);

  const isAdmin = user?.role === 'admin';
  const isOwner = project && 'owner_user_id' in project && project.owner_user_id === user?.id;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<EditForm>({ resolver: zodResolver(editSchema) });

  useEffect(() => {
    if (!projectId) return;
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
      .catch(() => navigate('/projects'))
      .finally(() => setLoading(false));

    // Check pipeline status — redirect to appropriate page
    pipelineApi.getStatus(projectId).then(({ data }) => {
      if (data.status === 'running') {
        navigate(`/projects/${projectId}/progress`, { replace: true });
      } else if (data.status === 'completed') {
        navigate(`/projects/${projectId}/completed`, { replace: true });
      } else if (data.status === 'failed') {
        navigate(`/projects/${projectId}/progress`, { replace: true });
      }
    }).catch(() => {
      // No pipeline — stay on detail page or redirect to setup
    });

    // Check existing BOQ documents, extracted items, and spec on mount
    boqApi.listDocuments(projectId).then(({ data }) => {
      if (data.length > 0) setHasBoq(true);
    }).catch(() => {});

    boqApi.listItems(projectId, { page: 1, limit: 1 }).then(({ data }) => {
      if (data.pagination.total > 0) setHasBoqExtracted(true);
    }).catch(() => {});

    specApi.checkExisting(projectId).then(({ data }) => {
      if (data.exists) setHasSpec(true);
    }).catch(() => {});
  }, [projectId, navigate, reset]);

  useEffect(() => {
    projectsApi.getCountries().then(({ data }) => setCountries(data)).catch(() => {});
  }, []);

  const onSave = async (formData: EditForm) => {
    if (!projectId) return;
    setSubmitError('');
    try {
      const { data } = await projectsApi.update(projectId, formData);
      setProject(data);
      setEditing(false);
    } catch (err) {
      setSubmitError(normalizeError(err).message);
    }
  };

  const handleBoqExtractionComplete = () => {
    setHasBoqExtracted(true);
    setBoqRefreshKey((k) => k + 1);
  };

  const handleAnalysisComplete = () => {
    navigate(`/projects/${projectId}/setup`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading project...
      </div>
    );
  }

  if (!project) return null;

  const fullProject = project as Project;
  const isFullView = 'country' in project;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/projects')}
            className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
          >
            <ArrowLeft className="h-4 w-4 text-gray-500" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{project.project_name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant={statusVariant[project.status] || 'default'}>
                {statusLabel[project.status] || project.status}
              </Badge>
              {project.client_name && (
                <span className="text-sm text-gray-500">{project.client_name}</span>
              )}
            </div>
          </div>
        </div>
        {isOwner && !editing && (
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => navigate(`/projects/${projectId}/setup`)}>
              <ExternalLink className="mr-2 h-4 w-4" />
              Project Setup
            </Button>
            <Button variant="outline" onClick={() => setEditing(true)}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
          </div>
        )}
      </div>

      {/* Edit Mode */}
      {editing && isFullView && (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Edit Project</h2>
            <button onClick={() => { setEditing(false); setSubmitError(''); }}>
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

      {/* Project Info */}
      {!editing && (
        <Card>
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Project Information</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <InfoItem label="Project Name" value={project.project_name} />
            {'client_id' in project && (project as Project).client_id ? (
              <div>
                <p className="text-xs font-medium uppercase text-gray-400">Client</p>
                <button
                  onClick={() => navigate(`/clients/${(project as Project).client_id}`)}
                  className="mt-1 text-sm font-medium text-indigo-600 hover:text-indigo-800"
                >
                  {project.client_name || '\u2014'}
                </button>
              </div>
            ) : (
              <InfoItem label="Client" value={project.client_name || '\u2014'} />
            )}
            <InfoItem label="Status" value={statusLabel[project.status] || project.status} />
            <InfoItem
              label="Created"
              value={project.created_at ? new Date(project.created_at).toLocaleDateString() : '\u2014'}
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
              <InfoItem label="Created By" value={(project as ProjectAdmin).created_by_name || '\u2014'} />
            )}
          </div>
        </Card>
      )}

      {/* Workflow sections — only for project owner */}
      {isOwner && !editing && (
        <div className="space-y-6">
          {/* Step 1: Upload BOQ */}
          <BoqUploadSection
            projectId={projectId!}
            projectName={project.project_name}
            refreshKey={boqRefreshKey}
            onBoqUploaded={() => setHasBoq(true)}
          />

          {/* Step 2: Extract BOQ */}
          <BoqExtractionSection
            projectId={projectId!}
            hasBoq={hasBoq}
            onExtractionComplete={handleBoqExtractionComplete}
          />

          {/* Step 3: Upload Spec */}
          <SpecUpload
            projectId={projectId!}
            refreshKey={boqRefreshKey}
            onSpecUploaded={() => setHasSpec(true)}
          />

          {/* Step 4: Run Analysis (spec markdown + questions) */}
          <SpecAnalysisSection
            projectId={projectId!}
            hasSpec={hasSpec}
            hasBoqExtracted={hasBoqExtracted}
            onAnalysisComplete={handleAnalysisComplete}
          />
        </div>
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
