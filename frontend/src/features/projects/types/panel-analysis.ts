export interface PanelAnalysisAnswerResponse {
  id: string;
  project_id: string;
  question_id: string;
  question_no: number;
  question_text: string;
  category: string;
  answer: string;
  confidence: string;
  supporting_notes: string[];
  inferred_from: string;
  created_at: string | null;
}

export interface PanelResult {
  total_detection_devices: number;
  panel_count: number | null;
  devices_per_panel: number | null;
  label: string;
}

export interface PanelAnalysisResultResponse {
  project_id: string;
  answers: PanelAnalysisAnswerResponse[];
  status: string;
  message: string;
  panel_result: PanelResult | null;
}
