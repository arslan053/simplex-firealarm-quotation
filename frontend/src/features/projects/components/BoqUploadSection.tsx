import { useCallback, useEffect, useState } from 'react';
import { FileText, FileUp, ImagePlus } from 'lucide-react';

import { boqApi } from '../api/boq.api';
import type { DocumentResponse } from '../types/boq';
import { DocumentUploadCard } from './DocumentUploadCard';

interface BoqUploadSectionProps {
  projectId: string;
  onBoqChanged: (hasBoq: boolean) => void;
}

export function BoqUploadSection({ projectId, onBoqChanged }: BoqUploadSectionProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentDocument, setCurrentDocument] = useState<DocumentResponse | null>(null);
  const hasExistingBoq = Boolean(currentDocument);
  const currentKind = getBoqDocumentKind(currentDocument);

  const refreshDocuments = useCallback(async () => {
    const { data } = await boqApi.listDocuments(projectId);
    const doc = data[0] || null;
    setCurrentDocument(doc);
    onBoqChanged(Boolean(doc));
  }, [projectId, onBoqChanged]);

  useEffect(() => {
    refreshDocuments().catch(() => {
      setCurrentDocument(null);
      onBoqChanged(false);
    });
  }, [refreshDocuments, onBoqChanged]);

  const handleUpload = async (uploadFn: () => Promise<unknown>) => {
    setIsProcessing(true);
    try {
      await uploadFn();
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <DocumentUploadCard
          icon={<FileUp className="mb-3 h-10 w-10 text-indigo-400" />}
          title="BOQ Excel"
          description="Bill of Quantities (.xlsx, .xls)"
          accept=".xlsx,.xls"
          uploadLabel="Upload Excel"
          replaceLabel="Replace BOQ"
          currentDocument={currentKind === 'excel' ? currentDocument : null}
          disabled={isProcessing}
          uploadDisabled={hasExistingBoq}
          upload={(files) => handleUpload(() => boqApi.upload(projectId, files[0]))}
          remove={currentKind === 'excel' && currentDocument ? () => boqApi.removeDocument(projectId, currentDocument.id) : undefined}
          onSuccess={refreshDocuments}
        />
        <DocumentUploadCard
          icon={<FileText className="mb-3 h-10 w-10 text-indigo-400" />}
          title="BOQ PDF"
          description="Bill of Quantities (.pdf)"
          accept=".pdf"
          uploadLabel="Upload PDF"
          replaceLabel="Replace BOQ"
          currentDocument={currentKind === 'pdf' ? currentDocument : null}
          disabled={isProcessing}
          uploadDisabled={hasExistingBoq}
          upload={(files) => handleUpload(() => boqApi.uploadPdf(projectId, files[0]))}
          remove={currentKind === 'pdf' && currentDocument ? () => boqApi.removeDocument(projectId, currentDocument.id) : undefined}
          onSuccess={refreshDocuments}
        />
        <DocumentUploadCard
          icon={<ImagePlus className="mb-3 h-10 w-10 text-indigo-400" />}
          title="BOQ Images"
          description="BOQ photos or scans (JPG, PNG, etc.)"
          accept="image/*"
          uploadLabel="Upload Images"
          replaceLabel="Replace BOQ"
          currentDocument={currentKind === 'images' ? currentDocument : null}
          disabled={isProcessing}
          uploadDisabled={hasExistingBoq}
          multiple
          selectedLabel={(count) => `${count} image${count !== 1 ? 's' : ''} selected`}
          upload={(files) => handleUpload(() => boqApi.uploadImages(projectId, files))}
          remove={currentKind === 'images' && currentDocument ? () => boqApi.removeDocument(projectId, currentDocument.id) : undefined}
          onSuccess={refreshDocuments}
        />
      </div>
    </div>
  );
}

function getBoqDocumentKind(doc: DocumentResponse | null): 'excel' | 'pdf' | 'images' | null {
  if (!doc) return null;

  const fileName = doc.original_file_name.toLowerCase();
  if (fileName.startsWith('boq_images_')) return 'images';
  if (fileName.endsWith('.xlsx') || fileName.endsWith('.xls')) return 'excel';
  if (fileName.endsWith('.pdf')) return 'pdf';
  return null;
}
