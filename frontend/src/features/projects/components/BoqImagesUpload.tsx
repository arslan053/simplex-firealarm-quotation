import { useRef, useState } from 'react';
import { ImagePlus, CheckCircle, AlertCircle } from 'lucide-react';

import { boqApi } from '../api/boq.api';
import type { DocumentResponse } from '../types/boq';
import { Card } from '@/shared/ui/Card';
import { Button } from '@/shared/ui/Button';
import { normalizeError } from '@/shared/api/errors';

interface BoqImagesUploadProps {
  projectId: string;
  disabled: boolean;
  onProcessingChange: (processing: boolean) => void;
  onSuccess: () => void;
}

export function BoqImagesUpload({
  projectId,
  disabled,
  onProcessingChange,
  onSuccess,
}: BoqImagesUploadProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState<DocumentResponse | null>(null);
  const [error, setError] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(files);
    setError('');
    setUploadedDoc(null);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);
    onProcessingChange(true);
    setError('');
    setUploadedDoc(null);

    try {
      const { data } = await boqApi.uploadImages(projectId, selectedFiles);
      setUploadedDoc(data);
      onSuccess();
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError(normalizeError(err).message);
    } finally {
      setUploading(false);
      onProcessingChange(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-col items-center py-6 text-center">
        <ImagePlus className="mb-3 h-10 w-10 text-indigo-400" />
        <h3 className="text-sm font-semibold text-gray-900">Upload Images</h3>
        <p className="mt-1 text-xs text-gray-500">
          BOQ photos or scans (JPG, PNG, etc.)
        </p>

        <div className="mt-4 flex flex-col items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            disabled={disabled}
            className="block w-full max-w-xs text-sm text-gray-500 file:mr-4 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-indigo-700 hover:file:bg-indigo-100 disabled:opacity-50"
          />
          {selectedFiles.length > 0 && (
            <p className="text-xs text-gray-500">
              {selectedFiles.length} image{selectedFiles.length !== 1 ? 's' : ''} selected
            </p>
          )}
          <Button
            variant="primary"
            size="sm"
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || uploading || disabled}
            isLoading={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload Images'}
          </Button>
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {uploadedDoc && (
          <div className="mt-4 flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm text-green-700">
            <CheckCircle className="h-4 w-4 flex-shrink-0" />
            <span>File uploaded. Run analysis to extract.</span>
          </div>
        )}
      </div>
    </Card>
  );
}
