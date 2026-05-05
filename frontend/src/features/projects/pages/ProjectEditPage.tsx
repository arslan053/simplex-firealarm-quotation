import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { ProjectInfoEditor } from '../components/ProjectInfoEditor';

export function ProjectEditPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  if (!projectId) return null;

  const backToSetup = () => navigate(`/projects/${projectId}/setup`);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={backToSetup}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Edit Project</h1>
          <p className="mt-1 text-sm text-gray-500">Update project information</p>
        </div>
      </div>

      <ProjectInfoEditor
        projectId={projectId}
        initialEditing
        onCancel={backToSetup}
        onProjectUpdated={backToSetup}
      />
    </div>
  );
}
