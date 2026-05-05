export interface DocumentResponse {
  id: string;
  project_id: string;
  type: string;
  original_file_name: string;
  file_size: number;
  created_at: string | null;
  document_category: string | null;
  document_category_confidence: number | null;
}
