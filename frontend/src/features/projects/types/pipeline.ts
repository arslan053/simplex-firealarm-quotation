export interface PipelineStatus {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  current_step: string | null;
  steps_completed: string[];
  error_message: string | null;
  error_step: string | null;
  retry_count: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface StartPipelineResponse {
  pipeline_run_id: string;
  status: string;
}

export interface QuotationConfigData {
  client_name: string;
  client_address: string;
  subject?: string | null;
  service_option: number;
  margin_percent: number;
  payment_terms_text?: string | null;
  inclusion_answers: Record<string, boolean>;
}

export interface OverridesData {
  protocol?: string | null;
  notification_type?: string | null;
  network_type?: string | null;
}

export const PIPELINE_STEPS = [
  { key: 'boq_extraction', label: 'BOQ Extraction' },
  { key: 'spec_analysis', label: 'Specification Analysis' },
  { key: 'device_selection', label: 'Device Selection' },
  { key: 'panel_selection', label: 'Panel Configuration' },
  { key: 'pricing', label: 'Pricing Calculation' },
  { key: 'quotation_generation', label: 'Quotation Generation' },
] as const;
