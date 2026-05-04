import { useState } from 'react';

import { BoqExcelUpload } from './BoqExcelUpload';
import { BoqPdfUpload } from './BoqPdfUpload';
import { BoqImagesUpload } from './BoqImagesUpload';

interface BoqUploadSectionProps {
  projectId: string;
  onBoqUploaded: () => void;
}

export function BoqUploadSection({ projectId, onBoqUploaded }: BoqUploadSectionProps) {
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSuccess = () => {
    onBoqUploaded();
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <BoqExcelUpload
          projectId={projectId}
          disabled={isProcessing}
          onProcessingChange={setIsProcessing}
          onSuccess={handleSuccess}
        />
        <BoqPdfUpload
          projectId={projectId}
          disabled={isProcessing}
          onProcessingChange={setIsProcessing}
          onSuccess={handleSuccess}
        />
        <BoqImagesUpload
          projectId={projectId}
          disabled={isProcessing}
          onProcessingChange={setIsProcessing}
          onSuccess={handleSuccess}
        />
      </div>
    </div>
  );
}
