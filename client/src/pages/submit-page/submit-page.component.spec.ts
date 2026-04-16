import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { of } from 'rxjs';

import { SubmitPageComponent } from './submit-page.component';
import { EvaluationService } from '../../services/evaluation.service';
import { SubmissionResponse } from '../../utils/api.types';

const METADATA = { timestamp: '', module: 'a1', version: '1.0.0' };

function makeSuccessResponse(submissionId = 'sub-id'): SubmissionResponse {
  return {
    success: true,
    error: null,
    metadata: METADATA,
    data: {
      submission_id: submissionId,
      github_url: 'https://github.com/owner/repo',
      assignment_id: 'assign-id',
      rubric_digest: 'abc',
      status: 'Pending',
      local_repo_path: '/tmp/repo',
      commit_hash: 'abc123',
    },
  };
}

function makeErrorResponse(code: string, message: string): SubmissionResponse {
  return { success: false, data: null, error: { code, message }, metadata: METADATA };
}

describe('SubmitPageComponent', () => {
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SubmitPageComponent],
      providers: [
        EvaluationService,
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    httpMock.verify();
  });

  function setup() {
    const fixture = TestBed.createComponent(SubmitPageComponent);
    fixture.detectChanges();
    return { fixture, component: fixture.componentInstance };
  }

  // ── Form validation ────────────────────────────────────────────────────────

  describe('form validation', () => {
    it('is invalid when empty', () => {
      const { component } = setup();
      expect(component.form.invalid).toBe(true);
    });

    it('accepts a valid GitHub URL', () => {
      const { component } = setup();
      component.form.controls.githubUrl.setValue('https://github.com/owner/repo');
      expect(component.form.controls.githubUrl.valid).toBe(true);
    });

    it('rejects a non-GitHub URL', () => {
      const { component } = setup();
      component.form.controls.githubUrl.setValue('https://gitlab.com/owner/repo');
      expect(component.form.controls.githubUrl.invalid).toBe(true);
    });

    it('rejects a plain string', () => {
      const { component } = setup();
      component.form.controls.githubUrl.setValue('not-a-url');
      expect(component.form.controls.githubUrl.invalid).toBe(true);
    });

    it('requires assignmentId to be non-empty', () => {
      const { component } = setup();
      component.form.controls.assignmentId.setValue('');
      expect(component.form.controls.assignmentId.invalid).toBe(true);
    });
  });

  // ── onSubmit ───────────────────────────────────────────────────────────────

  describe('onSubmit', () => {
    it('sets fileError when no file is selected', () => {
      const { component } = setup();
      component.form.controls.githubUrl.setValue('https://github.com/owner/repo');
      component.form.controls.assignmentId.setValue('some-id');
      component.selectedFile = null;

      component.onSubmit();

      expect(component.fileError).toBe(true);
    });

    it('marks all fields as touched when form is invalid', () => {
      const { component } = setup();
      const spy = vi.spyOn(component.form, 'markAllAsTouched');

      component.onSubmit();

      expect(spy).toHaveBeenCalled();
    });

    it('does not call the service when form is invalid', () => {
      const { component } = setup();
      const service = TestBed.inject(EvaluationService);
      const spy = vi.spyOn(service, 'submitEvaluation');

      component.onSubmit();

      expect(spy).not.toHaveBeenCalled();
    });

    it('navigates to /status/:id on a successful submission', () => {
      const { component } = setup();
      const service = TestBed.inject(EvaluationService);
      const router = TestBed.inject(Router);
      const navSpy = vi.spyOn(router, 'navigate');

      vi.spyOn(service, 'submitEvaluation').mockReturnValue(of(makeSuccessResponse('returned-sub-id')));

      component.form.controls.githubUrl.setValue('https://github.com/owner/repo');
      component.form.controls.assignmentId.setValue('assign-id');
      component.selectedFile = new File(['rubric'], 'rubric.txt');

      component.onSubmit();

      expect(navSpy).toHaveBeenCalledWith(
        ['/status', 'returned-sub-id'],
        expect.objectContaining({ state: expect.anything() }),
      );
    });

    it('sets errorMessage on a failure response', () => {
      const { component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'submitEvaluation').mockReturnValue(
        of(makeErrorResponse('VALIDATION_ERROR', 'Bad GitHub URL')),
      );

      component.form.controls.githubUrl.setValue('https://github.com/owner/repo');
      component.form.controls.assignmentId.setValue('assign-id');
      component.selectedFile = new File(['rubric'], 'rubric.txt');

      component.onSubmit();

      expect(component.errorMessage).toBe('Bad GitHub URL');
    });

    it('resets submitting to false after the response', () => {
      const { component } = setup();
      const service = TestBed.inject(EvaluationService);

      vi.spyOn(service, 'submitEvaluation').mockReturnValue(
        of(makeErrorResponse('ERR', 'error')),
      );

      component.form.controls.githubUrl.setValue('https://github.com/owner/repo');
      component.form.controls.assignmentId.setValue('assign-id');
      component.selectedFile = new File(['rubric'], 'rubric.txt');

      component.onSubmit();

      expect(component.submitting).toBe(false);
    });
  });
});
