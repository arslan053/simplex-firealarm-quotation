export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface BoqExtractionJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  message: string;
  boq_items_count: number;
}
