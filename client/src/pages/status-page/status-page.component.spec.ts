import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute } from '@angular/router';
import { provideRouter } from '@angular/router';
import { of, Subject } from 'rxjs';

import { StatusPageComponent } from './status-page.component';
import { EvaluationService } from '../../services/evaluation.service';
import { SubmissionStatusResponse } from '../../utils/api.types';

const SUBMISSION_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const STATUS_URL = `http://localhost:8000/api/v1/code-eval/submissions/${SUBMISSION_ID}`;
const METADATA = { timestamp: '2026-04-15T00:00:00Z', module: 'a1', version: '1.0.0' };

const MOCK_EVALUATION = {
  deterministic_score: 85,
  ai_feedback: { summary: 'Great work overall.' },
  metadata: {
    language: { language: 'python', version: '3.12', source: 'pyproject.toml', override_applied: false },
    test_summary: { framework: 'pytest', passed: 8, failed: 2, errors: 1, skipped: 1 },
  },
};

function makeStatusData(status: string, evaluation?: typeof MOCK_EVALUATION) {
  return {
    submission_id: SUBMISSION_ID,
    assignment_id: null,
    student_id: 'student-id',
    github_repo_url: 'https://github.com/owner/repo',
    commit_hash: 'abc123',
    status,
    created_at: '2026-04-15T00:00:00Z',
    ...(evaluation ? { evaluation } : {}),
  };
}

function makeResponse(status: string, evaluation?: typeof MOCK_EVALUATION): SubmissionStatusResponse {
  return { success: true, error: null, metadata: METADATA, data: makeStatusData(status, evaluation) };
}

function makeErrorResponse(): SubmissionStatusResponse {
  return {
    success: false,
    data: null,
    error: { code: 'NOT_FOUND', message: 'Submission not found' },
    metadata: METADATA,
  };
}

describe('StatusPageComponent', () => {
  let httpMock: HttpTestingController;

  function setup(submissionId: string | null = SUBMISSION_ID) {
    TestBed.configureTestingModule({
      imports: [StatusPageComponent],
      providers: [
        EvaluationService,
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: { get: (_key: string) => submissionId } } },
        },
      ],
    });
    httpMock = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(StatusPageComponent);
    return { fixture, component: fixture.componentInstance };
  }

  afterEach(() => {
    vi.restoreAllMocks();
    httpMock.verify();
  });

  // ── Polling lifecycle ──────────────────────────────────────────────────────

  describe('polling', () => {
    it('issues a GET on init when submissionId is present', () => {
      const { fixture } = setup();
      fixture.detectChanges();

      // Flush so httpMock.verify() passes
      httpMock.expectOne(STATUS_URL).flush(makeResponse('Pending'));
      // Discard in-flight interval without advancing time
      clearInterval(fixture.componentInstance['pollTimer'] ?? undefined);
    });

    it('does not make any request when submissionId is absent', () => {
      const { fixture } = setup(null);
      fixture.detectChanges();

      httpMock.expectNone(STATUS_URL);
    });

    it('calls getSubmissionStatus again after the poll interval fires', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      // Stub so we control when responses arrive
      let callCount = 0;
      vi.spyOn(service, 'getSubmissionStatus').mockImplementation(() => {
        callCount += 1;
        return of(makeResponse('Processing'));
      });

      fixture.detectChanges(); // ngOnInit → first call

      expect(callCount).toBe(1);

      // Manually fire the interval callback once (simulates a tick)
      const pollTimer = (component as unknown as { pollTimer: ReturnType<typeof setInterval> }).pollTimer;
      // Trigger the interval by forcing the component to call fetchStatus again
      (component as unknown as { fetchStatus: () => void }).fetchStatus();

      expect(callCount).toBe(2);

      clearInterval(pollTimer);
    });

    it('clears the interval when status is Completed', () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Completed')));

      fixture.detectChanges();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });

    it('clears the interval when status is Failed', () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Failed')));

      fixture.detectChanges();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });

    it('sets pollError and clears the interval on API error', () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeErrorResponse()));

      fixture.detectChanges();

      expect(component.pollError).toBe('Submission not found');
      expect(clearIntervalSpy).toHaveBeenCalled();
    });

    it('clears the interval on destroy', () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Pending')));

      fixture.detectChanges();
      fixture.destroy();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });

  // ── testSummary getter ─────────────────────────────────────────────────────

  describe('testSummary getter', () => {
    it('returns null when there is no evaluation', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Pending')));

      fixture.detectChanges();

      expect(component.testSummary).toBeNull();

      clearInterval((component as unknown as { pollTimer: ReturnType<typeof setInterval> }).pollTimer);
    });

    it('returns null when evaluation has no metadata', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const evalNoMeta: any = { deterministic_score: 70, ai_feedback: null };
      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(
        of(makeResponse('Completed', evalNoMeta)),
      );

      fixture.detectChanges();

      expect(component.testSummary).toBeNull();
    });

    it('returns the test_summary object when evaluation is present', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Completed', MOCK_EVALUATION)));

      fixture.detectChanges();

      expect(component.testSummary).toEqual({
        framework: 'pytest',
        passed: 8,
        failed: 2,
        errors: 1,
        skipped: 1,
      });
    });
  });

  // ── totalTests getter ──────────────────────────────────────────────────────

  describe('totalTests getter', () => {
    it('returns 0 when there is no test summary', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Pending')));

      fixture.detectChanges();

      expect(component.totalTests).toBe(0);

      clearInterval((component as unknown as { pollTimer: ReturnType<typeof setInterval> }).pollTimer);
    });

    it('sums passed + failed + errors + skipped', () => {
      const { fixture, component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Completed', MOCK_EVALUATION)));

      fixture.detectChanges();

      expect(component.totalTests).toBe(12); // 8 + 2 + 1 + 1
    });
  });

  // ── Template rendering ─────────────────────────────────────────────────────

  describe('template', () => {
    it('shows the loading state before the first response', () => {
      const { fixture } = setup();

      // Stub so no response arrives, leaving the component in the loading state
      const service = TestBed.inject(EvaluationService);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(new Subject());

      fixture.detectChanges();

      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('Loading submission');
      expect(text).toContain(SUBMISSION_ID);

      // Clean up interval (response never arrived so polling is still running)
      clearInterval(
        (fixture.componentInstance as unknown as { pollTimer: ReturnType<typeof setInterval> }).pollTimer,
      );
    });

    it('renders submission data after a successful response', () => {
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Completed')));

      fixture.detectChanges();

      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain(SUBMISSION_ID);
      expect(text).toContain('Completed');
      expect(text).toContain('https://github.com/owner/repo');
    });

    it('renders the poll error when the API fails', () => {
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeErrorResponse()));

      fixture.detectChanges();

      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('Submission not found');
    });

    it('renders score, test counts, framework, and AI feedback', () => {
      const { fixture } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'getSubmissionStatus').mockReturnValue(of(makeResponse('Completed', MOCK_EVALUATION)));

      fixture.detectChanges();

      const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
      expect(text).toContain('85');                   // deterministic_score
      expect(text).toContain('8');                    // passed
      expect(text).toContain('2');                    // failed
      expect(text).toContain('pytest');               // framework
      expect(text).toContain('Great work overall.');  // ai_feedback.summary
    });
  });
});
