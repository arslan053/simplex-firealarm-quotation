import { useState } from 'react';

import { BoqExcelUpload } from './BoqExcelUpload';
import { BoqPdfUpload } from './BoqPdfUpload';
import { BoqImagesUpload } from './BoqImagesUpload';
import { BoqItemsTable } from './BoqItemsTable';

interface BoqUploadSectionProps {
  projectId: string;
  projectName: string;
  refreshKey: number;
  onBoqUploaded: () => void;
}

export function BoqUploadSection({ projectId, projectName, refreshKey, onBoqUploaded }: BoqUploadSectionProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [showItems, setShowItems] = useState(false);

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

      <BoqItemsTable
        projectId={projectId}
        projectName={projectName}
        show={showItems}
        onToggleShow={() => setShowItems(!showItems)}
        refreshKey={refreshKey}
      />
    </div>
  );
}
