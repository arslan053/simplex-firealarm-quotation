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

export interface SpecBlock {
  id: string;
  document_id: string;
  page_no: number;
  parent_id: string | null;
  order_in_page: number;
  style: string;
  level: number | null;
  list_kind: string | null;
  content: string;
}

export interface SpecBlockListResponse {
  data: SpecBlock[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
}
