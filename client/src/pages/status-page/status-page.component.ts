import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { EvaluationService } from '../../services/evaluation.service';
import { SubmissionData, SubmissionStatusData, TestSummary } from '../../utils/api.types';

// Polling stops when status reaches one of these terminal values.
const TERMINAL_STATUSES = new Set(['Completed', 'Failed']);

const POLL_INTERVAL_MS = 3000;

@Component({
  selector: 'app-status-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './status-page.component.html',
})
export class StatusPageComponent implements OnInit, OnDestroy {
  // Data passed via router state from the POST /evaluate response (M1 shape).
  data: SubmissionData | null = null;

  // Data fetched via GET /submissions/:id (M2 shape).
  statusData: SubmissionStatusData | null = null;

  submissionId: string | null = null;
  pollError: string | null = null;

  private pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private route: ActivatedRoute,
    private evaluationService: EvaluationService,
  ) {}

  ngOnInit(): void {
    this.submissionId = this.route.snapshot.paramMap.get('id');

    const state = history.state as { data?: SubmissionData };
    this.data = state?.data ?? null;

    if (this.submissionId) {
      this.fetchStatus();
      this.pollTimer = setInterval(() => {
        if (!this.isPolling()) {
          this.stopPolling();
          return;
        }
        this.fetchStatus();
      }, POLL_INTERVAL_MS);
    }
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  private fetchStatus(): void {
    if (!this.submissionId) return;

    this.evaluationService.getSubmissionStatus(this.submissionId).subscribe((response) => {
      if (response.success && response.data) {
        this.statusData = response.data;
        this.pollError = null;
        if (!this.isPolling()) {
          this.stopPolling();
        }
      } else {
        this.pollError = response.error?.message ?? 'Failed to fetch submission status.';
        this.stopPolling();
      }
    });
  }

  private isPolling(): boolean {
    return this.statusData === null || !TERMINAL_STATUSES.has(this.statusData.status);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  get testSummary(): TestSummary | null {
    return this.statusData?.evaluation?.metadata?.test_summary ?? null;
  }

  get totalTests(): number {
    const s = this.testSummary;
    if (!s) return 0;
    return s.passed + s.failed + s.errors + s.skipped;
  }

  abbrev(value: string): string {
    return value.slice(0, 12);
  }
}
