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

export interface DimensionEntry {
  name: string;
  quantity: number | null;
  building_count: number | null;
}

export interface BoqItemResponse {
  id: string;
  row_number: number;
  description: string | null;
  quantity: number | null;
  unit: string | null;
  is_hidden: boolean;
  is_valid: boolean;
  type: 'boq_item' | 'description' | 'section_description';
  category: string | null;
  dimensions: DimensionEntry[] | null;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface BoqItemListResponse {
  data: BoqItemResponse[];
  pagination: PaginationMeta;
}
