export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface SpecAnalysisJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  message: string;
  spec_blocks_count: number;
  answers_count: number;
}
