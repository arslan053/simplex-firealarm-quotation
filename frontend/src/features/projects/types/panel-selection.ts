export interface PanelSelectionJobStatus {
  job_id: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  message: string;
}

export interface PanelSelectionGateResult {
  q1_total_devices: number;
  q1_devices_per_panel: number;
  q1_panel_count: number | null;
  q1_passed: boolean;
  panel_type: string | null;
  panel_label: string | null;
  mx_addressable_blocked: boolean;
  q2_answer: string | null;
  q2_passed: boolean;
  q3_answer: string | null;
  q3_passed: boolean;
  is_4100es?: boolean;
  entry_reasons?: string[];
  loop_count?: number | null;
}

export interface PanelSelectionProduct {
  product_code: string;
  product_name: string | null;
  quantity: number;
  source: string;
  question_no: number | null;
  reason: string | null;
}

export interface PanelGroupProduct {
  product_code: string;
  product_name: string | null;
  quantity: number;
  source: string;
  question_no: number | null;
  reason: string | null;
}

export interface PanelGroupResult {
  id: string;
  boq_description: string | null;
  loop_count: number;
  quantity: number;
  panel_type: string;
  panel_label: string;
  is_main: boolean;
  products: PanelGroupProduct[];
}

export interface PanelSelectionResults {
  project_id: string;
  panel_supported: boolean;
  gate_result: PanelSelectionGateResult;
  products: PanelSelectionProduct[];
  is_multi_group?: boolean;
  panel_groups?: PanelGroupResult[];
  status: string;
  message: string;
}

export interface JobStartResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface PanelQuestionAnswer {
  question_no: number;
  question: string;
  answer: string;
  confidence: string | null;
  supporting_notes: string[];
}

export interface PanelAnswersResponse {
  answers: PanelQuestionAnswer[];
}
