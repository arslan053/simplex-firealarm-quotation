import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import { specApi } from '../api/spec.api';
import { DeviceSelectionSection } from '../components/DeviceSelectionSection';

export function DeviceSelectionPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [projectName, setProjectName] = useState('');
  const [hasSpec, setHasSpec] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    projectsApi.get(projectId).then(({ data }) => setProjectName(data.project_name)).catch(() => {});
    specApi.checkExisting(projectId).then(({ data }) => {
      if (data.exists) setHasSpec(true);
    }).catch(() => {});
  }, [projectId]);

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Select Devices</h1>
          <p className="mt-1 text-sm text-gray-500">
            Match BOQ items to detection devices and notification appliances
          </p>
        </div>
      </div>

      <DeviceSelectionSection projectId={projectId} projectName={projectName} hasSpec={hasSpec} />
    </div>
  );
}
