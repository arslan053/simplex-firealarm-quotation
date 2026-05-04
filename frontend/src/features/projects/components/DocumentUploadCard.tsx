import { useRef, useState, type ReactNode } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, Trash2 } from 'lucide-react';

import { Button } from '@/shared/ui/Button';
import { Card } from '@/shared/ui/Card';
import { normalizeError } from '@/shared/api/errors';

interface CurrentDocument {
  id: string;
  original_file_name: string;
}

interface DocumentUploadCardProps {
  icon: ReactNode;
  title: string;
  description: string;
  accept: string;
  uploadLabel: string;
  replaceLabel: string;
  currentDocument: CurrentDocument | null;
  hasExistingDocument?: boolean;
  multiple?: boolean;
  disabled?: boolean;
  uploadDisabled?: boolean;
  selectedLabel?: (count: number) => string;
  upload: (files: File[]) => Promise<unknown>;
  remove?: () => Promise<unknown>;
  onSuccess: () => void;
}

export function DocumentUploadCard({
  icon,
  title,
  description,
  accept,
  uploadLabel,
  replaceLabel,
  currentDocument,
  hasExistingDocument,
  multiple = false,
  disabled = false,
  uploadDisabled = false,
  selectedLabel,
  upload,
  remove,
  onSuccess,
}: DocumentUploadCardProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [showReplaceWarning, setShowReplaceWarning] = useState(false);
  const [showRemoveWarning, setShowRemoveWarning] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [error, setError] = useState('');

  const hasSelection = selectedFiles.length > 0;
  const shouldReplace = !uploadDisabled && (hasExistingDocument ?? Boolean(currentDocument));
  const isUploadDisabled = disabled || uploadDisabled;

  const clearSelection = () => {
    setSelectedFiles([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(files);
    setError('');
    setUploaded(false);
    setShowReplaceWarning(false);
  };

  const handleUploadClick = () => {
    if (!hasSelection) return;
    if (shouldReplace) {
      setShowReplaceWarning(true);
      return;
    }
    void doUpload();
  };

  const doUpload = async () => {
    if (!hasSelection) return;

    setUploading(true);
    setError('');
    setUploaded(false);
    setShowReplaceWarning(false);

    try {
      await upload(selectedFiles);
      setUploaded(true);
      clearSelection();
      onSuccess();
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setUploading(false);
    }
  };

  const doRemove = async () => {
    if (!remove) return;

    setRemoving(true);
    setError('');
    setShowRemoveWarning(false);

    try {
      await remove();
      setUploaded(false);
      clearSelection();
      onSuccess();
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setRemoving(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-col items-center py-6 text-center">
        {icon}
        <h3 className="text-sm font-semibold text-gray-900">
          {shouldReplace ? `Replace ${title}` : `Upload ${title}`}
        </h3>
        <p className="mt-1 text-xs text-gray-500">{description}</p>

        {currentDocument && !uploaded && (
          <div className="mt-3 flex max-w-full items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            <span className="truncate">
              Current: <span className="font-medium">{currentDocument.original_file_name}</span>
            </span>
          </div>
        )}

        <div className="mt-4 flex flex-col items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept={accept}
            multiple={multiple}
            onChange={handleFileChange}
            disabled={isUploadDisabled || uploading || removing}
            className="block w-full max-w-xs text-sm text-gray-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
          />
          {multiple && selectedFiles.length > 0 && (
            <p className="text-xs text-gray-500">
              {selectedLabel?.(selectedFiles.length) || `${selectedFiles.length} files selected`}
            </p>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={handleUploadClick}
              disabled={!hasSelection || uploading || removing || isUploadDisabled}
              isLoading={uploading}
            >
              {uploading ? 'Uploading...' : shouldReplace ? replaceLabel : uploadLabel}
            </Button>
            {currentDocument && remove && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowRemoveWarning(true)}
                disabled={uploading || removing || disabled}
                isLoading={removing}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Remove
              </Button>
            )}
          </div>
        </div>

        {showReplaceWarning && (
          <WarningBox
            title={`${title} already exists.`}
            message="Uploading a new file will replace the current one."
            confirmLabel="Confirm Upload"
            loading={uploading}
            onCancel={() => setShowReplaceWarning(false)}
            onConfirm={doUpload}
          />
        )}

        {showRemoveWarning && (
          <WarningBox
            title={`Remove ${title}?`}
            message="This will delete the uploaded document from this project."
            confirmLabel="Remove"
            loading={removing}
            onCancel={() => setShowRemoveWarning(false)}
            onConfirm={doRemove}
          />
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {uploaded && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            <span>File uploaded. Run analysis to extract.</span>
          </div>
        )}
      </div>
    </Card>
  );
}

function WarningBox({
  title,
  message,
  confirmLabel,
  loading,
  onCancel,
  onConfirm,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <div className="mt-4 w-full max-w-md rounded-lg bg-yellow-50 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-yellow-600" />
        <div className="text-left text-sm text-yellow-800">
          <p className="font-medium">{title}</p>
          <p className="mt-1">{message}</p>
          <div className="mt-3 flex gap-2">
            <Button variant="outline" size="sm" onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" onClick={onConfirm} isLoading={loading}>
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
