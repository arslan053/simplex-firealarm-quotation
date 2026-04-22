import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  Pencil,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  Loader2,
  X,
} from 'lucide-react';

import { projectsApi } from '../api/projects.api';
import { pipelineApi } from '../api/pipeline.api';
import { quotationApi } from '../api/quotation.api';
import { ProjectDocuments } from '../components/ProjectDocuments';
import { DeviceSelectionSection } from '../components/DeviceSelectionSection';
import { PanelConfigurationSection } from '../components/PanelConfigurationSection';
import { QuotationModal } from '../components/QuotationModal';
import type { QuotationResponse } from '../types/quotation';
import type { QuotationConfigData } from '../types/pipeline';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { Badge } from '@/shared/ui/Badge';
import { normalizeError } from '@/shared/api/errors';

export function ProjectCompletedPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [projectName, setProjectName] = useState('');
  const [completedAt, setCompletedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [quotation, setQuotation] = useState<QuotationResponse | null>(null);
  const [quotationConfig, setQuotationConfig] = useState<QuotationConfigData | null>(null);

  const [showDetails, setShowDetails] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [downloadingDocx, setDownloadingDocx] = useState(false);
  const [downloadingXlsx, setDownloadingXlsx] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState('');
  const [regenerateSuccess, setRegenerateSuccess] = useState(false);

  useEffect(() => {
    if (!projectId) return;

    // Load project
    projectsApi.get(projectId).then(({ data }) => {
      setProjectName(data.project_name);
    }).catch(() => navigate('/projects'));

    // Load pipeline status — redirect if not completed
    pipelineApi.getStatus(projectId).then(({ data }) => {
      if (data.status === 'running') {
        navigate(`/projects/${projectId}/progress`, { replace: true });
        return;
      }
      if (data.status !== 'completed') {
        navigate(`/projects/${projectId}/setup`, { replace: true });
        return;
      }
      setCompletedAt(data.completed_at);
    }).catch(() => {
      navigate(`/projects/${projectId}/setup`, { replace: true });
    });

    // Load quotation
    quotationApi.get(projectId).then(({ data }) => {
      setQuotation(data);
    }).catch(() => {});

    // Load quotation config
    pipelineApi.getQuotationConfig(projectId).then(({ data }) => {
      if (data.quotation_config) {
        setQuotationConfig(data.quotation_config);
      }
    }).catch(() => {});

    setLoading(false);
  }, [projectId, navigate]);

  const handleDownload = async (format: 'docx' | 'xlsx') => {
    if (!projectId) return;
    const setLoading = format === 'docx' ? setDownloadingDocx : setDownloadingXlsx;
    setLoading(true);
    try {
      const { data } = await quotationApi.download(projectId, format);
      window.open(data.url, '_blank');
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async () => {
    if (!projectId) return;
    setPreviewing(true);
    const newWindow = window.open('about:blank', '_blank');
    try {
      const blob = await quotationApi.preview(projectId).then((r) => r.data);
      const url = URL.createObjectURL(blob);
      if (newWindow) newWindow.location.href = url;
    } catch {
      if (newWindow) newWindow.close();
    } finally {
      setPreviewing(false);
    }
  };

  const handleRegenerate = async (updated: QuotationResponse) => {
    setShowEditModal(false);
    setQuotation(updated);
    setRegenerateSuccess(true);

    // Auto-open the regenerated PDF in a new tab
    try {
      const blob = await quotationApi.preview(projectId!).then((r) => r.data);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch {
      // PDF preview failed — user can still download manually
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-500">
        Loading...
      </div>
    );
  }

  if (!projectId) return null;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
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
            <h1 className="text-2xl font-bold text-gray-900">{projectName}</h1>
            <div className="mt-1 flex items-center gap-2">
              <Badge variant="success">
                <CheckCircle className="mr-1 h-3 w-3" />
                Completed
              </Badge>
              {completedAt && (
                <span className="text-sm text-gray-500">
                  {new Date(completedAt).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <Card>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => handleDownload('docx')} isLoading={downloadingDocx}>
            <FileText className="mr-2 h-4 w-4" />
            Download Word
          </Button>
          <Button onClick={() => handleDownload('xlsx')} isLoading={downloadingXlsx}>
            <FileSpreadsheet className="mr-2 h-4 w-4" />
            Download Excel
          </Button>
          <Button variant="outline" onClick={handlePreview} disabled={previewing}>
            {previewing ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Eye className="mr-2 h-4 w-4" />
            )}
            View PDF
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowEditModal(true)}
          >
            <Pencil className="mr-2 h-4 w-4" />
            Edit & Regenerate
          </Button>
          <Button
            variant="outline"
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? (
              <ChevronUp className="mr-2 h-4 w-4" />
            ) : (
              <ChevronDown className="mr-2 h-4 w-4" />
            )}
            View Details
          </Button>
        </div>
      </Card>

      {/* Regeneration Success */}
      {regenerateSuccess && (
        <div className="flex items-start gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">
              Quotation regenerated successfully!
            </p>
            <p className="mt-0.5 text-sm text-green-700">
              The updated PDF has been opened in a new tab. You can also download it below.
            </p>
          </div>
          <button
            onClick={() => setRegenerateSuccess(false)}
            className="rounded p-1 text-green-600 hover:bg-green-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Quotation Summary */}
      {quotation && (
        <Card className="border border-gray-100">
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <p className="text-xs font-medium uppercase text-gray-400">
                Reference
              </p>
              <p className="mt-1 text-sm text-gray-900">
                {quotation.reference_number}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-400">
                Client
              </p>
              <p className="mt-1 text-sm text-gray-900">
                {quotation.client_name}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-gray-400">
                Grand Total
              </p>
              <p className="mt-1 text-sm font-semibold text-gray-900">
                SAR{' '}
                {quotation.grand_total_sar.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Expandable Details */}
      {showDetails && (
        <div className="space-y-6">
          <DeviceSelectionSection
            projectId={projectId}
            projectName={projectName}
            readOnly
          />
          <PanelConfigurationSection projectId={projectId} readOnly />
        </div>
      )}

      {/* Project Documents */}
      <ProjectDocuments projectId={projectId} />

      {/* Error */}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Edit & Regenerate Modal */}
      {showEditModal && (
        <QuotationModal
          projectId={projectId}
          margin={quotation?.margin_percent ?? quotationConfig?.margin_percent ?? 0}
          existingQuotation={quotation}
          onClose={() => setShowEditModal(false)}
          onGenerated={handleRegenerate}
        />
      )}
    </div>
  );
}
