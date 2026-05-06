import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { AssignmentService } from '../../services/assignment.service';
import { EvaluationService } from '../../services/evaluation.service';
import { AssignmentData } from '../../utils/api.types';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import { AVATAR_TINTS, StudentInfo, deriveStudent, formatDate } from '../../utils/student-display.util';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';

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
  imports: [RouterLink, ConfirmDialogComponent],
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
    error: string | null;
  } | null>(null);
  private readonly _submissions = signal<SubmissionRow[]>([]);

  readonly loading = computed(() => this._loaded() === null);
  readonly loadError = computed(() => this._loaded()?.error ?? null);
  readonly assignment = computed(() => this._loaded()?.assignment ?? null);
  readonly submissions = computed(() => this._submissions());
  readonly filteredSubmissions = computed(() => {
    const needle = this.searchQuery().toLowerCase();
    if (!needle) return this._submissions();
    return this._submissions().filter(r =>
      [r.student.name, r.student.email, r.github, r.id].join(' ').toLowerCase().includes(needle));
  });

  readonly showAssignmentDeleteDialog = signal(false);
  readonly assignmentDeleteLoading = signal(false);

  readonly showSubmissionDeleteDialog = signal(false);
  readonly pendingSubmissionDeleteId = signal<string | null>(null);
  readonly submissionDeleteLoading = signal(false);

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
      this._loaded.set({ assignment: aData, error: aError });
      this._submissions.set(sRows);
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

  openAssignmentDeleteDialog(): void {
    this.showAssignmentDeleteDialog.set(true);
  }

  onAssignmentDeleteConfirmed(): void {
    const a = this.assignment();
    if (!a) return;
    this.assignmentDeleteLoading.set(true);
    this.assignmentService.delete(a.assignment_id).subscribe(res => {
      this.assignmentDeleteLoading.set(false);
      if (res.success) {
        this.router.navigate(['/assignments']);
      }
    });
  }

  openSubmissionDeleteDialog(id: string, event: Event): void {
    event.stopPropagation();
    this.pendingSubmissionDeleteId.set(id);
    this.showSubmissionDeleteDialog.set(true);
  }

  onSubmissionDeleteConfirmed(): void {
    const id = this.pendingSubmissionDeleteId();
    if (!id) return;
    this.submissionDeleteLoading.set(true);
    this.evalService.deleteSubmission(id).subscribe(res => {
      this.submissionDeleteLoading.set(false);
      if (res.success) {
        this._submissions.update(list => list.filter(r => r.id !== id));
        this.showSubmissionDeleteDialog.set(false);
        this.pendingSubmissionDeleteId.set(null);
      }
    });
  }
}
