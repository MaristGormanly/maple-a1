import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { EvaluationService } from './evaluation.service';
import { SubmissionStatusResponse } from '../utils/api.types';

const BASE = 'http://localhost:8000/api/v1/code-eval';
const SUBMISSION_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

const METADATA = { timestamp: '2026-04-15T00:00:00Z', module: 'a1', version: '1.0.0' };

function makeStatusResponse(status: string): SubmissionStatusResponse {
  return {
    success: true,
    error: null,
    metadata: METADATA,
    data: {
      submission_id: SUBMISSION_ID,
      assignment_id: null,
      student_id: 'student-id',
      github_repo_url: 'https://github.com/owner/repo',
      commit_hash: 'abc123',
      status,
      created_at: '2026-04-15T00:00:00Z',
    },
  };
}

describe('EvaluationService', () => {
  let service: EvaluationService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [EvaluationService, provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(EvaluationService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  // ── getSubmissionStatus ────────────────────────────────────────────────────

  describe('getSubmissionStatus', () => {
    it('makes a GET request to /submissions/:id', () => {
      service.getSubmissionStatus(SUBMISSION_ID).subscribe();

      const req = httpMock.expectOne(`${BASE}/submissions/${SUBMISSION_ID}`);
      expect(req.request.method).toBe('GET');
      req.flush(makeStatusResponse('Pending'));
    });

    it('returns the response data on success', () => {
      let result: SubmissionStatusResponse | undefined;
      service.getSubmissionStatus(SUBMISSION_ID).subscribe((r) => (result = r));

      httpMock
        .expectOne(`${BASE}/submissions/${SUBMISSION_ID}`)
        .flush(makeStatusResponse('Completed'));

      expect(result!.success).toBe(true);
      expect(result!.data!.status).toBe('Completed');
      expect(result!.data!.submission_id).toBe(SUBMISSION_ID);
    });

    it('returns a normalized error envelope on HTTP error', () => {
      let result: SubmissionStatusResponse | undefined;
      service.getSubmissionStatus(SUBMISSION_ID).subscribe((r) => (result = r));

      httpMock.expectOne(`${BASE}/submissions/${SUBMISSION_ID}`).flush(
        { success: false, data: null, error: { code: 'NOT_FOUND', message: 'Not found' }, metadata: METADATA },
        { status: 404, statusText: 'Not Found' },
      );

      expect(result!.success).toBe(false);
      expect(result!.data).toBeNull();
    });

    it('carries the Authorization header', () => {
      service.getSubmissionStatus(SUBMISSION_ID).subscribe();

      const req = httpMock.expectOne(`${BASE}/submissions/${SUBMISSION_ID}`);
      expect(req.request.headers.has('Authorization')).toBe(true);
      req.flush(makeStatusResponse('Pending'));
    });
  });

  // ── submitEvaluation ───────────────────────────────────────────────────────

  describe('submitEvaluation', () => {
    const file = () => new File(['rubric content'], 'rubric.txt', { type: 'text/plain' });

    it('makes a POST request to /evaluate', () => {
      service.submitEvaluation('https://github.com/owner/repo', 'assign-id', file()).subscribe();

      const req = httpMock.expectOne(`${BASE}/evaluate`);
      expect(req.request.method).toBe('POST');
      req.flush({ success: true, data: null, error: null, metadata: METADATA });
    });

    it('sends a FormData body', () => {
      service.submitEvaluation('https://github.com/owner/repo', 'assign-id', file()).subscribe();

      const req = httpMock.expectOne(`${BASE}/evaluate`);
      expect(req.request.body).toBeInstanceOf(FormData);
      req.flush({ success: true, data: null, error: null, metadata: METADATA });
    });

    it('returns a normalized error envelope on HTTP error', () => {
      let result: any;
      service.submitEvaluation('https://github.com/owner/repo', 'id', file()).subscribe((r) => (result = r));

      httpMock.expectOne(`${BASE}/evaluate`).flush(
        { success: false, data: null, error: { code: 'VALIDATION_ERROR', message: 'Bad URL' }, metadata: METADATA },
        { status: 400, statusText: 'Bad Request' },
      );

      expect(result.success).toBe(false);
      expect(result.error.code).toBe('VALIDATION_ERROR');
      expect(result.data).toBeNull();
    });
  });
});
