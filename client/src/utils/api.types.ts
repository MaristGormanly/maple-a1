export interface SubmissionData {
  submission_id: string;
  github_url: string;
  assignment_id: string | null;
  rubric_digest: string;
  status: string;
  local_repo_path: string;
  commit_hash: string;
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
