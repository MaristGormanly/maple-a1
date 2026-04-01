import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, catchError, of } from 'rxjs';

import { environment } from '../environments/environment';
import { SubmissionResponse } from '../utils/api.types';

@Injectable({ providedIn: 'root' })
export class EvaluationService {
  private readonly url = `${environment.apiBaseUrl}/api/v1/code-eval/evaluate`;

  constructor(private http: HttpClient) {}

  // TODO: Replace devToken stub with a real token from the auth service once
  // POST /api/v1/code-eval/auth/login is implemented (Milestone 2).
  submitEvaluation(
    githubUrl: string,
    assignmentId: string | null,
    rubricFile: File
  ): Observable<SubmissionResponse> {
    const body = new FormData();
    body.append('github_url', githubUrl);
    if (assignmentId) {
      body.append('assignment_id', assignmentId);
    }
    body.append('rubric', rubricFile);

    // Do not set Content-Type manually — the browser sets multipart/form-data
    // with the correct boundary automatically when the body is FormData.
    const headers = new HttpHeaders({
      Authorization: `Bearer ${environment.devToken}`,
    });

    return this.http.post<SubmissionResponse>(this.url, body, { headers }).pipe(
      catchError((err) => {
        const message: string =
          err?.error?.error?.message ?? err?.message ?? 'Unknown error';
        const code: string = err?.error?.error?.code ?? 'NETWORK_ERROR';
        const response: SubmissionResponse = {
          success: false,
          data: null,
          error: { code, message },
          metadata: {
            timestamp: new Date().toISOString(),
            module: 'a1',
            version: 'unknown',
          },
        };
        return of(response);
      })
    );
  }
}
