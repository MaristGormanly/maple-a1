import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { AssignmentService } from '../../services/assignment.service';
import { EvaluationService } from '../../services/evaluation.service';
import { AssignmentData, SubmissionSummary } from '../../utils/api.types';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import { AVATAR_TINTS, StudentInfo, deriveStudent, formatDate } from '../../utils/student-display.util';

interface SubmissionRow {
  id: string;
  student: StudentInfo;
  github: string;
  status: string;
  score: number | null;
  submitted: string;
}

@Component({
  selector: 'app-assignment-detail-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './assignment-detail-page.component.html',
})
export class AssignmentDetailPageComponent {
  private route = inject(ActivatedRoute);
  readonly router = inject(Router);
  private assignmentService = inject(AssignmentService);
  private evalService = inject(EvaluationService);

  readonly searchQuery = signal('');
  readonly avatarTints = AVATAR_TINTS;

  private readonly _loaded = signal<{
    assignment: AssignmentData | null;
    submissions: SubmissionRow[];
    error: string | null;
  } | null>(null);

  readonly loading = computed(() => this._loaded() === null);
  readonly loadError = computed(() => this._loaded()?.error ?? null);
  readonly assignment = computed(() => this._loaded()?.assignment ?? null);
  readonly submissions = computed(() => this._loaded()?.submissions ?? []);
  readonly filteredSubmissions = computed(() => {
    const needle = this.searchQuery().toLowerCase();
    if (!needle) return this.submissions();
    return this.submissions().filter(r =>
      [r.student.name, r.student.email, r.github, r.id].join(' ').toLowerCase().includes(needle));
  });

  constructor() {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    forkJoin({
      assignment: this.assignmentService.getById(id),
      submissions: this.evalService.getSubmissions(),
    }).subscribe(({ assignment, submissions }) => {
      const aData = assignment.success && assignment.data ? assignment.data : null;
      const aError = !assignment.success ? (assignment.error?.message ?? 'Assignment not found.') : null;
      const sRows: SubmissionRow[] = submissions.success && submissions.data
        ? submissions.data.submissions
            .filter(s => s.assignment_id === id)
            .map((s): SubmissionRow => ({
              id: s.submission_id,
              student: deriveStudent(s),
              github: s.github_repo_url,
              status: s.status,
              score: s.deterministic_score,
              submitted: formatDate(s.created_at),
            }))
        : [];
      this._loaded.set({ assignment: aData, submissions: sRows, error: aError });
    });
  }

  avatarColor(tint: number): string {
    return this.avatarTints[tint % this.avatarTints.length];
  }

  badgeClass(status: string): string {
    return `badge badge--${badgeTone(displayStatus(status))}`;
  }

  displayStatus(raw: string): string {
    return displayStatus(raw);
  }

  viewSubmission(r: SubmissionRow): void {
    this.router.navigate(['/status', r.id], { state: { studentLabel: r.student.name } });
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }
}
