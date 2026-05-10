export interface SubmissionData {
  submission_id: string;
  github_url: string;
  assignment_id: string | null;
  rubric_digest: string;
  status: string;
  local_repo_path: string;
  commit_hash: string;
}

export interface TestCase {
  name: string;
  status: 'passed' | 'failed' | 'error' | 'skipped';
  message: string | null;
}

export interface TestSummary {
  framework: string;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
  tests?: TestCase[];
}

export interface LanguageInfo {
  language: string;
  version: string | null;
  source: string | null;
  override_applied: boolean;
}

export type ScoreLevel =
  | 'NEEDS_HUMAN_REVIEW'
  | 'NEEDS_IMPROVEMENT'
  | 'WEAK'
  | 'ACCEPTABLE'
  | 'STRONG'
  | 'EXEMPLARY';

export interface RecommendationObject {
  file_path: string;
  line_range: { start: number; end: number };
  original_snippet: string;
  revised_snippet: string;
  diff: string;
  rationale?: string;
}

export interface CriterionReasoningDetails {
  score_reasoning: string;
  confidence_reasoning: string;
  evidence: string;
  uncertainty: string;
  limitations: string;
}

export interface CriterionScore {
  criterion_name: string;
  name?: string;
  score: number;
  level: ScoreLevel;
  rubric_standard?: string;
  rubric_weight?: string;
  justification: string;
  confidence: number;
  reasoning_details?: CriterionReasoningDetails;
  recommendation?: RecommendationObject;
  recommendations?: RecommendationObject[];
}

export interface AiFeedback {
  criteria_scores: CriterionScore[];
  flags: string[];
  metadata: {
    style_guide_version?: string | string[];
    language?: string;
  };
  recommendations: RecommendationObject[];
}

export interface CriterionOverride {
  criterion_name: string;
  level: ScoreLevel;
  score: number;
}

export interface EvaluationResult {
  deterministic_score: number | null;
  review_status?: string;
  instructor_notes?: string | null;
  override_grades?: CriterionOverride[] | null;
  student_comment?: string | null;
  ai_feedback?: AiFeedback | null;
  metadata?: {
    language: LanguageInfo | null;
    test_summary: TestSummary | null;
  };
}

export interface RubricLevel {
  label: string;
  points: number;
  description: string;
}

export interface RubricCriterion {
  name: string;
  max_points: number;
  levels: RubricLevel[];
}

// Shape returned by GET /api/v1/code-eval/submissions/:id
export interface SubmissionStatusData {
  submission_id: string;
  assignment_id: string | null;
  student_id: string;
  github_repo_url: string;
  commit_hash: string | null;
  status: string;
  created_at: string;
  evaluation?: EvaluationResult;
  rubric_criteria?: RubricCriterion[] | null;
}

export interface SubmissionStatusResponse {
  success: boolean;
  data: SubmissionStatusData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface SubmissionSummary {
  submission_id: string;
  assignment_id: string | null;
  student_id: string;
  student_email: string | null;
  student_name: string | null;
  github_repo_url: string;
  status: string;
  created_at: string;
  deterministic_score: number | null;
  ai_score: number | null;
}

export interface SubmissionListResponse {
  success: boolean;
  data: { submissions: SubmissionSummary[] } | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface ResponseMetadata {
  timestamp: string;
  module: string;
  version: string;
}

export interface ApiError {
  code: string;
  message: string;
}

export interface SubmissionResponse {
  success: boolean;
  data: SubmissionData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface ReviewRequest {
  action: 'approve' | 'override';
  override_grades?: CriterionOverride[];
  student_comment?: string;
  instructor_notes?: string;
}

export interface AssignmentData {
  assignment_id: string;
  title: string;
  instructor_id: string;
  test_suite_repo_url: string | null;
  rubric_id: string | null;
  enable_lint_review: boolean;
  language_override: string | null;
  submission_count: number;
}

export interface AssignmentListResponse {
  success: boolean;
  data: { assignments: AssignmentData[] } | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface AssignmentDetailResponse {
  success: boolean;
  data: AssignmentData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface DeleteResponse {
  success: boolean;
  data: { deleted: string } | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}

export interface GitHubSettingsData {
  connected: boolean;
  github_username: string | null;
  last_updated_at: string | null;
}

export interface GitHubSettingsResponse {
  success: boolean;
  data: GitHubSettingsData | null;
  error: ApiError | null;
  metadata: ResponseMetadata;
}
