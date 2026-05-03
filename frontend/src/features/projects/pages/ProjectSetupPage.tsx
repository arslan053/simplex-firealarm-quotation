import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Play,
  Settings2,
  FileText,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import { pipelineApi } from '../api/pipeline.api';
import { boqApi } from '../api/boq.api';
import { specApi } from '../api/spec.api';
import { BoqUploadSection } from '../components/BoqUploadSection';
import { SpecUpload } from '../components/SpecUpload';
import { QuotationModal } from '../components/QuotationModal';
import type { GenerateQuotationRequest } from '../types/quotation';
import type { QuotationConfigData } from '../types/pipeline';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

const SERVICE_LABELS: Record<number, string> = {
  1: 'Supply Only',
  2: 'Supply + Installation',
  3: 'Supply + Full Installation',
};

export function ProjectSetupPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [projectName, setProjectName] = useState('');
  const [loading, setLoading] = useState(true);

  // Upload state
  const [hasBoq, setHasBoq] = useState(false);
  const [boqRefreshKey] = useState(0);

  // Overrides
  const [protocol, setProtocol] = useState('');
  const [notificationType, setNotificationType] = useState('');
  const [networkType, setNetworkType] = useState('');

  // Quotation config
  const [quotationConfig, setQuotationConfig] = useState<QuotationConfigData | null>(null);
  const [showQuotationModal, setShowQuotationModal] = useState(false);

  // Run state
  const [starting, setStarting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId) return;

    // Load project
    projectsApi.get(projectId).then(({ data }) => {
      setProjectName(data.project_name);
      // Pre-fill overrides from existing project fields
      if ('country' in data) {
        const p = data as { protocol?: string | null; notification_type?: string | null; network_type?: string | null };
        if (p.protocol) setProtocol(p.protocol);
        if (p.notification_type) setNotificationType(p.notification_type);
        if (p.network_type) setNetworkType(p.network_type);
      }
    }).catch(() => navigate('/projects')).finally(() => setLoading(false));

    // Check BOQ docs
    boqApi.listDocuments(projectId).then(({ data }) => {
      if (data.length > 0) setHasBoq(true);
    }).catch(() => {});

    // Check spec (no-op, spec is optional)
    specApi.checkExisting(projectId).catch(() => {});

    // Load existing quotation config
    pipelineApi.getQuotationConfig(projectId).then(({ data }) => {
      if (data.quotation_config && data.quotation_config.client_name) {
        setQuotationConfig(data.quotation_config);
      }
    }).catch(() => {});

    // Check if pipeline already started — redirect if so
    pipelineApi.getStatus(projectId).then(({ data }) => {
      if (data.status === 'running') {
        navigate(`/projects/${projectId}/progress`, { replace: true });
      } else if (data.status === 'completed') {
        navigate(`/projects/${projectId}/completed`, { replace: true });
      }
    }).catch(() => {
      // 404 = no pipeline run — that's expected
    });
  }, [projectId, navigate]);

  const canRun = hasBoq && quotationConfig !== null;

  const handleSaveOverrides = async () => {
    if (!projectId) return;
    try {
      await pipelineApi.saveOverrides(projectId, {
        protocol: protocol || null,
        notification_type: notificationType || null,
        network_type: networkType || null,
      });
    } catch {
      // Silent — overrides are optional
    }
  };

  const handleQuotationConfigured = async (config: GenerateQuotationRequest) => {
    if (!projectId) return;
    setShowQuotationModal(false);
    const configData: QuotationConfigData = {
      client_name: config.client_name,
      client_address: config.client_address,
      subject: config.subject || null,
      service_option: config.service_option,
      margin_percent: config.margin_percent,
      payment_terms_text: config.payment_terms_text || null,
      inclusion_answers: config.inclusion_answers || {},
    };
    setQuotationConfig(configData);

    try {
      await pipelineApi.saveQuotationConfig(projectId, configData);
    } catch (err) {
      setError(normalizeError(err).message);
    }
  };

  const handleRun = async () => {
    if (!projectId) return;
    setShowConfirm(false);
    setStarting(true);
    setError('');

    try {
      // Save overrides before starting
      await handleSaveOverrides();
      await pipelineApi.start(projectId);
      navigate(`/projects/${projectId}/progress`);
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading project...
      </div>
    );
  }

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-4 w-4 text-gray-500" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Project Setup</h1>
          {projectName && (
            <p className="mt-1 text-sm text-gray-500">{projectName}</p>
          )}
        </div>
      </div>

      {/* Section 1: Document Upload */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Upload Documents</h2>
        <BoqUploadSection
          projectId={projectId}
          projectName={projectName}
          refreshKey={boqRefreshKey}
          onBoqUploaded={() => setHasBoq(true)}
        />
        <SpecUpload
          projectId={projectId}
          refreshKey={boqRefreshKey}
          onSpecUploaded={() => {}}
        />
      </div>

      {/* Section 2: Optional Overrides */}
      <Card>
        <div className="mb-4 flex items-center gap-2">
          <Settings2 className="h-5 w-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900">
            Analysis Preferences (Optional)
          </h2>
        </div>
        <p className="mb-5 text-sm text-gray-500">
          Leave these on Auto-detect to let the system decide based on your
          documents. Only change them if you have a specific requirement.
        </p>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Protocol
            </label>
            <select
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">Auto-detect</option>
              <option value="MX">MX</option>
              <option value="IDNET">IDNET</option>
            </select>
            <p className="mt-1 text-xs text-gray-400">
              Communication protocol between devices
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Notification Type
            </label>
            <select
              value={notificationType}
              onChange={(e) => setNotificationType(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">Auto-detect</option>
              <option value="addressable">Addressable</option>
              <option value="non_addressable">Non-addressable</option>
            </select>
            <p className="mt-1 text-xs text-gray-400">
              Notification device addressing mode
            </p>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Network Type
            </label>
            <select
              value={networkType}
              onChange={(e) => setNetworkType(e.target.value)}
              className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="">Auto-detect</option>
              <option value="wired">Wired</option>
              <option value="fiber">Fiber</option>
              <option value="IP">IP</option>
            </select>
            <p className="mt-1 text-xs text-gray-400">
              Network infrastructure type
            </p>
          </div>
        </div>
      </Card>

      {/* Section 3: Quotation Configuration */}
      <Card>
        <div className="mb-4 flex items-center gap-2">
          <FileText className="h-5 w-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900">
            Quotation Details
          </h2>
        </div>

        {quotationConfig ? (
          <div className="space-y-3">
            <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 p-4">
              <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-600" />
              <div className="text-sm">
                <p className="font-medium text-green-800">
                  Quotation configured
                </p>
                <p className="mt-1 text-green-700">
                  {SERVICE_LABELS[quotationConfig.service_option] || 'Supply Only'}
                  {quotationConfig.margin_percent > 0 && `, ${quotationConfig.margin_percent}% margin`}
                  {quotationConfig.client_name && ` \u2014 ${quotationConfig.client_name}`}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              onClick={() => setShowQuotationModal(true)}
            >
              Edit Quotation Details
            </Button>
          </div>
        ) : (
          <div>
            <p className="mb-3 text-sm text-gray-500">
              Configure client details, service option, and payment terms for the
              quotation that will be generated.
            </p>
            <Button onClick={() => setShowQuotationModal(true)}>
              Configure Quotation Details
            </Button>
          </div>
        )}
      </Card>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <div className="flex items-start gap-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Run Button */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        {!canRun && (
          <p className="mb-3 text-sm text-gray-500">
            Upload a BOQ file and configure quotation details to start the
            analysis.
          </p>
        )}
        <Button
          onClick={() => setShowConfirm(true)}
          disabled={!canRun || starting}
          isLoading={starting}
          className="w-full justify-center"
        >
          <Play className="mr-2 h-4 w-4" />
          Run Full Analysis
        </Button>
      </div>

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowConfirm(false)}
          />
          <div className="relative z-10 mx-4 w-full max-w-md rounded-xl bg-white p-6 shadow-2xl">
            <h3 className="text-lg font-semibold text-gray-900">
              Start Analysis?
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              This will analyze your project and generate a quotation. This
              process takes 2-5 minutes. You can close this page and come back
              — the analysis will continue in the background.
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => setShowConfirm(false)}
              >
                Cancel
              </Button>
              <Button onClick={handleRun} isLoading={starting}>
                <Play className="mr-2 h-4 w-4" />
                Continue
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Quotation Modal */}
      {showQuotationModal && (
        <QuotationModal
          projectId={projectId}
          margin={quotationConfig?.margin_percent ?? 0}
          existingQuotation={
            quotationConfig
              ? {
                  id: '',
                  project_id: projectId,
                  reference_number: '',
                  client_name: quotationConfig.client_name,
                  client_address: quotationConfig.client_address,
                  subject: quotationConfig.subject,
                  service_option: quotationConfig.service_option,
                  margin_percent: quotationConfig.margin_percent,
                  payment_terms_text: quotationConfig.payment_terms_text,
                  inclusion_answers: quotationConfig.inclusion_answers,
                  subtotal_sar: 0,
                  vat_sar: 0,
                  grand_total_sar: 0,
                  original_file_name: '',
                  created_at: '',
                  updated_at: '',
                }
              : null
          }
          onClose={() => setShowQuotationModal(false)}
          onGenerated={() => {}}
          onConfigured={handleQuotationConfigured}
        />
      )}
    </div>
  );
}
