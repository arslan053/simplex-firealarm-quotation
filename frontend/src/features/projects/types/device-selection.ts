export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface DeviceSelectionJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  message: string;
  matched_count: number;
}

export interface DeviceSelectionItem {
  boq_item_id: string;
  boq_description: string | null;
  selectable_id: string | null;
  selectable_category: string | null;
  selection_type: 'single' | 'combo' | 'none';
  product_codes: string[];
  selectable_description: string | null;
  reason: string | null;
  status: 'finalized' | 'no_match' | 'pending_panel';
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface DeviceSelectionResultsResponse {
  project_id: string;
  data: DeviceSelectionItem[];
  pagination: PaginationMeta;
}
