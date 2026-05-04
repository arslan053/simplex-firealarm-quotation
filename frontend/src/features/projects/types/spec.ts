export interface SpecDocumentResponse {
  id: string;
  project_id: string;
  type: string;
  original_file_name: string;
  file_size: number;
  created_at: string | null;
}

export interface SpecUploadResponse {
  document: SpecDocumentResponse;
  message: string;
}

export interface SpecExistingCheckResponse {
  exists: boolean;
  document: SpecDocumentResponse | null;
}
