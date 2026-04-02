import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Calculator } from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import { specApi } from '../api/spec.api';
import { panelSelectionApi } from '../api/panel-selection.api';
import { ProjectDocuments } from '../components/ProjectDocuments';
import { AnalysisSection } from '../components/AnalysisSection';
import { PanelAnalysisSection } from '../components/PanelAnalysisSection';
import { DeviceSelectionSection } from '../components/DeviceSelectionSection';
import { PanelConfigurationSection } from '../components/PanelConfigurationSection';
import { Button } from '@/shared/ui/Button';

export function ProjectResultsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [projectName, setProjectName] = useState('');
  const [hasSpec, setHasSpec] = useState(false);
  const [deviceRefreshKey, setDeviceRefreshKey] = useState(0);
  const [panelDone, setPanelDone] = useState(false);

  const handlePanelComplete = useCallback(() => {
    setDeviceRefreshKey((k) => k + 1);
    setPanelDone(true);
  }, []);

  useEffect(() => {
    if (!projectId) return;
    projectsApi
      .get(projectId)
      .then(({ data }) => setProjectName(data.project_name))
      .catch(() => navigate('/projects'));
    specApi.checkExisting(projectId).then(({ data }) => {
      if (data.exists) setHasSpec(true);
    }).catch(() => {});
    // Check if panel already done
    panelSelectionApi.getResults(projectId).then(({ data }) => {
      if (data.panel_supported && data.status !== 'empty') {
        setPanelDone(true);
      }
    }).catch(() => {});
  }, [projectId, navigate]);

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
          <h1 className="text-2xl font-bold text-gray-900">Project Results</h1>
          {projectName && (
            <p className="mt-1 text-sm text-gray-500">{projectName}</p>
          )}
        </div>
      </div>

      {/* Project Documents */}
      <ProjectDocuments projectId={projectId} />

      {/* Protocol Decision Analysis */}
      <AnalysisSection projectId={projectId} refreshKey={0} />

      {/* Panel Selection Analysis */}
      <PanelAnalysisSection projectId={projectId} refreshKey={0} />

      {/* Device Selection */}
      <DeviceSelectionSection projectId={projectId} projectName={projectName} refreshKey={deviceRefreshKey} hasSpec={hasSpec} />

      {/* Panel Configuration */}
      <PanelConfigurationSection projectId={projectId} onPanelComplete={handlePanelComplete} hasSpec={hasSpec} />

      {/* Pricing Link */}
      <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Quotation Pricing</h2>
          <p className="text-sm text-gray-500">
            {panelDone
              ? 'Generate a full pricing quotation with margin and VAT'
              : 'Complete panel configuration first to enable pricing'}
          </p>
        </div>
        <Button
          variant="primary"
          onClick={() => navigate(`/projects/${projectId}/pricing`)}
          disabled={!panelDone}
        >
          <Calculator className="mr-2 h-4 w-4" />
          Open Pricing
        </Button>
      </div>
    </div>
  );
}
