import { ChangeDetectorRef, Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { FormsModule } from '@angular/forms';

import { EvaluationService } from '../../services/evaluation.service';
import {
  CriterionOverride, CriterionScore, LanguageInfo, RecommendationObject, ReviewRequest,
  RubricCriterion, ScoreLevel, StyleFinding, SubmissionData, SubmissionStatusData, TestCase, TestSummary,
} from '../../utils/api.types';
import { CriteriaScoresComponent } from '../../components/criteria-scores/criteria-scores.component';
import { DiffViewerComponent } from '../../components/diff-viewer/diff-viewer.component';
import { StyleFindingsComponent } from '../../components/style-findings/style-findings.component';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';
import { badgeTone, displayStatus } from '../../utils/status-display.util';

const TERMINAL_STATUSES = new Set(['Completed', 'Failed', 'Awaiting Review', 'Overridden', 'EVALUATION_FAILED']);
const POLL_INTERVAL_MS = 3000;

interface PipelineStage {
  key: string;
  label: string;
  hint: string;
  done: boolean;
  active: boolean;
  failed: boolean;
}

@Component({
  selector: 'app-status-page',
  standalone: true,
  imports: [FormsModule, CriteriaScoresComponent, DiffViewerComponent, ConfirmDialogComponent, StyleFindingsComponent],
  templateUrl: './status-page.component.html',
})
export class StatusPageComponent implements OnInit, OnDestroy {
  data: SubmissionData | null = null;
  statusData: SubmissionStatusData | null = null;
  submissionId: string | null = null;
  studentLabel: string | null = null;
  pollError: string | null = null;

  activeTab: 'scores' | 'diff' | 'style' = 'scores';
  showDeleteDialog = false;
  showTestCases = false;
  deleteLoading = false;
  showOverrideInput = false;
  overrideNotes = '';
  overrideStudentComment = '';
  overrideRows: CriterionOverride[] = [];
  reviewSubmitting = false;
  reviewError: string | null = null;
  reviewRecorded = false;

  readonly scoreLevels: ScoreLevel[] = [
    'NEEDS_IMPROVEMENT',
    'WEAK',
    'ACCEPTABLE',
    'STRONG',
    'EXEMPLARY',
  ];
  readonly levelScores: Partial<Record<ScoreLevel, number>> = {
    NEEDS_IMPROVEMENT: 50,
    WEAK: 62.5,
    ACCEPTABLE: 75,
    STRONG: 87.5,
    EXEMPLARY: 100,
  };

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private route: ActivatedRoute,
    private evaluationService: EvaluationService,
    public router: Router,
    private cdr: ChangeDetectorRef,
  ) { }

  ngOnInit(): void {
    this.submissionId = this.route.snapshot.paramMap.get('id');
    const state = history.state as { data?: SubmissionData; statusData?: SubmissionStatusData; studentLabel?: string };
    this.data = state?.data ?? null;
    this.studentLabel = state?.studentLabel ?? null;

    if (state?.statusData) {
      this.statusData = state.statusData;
    } else if (this.data) {
      // Seed statusData from the submit response so the UI renders the
      // Pending badge / processing card immediately instead of stalling on
      // "Loading submission…" until the first poll lands.
      this.statusData = this.deriveStatusDataFromSubmit(this.data);
    }

    if (this.submissionId && this.isPolling()) {
      this.fetchStatus();
      this.pollTimer = setInterval(() => {
        if (!this.isPolling()) { this.stopPolling(); return; }
        this.fetchStatus();
      }, POLL_INTERVAL_MS);
    }
  }

  private deriveStatusDataFromSubmit(data: SubmissionData): SubmissionStatusData {
    return {
      submission_id: data.submission_id,
      assignment_id: data.assignment_id,
      student_id: '',
      github_repo_url: data.github_url,
      commit_hash: data.commit_hash,
      status: data.status,
      created_at: new Date().toISOString(),
    };
  }

  ngOnDestroy(): void { this.stopPolling(); }

  private fetchStatus(): void {
    if (!this.submissionId) return;
    this.evaluationService.getSubmissionStatus(this.submissionId).subscribe({
      next: (response) => {
        if (response.success && response.data) {
          this.statusData = response.data;
          this.pollError = null;
          this.cdr.detectChanges();
          if (!this.isPolling()) this.stopPolling();
        } else {
          this.pollError = response.error?.message ?? 'Failed to fetch submission status.';
          this.cdr.detectChanges();
          this.stopPolling();
        }
      },
    });
  }

  isPolling(): boolean {
    return this.statusData === null || !TERMINAL_STATUSES.has(this.statusData.status);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) { clearInterval(this.pollTimer); this.pollTimer = null; }
  }

  get status(): string { return this.statusData?.status ?? 'Pending'; }

  get displayStatus(): string {
    return displayStatus(this.status);
  }

  get instructorNotes(): string | null {
    return this.statusData?.evaluation?.instructor_notes ?? null;
  }

  get isOverridden(): boolean {
    return this.status === 'Overridden';
  }

  get overrideGrades(): CriterionOverride[] {
    return this.statusData?.evaluation?.override_grades ?? [];
  }

  get studentComment(): string | null {
    return this.statusData?.evaluation?.student_comment ?? null;
  }
  get score(): number {
    const criteria = this.statusData?.evaluation?.ai_feedback?.criteria_scores ?? [];
    if (criteria.length > 0) {
      const avg = criteria.reduce((sum: number, c: any) => sum + (c.score ?? 0), 0) / criteria.length;
      return Math.round(avg);
    }
    return Math.round(this.statusData?.evaluation?.deterministic_score ?? 0);
  }

  get testSummary(): TestSummary | null {
    return this.statusData?.evaluation?.metadata?.test_summary ?? null;
  }

  get testCases(): TestCase[] {
    return this.statusData?.evaluation?.metadata?.test_summary?.tests ?? [];
  }

  get totalTests(): number {
    const s = this.testSummary;
    return s ? s.passed + s.failed + s.errors + s.skipped : 0;
  }

  get criteriaScores(): CriterionScore[] {
    return this.statusData?.evaluation?.ai_feedback?.criteria_scores ?? [];
  }

  get rubricCriteria(): RubricCriterion[] {
    return this.statusData?.rubric_criteria ?? [];
  }

  get recommendations(): RecommendationObject[] {
    return this.statusData?.evaluation?.ai_feedback?.recommendations ?? [];
  }

  get styleFindings(): StyleFinding[] {
    return this.statusData?.evaluation?.ai_feedback?.style_findings ?? [];
  }

  get languageInfo(): LanguageInfo | null {
    return this.statusData?.evaluation?.metadata?.language ?? null;
  }

  get styleGuideVersions(): string[] {
    const v = this.statusData?.evaluation?.ai_feedback?.metadata?.style_guide_version;
    if (!v) return [];
    return Array.isArray(v) ? v : [v];
  }

  get showReviewPanel(): boolean {
    return (
      this.statusData?.status === 'Awaiting Review' &&
      this.statusData?.evaluation?.review_status === 'pending'
    );
  }

  get hasEvaluation(): boolean {
    return !!this.statusData?.evaluation;
  }

  get isError(): boolean {
    return this.status === 'Failed' || this.status === 'EVALUATION_FAILED';
  }

  get isCompleted(): boolean {
    return (
      this.status === 'Completed' ||
      this.status === 'Awaiting Review' ||
      this.status === 'Overridden'
    );
  }

  get failedStageKey(): string | null {
    if (this.status === 'EVALUATION_FAILED') return 'llm';
    if (this.status !== 'Failed') return null;
    if (!this.statusData?.commit_hash) return 'clone';
    if (!this.statusData?.evaluation) return 'sandbox';
    return 'sandbox';
  }

  get isInactivePipeline(): boolean {
    return this.status === 'Failed' || this.status === 'EVALUATION_FAILED';
  }

  get pipelineStages(): PipelineStage[] {
    const s = this.status;
    const failed = this.failedStageKey;
    const doneSet = (statuses: string[]) => statuses.includes(s);
    return [
      {
        key: 'clone', label: 'Clone & preprocess', hint: 'Stripped .git, node_modules, binaries',
        done: doneSet(['Cloned', 'Cached', 'Testing', 'Evaluating', 'Awaiting Review', 'Completed']),
        active: s === 'Pending',
        failed: failed === 'clone',
      },
      {
        key: 'cache', label: 'Cache lookup', hint: 'Checking commit::rubric digest',
        done: doneSet(['Cached', 'Testing', 'Evaluating', 'Awaiting Review', 'Completed']),
        active: s === 'Cloned',
        failed: failed === 'cache',
      },
      {
        key: 'sandbox', label: 'Sandbox test run', hint: 'Running test suite in Docker sandbox',
        done: doneSet(['Evaluating', 'Awaiting Review', 'Completed']),
        active: s === 'Testing',
        failed: failed === 'sandbox',
      },
      {
        key: 'llm', label: 'AI evaluation', hint: 'Reconciling tests against rubric, drafting feedback',
        done: doneSet(['Awaiting Review', 'Completed']),
        active: s === 'Evaluating',
        failed: failed === 'llm',
      },
      {
        key: 'review', label: 'Awaiting your review', hint: 'Feedback held until you approve',
        done: s === 'Completed' || s === 'Overridden',
        active: s === 'Awaiting Review',
        failed: false,
      },
    ];
  }

  get scoreRingProps() {
    const size = 52, stroke = 6;
    const r = (size - stroke) / 2;
    const c = 2 * Math.PI * r;
    const pct = Math.min(Math.max(this.score, 0), 100) / 100;
    return { r, c, offset: c - pct * c, cx: size / 2, cy: size / 2, size, stroke };
  }

  abbrev(value: string): string { return value.slice(0, 12); }

  scoreForLevel(level: string): number | null {
    return this.levelScores[level as ScoreLevel] ?? null;
  }

  onApprove(): void { this.submitReview({ action: 'approve' }); }

  onOverrideOpen(): void {
    this.overrideRows = this.criteriaScores.map(c => ({
      criterion_name: c.criterion_name,
      level: (c.level === 'NEEDS_HUMAN_REVIEW' ? 'ACCEPTABLE' : c.level) as ScoreLevel,
      score: c.score,
    }));
    this.overrideStudentComment = '';
    this.overrideNotes = '';
    this.showOverrideInput = true;
    this.reviewError = null;
  }

  onOverrideCancel(): void {
    this.showOverrideInput = false;
    this.overrideRows = [];
    this.overrideNotes = '';
    this.overrideStudentComment = '';
  }

  onOverrideSubmit(): void {
    this.submitReview({
      action: 'override',
      override_grades: this.overrideRows,
      student_comment: this.overrideStudentComment || undefined,
      instructor_notes: this.overrideNotes || undefined,
    });
  }

  private submitReview(request: ReviewRequest): void {
    if (!this.submissionId || this.reviewSubmitting) return;
    this.reviewSubmitting = true;
    this.reviewError = null;
    this.evaluationService.submitReview(this.submissionId, request).subscribe((response) => {
      this.reviewSubmitting = false;
      if (response.success && response.data) {
        this.statusData = response.data;
        this.showOverrideInput = false;
        this.overrideRows = [];
        this.overrideNotes = '';
        this.overrideStudentComment = '';
        this.reviewRecorded = true;
      } else {
        this.reviewError = response.error?.message ?? 'Review action failed.';
      }
      this.cdr.detectChanges();
    });
  }

  badgeTone(status: string): string {
    return badgeTone(status);
  }

  onDeleteOpen(): void {
    this.showDeleteDialog = true;
  }

  onDeleteCancelled(): void {
    this.showDeleteDialog = false;
  }

  onDeleteConfirmed(): void {
    if (!this.submissionId) return;
    this.deleteLoading = true;
    this.evaluationService.deleteSubmission(this.submissionId).subscribe(res => {
      this.deleteLoading = false;
      if (res.success) {
        this.stopPolling();
        this.router.navigate(['/dashboard']);
      }
      this.cdr.detectChanges();
    });
  }
}
