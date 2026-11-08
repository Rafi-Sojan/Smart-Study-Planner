export type FeatureValue = boolean | number | string | null;
export type FeatureKind = "number" | "string" | "boolean" | "unknown";

export interface FeatureField {
  name: string;
  kind: FeatureKind;
  required: boolean;
}

export interface SessionState {
  authentication_required: boolean;
  browser_login_enabled: boolean;
  authenticated: boolean;
  username: string | null;
  expires_at: string | null;
}

export interface ModelMetadata {
  model_id: string;
  label: string;
  description: string;
  dataset: string | null;
  cutoff_days: number | null;
  model_version: string;
  model_source: string;
  registry_name: string | null;
  registry_version: string | null;
  threshold: number;
  threshold_source: string;
  feature_count: number;
  feature_names: string[];
  feature_fields: FeatureField[];
  feature_contract_sha256: string;
}

export interface ModelOption {
  model_id: string;
  label: string;
  description: string;
  dataset: string | null;
  cutoff_days: number | null;
  model_version: string;
  threshold: number;
  feature_count: number;
  is_default: boolean;
}

export interface ModelCatalog {
  default_model_id: string;
  models: ModelOption[];
}

export interface RiskResponse {
  model_id: string;
  risk_score: number;
  threshold: number;
  alert: boolean;
  model_version: string;
  feature_contract_sha256: string;
  threshold_source: string;
}

export interface StudyTaskPayload {
  task_id: string;
  title: string;
  subject: string;
  deadline: string;
  estimated_minutes: number;
  completed_minutes: number;
  difficulty: number;
  importance: number;
}

export interface AvailabilityPayload {
  start: string;
  end: string;
}

export interface RankedTask {
  task_id: string;
  title: string | null;
  subject: string | null;
  priority_score: number;
  remaining_minutes: number;
  rationale: string[];
}

export interface PlannedSession {
  task_id: string;
  title: string;
  subject: string;
  start: string;
  end: string;
  study_minutes: number;
  priority_score: number;
}

export interface StudyPlanResponse {
  model_id: string;
  risk_score: number;
  threshold: number;
  alert: boolean;
  model_version: string;
  ranked_tasks: RankedTask[];
  sessions: PlannedSession[];
  unscheduled_minutes: Record<string, number>;
  recommendations: string[];
  human_review_required: boolean;
}

export type StudentGoal =
  | "build_consistency"
  | "prepare_for_exams"
  | "complete_assignments"
  | "recover_missed_work"
  | "balance_subjects";

export type StudentCourseType =
  | "theory"
  | "theory_lab"
  | "theory_project"
  | "elective"
  | "other";

export type OptionalNumberDraft = number | "";

export interface StudentIntakeDraft {
  primary_goal: StudentGoal;
  subjects: string;
  course_type: StudentCourseType;
  current_term: number;
  current_credit_load: OptionalNumberDraft;
  previous_cgpa: OptionalNumberDraft;
  recent_score_percent: OptionalNumberDraft;
  attendance_percent: OptionalNumberDraft;
  submission_rate_percent: OptionalNumberDraft;
  weekly_study_hours: OptionalNumberDraft;
  confidence_level: OptionalNumberDraft;
  sleep_hours: OptionalNumberDraft;
  stress_level: OptionalNumberDraft;
  fatigue_level: OptionalNumberDraft;
  concentration_level: OptionalNumberDraft;
}

export interface StudentIntakePayload {
  primary_goal: StudentGoal;
  subjects: string[];
  course_type: StudentCourseType;
  current_term: number;
  current_credit_load: number | null;
  previous_cgpa: number | null;
  recent_score_percent: number | null;
  attendance_percent: number | null;
  submission_rate_percent: number | null;
  weekly_study_hours: number | null;
  confidence_level: number | null;
  sleep_hours: number | null;
  stress_level: number | null;
  fatigue_level: number | null;
  concentration_level: number | null;
}

export interface EvidenceSummary {
  evidence_mode: "self_reported_demo";
  institutional_data_connected: boolean;
  mapped_feature_count: number;
  unavailable_feature_count: number;
  coverage_percent: number;
  reliability: "limited" | "partial" | "institutional";
  source_labels: string[];
  message: string;
}

export interface StudentStudyPlanResponse {
  support_level: "standard_planning" | "review_recommended";
  alert: boolean;
  ranked_tasks: RankedTask[];
  sessions: PlannedSession[];
  unscheduled_minutes: Record<string, number>;
  recommendations: string[];
  evidence: EvidenceSummary;
  human_review_required: boolean;
}

export interface TaskDraft {
  task_id: string;
  title: string;
  subject: string;
  deadline: string;
  estimated_minutes: number;
  completed_minutes: number;
  difficulty: number;
  importance: number;
}

export interface AvailabilityDraft {
  start: string;
  end: string;
}
