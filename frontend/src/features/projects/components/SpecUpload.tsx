import { useEffect, useRef, useState } from 'react';
import { FileUp, AlertCircle, CheckCircle, AlertTriangle } from 'lucide-react';

import { specApi } from '../api/spec.api';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';
import { SpecResults } from './SpecResults';

interface SpecUploadProps {
  projectId: string;
  refreshKey: number;
  onSpecUploaded: () => void;
}

export function SpecUpload({ projectId, refreshKey, onSpecUploaded }: SpecUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [existingSpec, setExistingSpec] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showWarning, setShowWarning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [error, setError] = useState('');
  const [documentId, setDocumentId] = useState<string | null>(null);

  // Check for existing spec on mount
  useEffect(() => {
    specApi
      .checkExisting(projectId)
      .then(({ data }) => {
        setExistingSpec(data.exists);
        if (data.exists && data.document) {
          setDocumentId(data.document.id);
        }
      })
      .catch(() => {});
  }, [projectId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    setError('');
    setShowWarning(false);
    setUploaded(false);
  };

  const handleUploadClick = () => {
    if (!selectedFile) return;

    if (existingSpec) {
      setShowWarning(true);
    } else {
      doUpload();
    }
  };

  const doUpload = async () => {
    if (!selectedFile) return;

    setShowWarning(false);
    setUploading(true);
    setError('');
    setUploaded(false);

    try {
      const { data } = await specApi.upload(projectId, selectedFile);
      setExistingSpec(true);
      setDocumentId(data.document.id);
      setUploaded(true);
      onSpecUploaded();

      // Clear file input
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-col items-center py-6 text-center">
          <FileUp className="mb-3 h-10 w-10 text-indigo-400" />
          <h3 className="text-sm font-semibold text-gray-900">
            Upload Specification File
          </h3>
          <p className="mt-1 text-xs text-gray-500">
            Technical specifications document (.pdf)
          </p>

          <div className="mt-4 flex flex-col items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="block w-full max-w-xs text-sm text-gray-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={handleUploadClick}
              disabled={!selectedFile || uploading}
              isLoading={uploading}
            >
              {uploading ? 'Uploading...' : 'Upload Spec'}
            </Button>
          </div>

          {/* Replacement warning */}
          {showWarning && (
            <div className="mt-4 w-full max-w-md rounded-lg bg-yellow-50 p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-yellow-600" />
                <div className="text-left text-sm text-yellow-800">
                  <p className="font-medium">A specification already exists.</p>
                  <p className="mt-1">
                    Uploading a new file will delete the previous one.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowWarning(false)}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={doUpload}
                      isLoading={uploading}
                    >
                      Confirm Upload
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Uploaded badge */}
          {uploaded && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">
              <CheckCircle className="h-4 w-4 flex-shrink-0" />
              <span>File uploaded. Run analysis to extract.</span>
            </div>
          )}
        </div>
      </Card>

      {/* Structured block results */}
      {documentId && (
        <SpecResults
          projectId={projectId}
          documentId={documentId}
          refreshKey={refreshKey}
        />
      )}
    </div>
  );
}
