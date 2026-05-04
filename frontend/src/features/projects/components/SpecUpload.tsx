import { useCallback, useEffect, useState } from 'react';
import { FileUp } from 'lucide-react';

import { specApi } from '../api/spec.api';
import type { SpecDocumentResponse } from '../types/spec';
import { DocumentUploadCard } from './DocumentUploadCard';

interface SpecUploadProps {
  projectId: string;
  onSpecUploaded: () => void;
}

export function SpecUpload({ projectId, onSpecUploaded }: SpecUploadProps) {
  const [currentDocument, setCurrentDocument] = useState<SpecDocumentResponse | null>(null);

  const refreshSpec = useCallback(async () => {
    const { data } = await specApi.checkExisting(projectId);
    setCurrentDocument(data.exists ? data.document : null);
  }, [projectId]);

  useEffect(() => {
    refreshSpec().catch(() => setCurrentDocument(null));
  }, [refreshSpec]);

  const handleSuccess = async () => {
    await refreshSpec();
    onSpecUploaded();
  };

  return (
    <div className="space-y-6">
      <DocumentUploadCard
        icon={<FileUp className="mb-3 h-10 w-10 text-indigo-400" />}
        title="Specification File"
        description="Technical specifications document (.pdf)"
        accept=".pdf"
        uploadLabel="Upload Spec"
        replaceLabel="Replace Spec"
        currentDocument={currentDocument}
        upload={(files) => specApi.upload(projectId, files[0])}
        remove={currentDocument ? () => specApi.remove(projectId) : undefined}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
