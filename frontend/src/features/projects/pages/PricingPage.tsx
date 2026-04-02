import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import { PricingSection } from '../components/PricingSection';

export function PricingPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [projectName, setProjectName] = useState('');

  useEffect(() => {
    if (!projectId) return;
    projectsApi
      .get(projectId)
      .then(({ data }) => setProjectName(data.project_name))
      .catch(() => navigate('/projects'));
  }, [projectId, navigate]);

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <button
          onClick={() => navigate(`/projects/${projectId}/results`)}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100 transition-colors"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Pricing</h1>
          {projectName && (
            <p className="mt-0.5 text-sm text-gray-500">{projectName}</p>
          )}
        </div>
      </div>

      <PricingSection projectId={projectId} projectName={projectName} />
    </div>
  );
}
