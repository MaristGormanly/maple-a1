import { Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Router } from '@angular/router';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import { AVATAR_TINTS, StudentInfo, deriveStudent, formatDate } from '../../utils/student-display.util';
import { EvaluationService } from '../../services/evaluation.service';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';

interface Submission {
  id: string;
  student: StudentInfo;
  github: string;
  status: string;
  score: number | null;
  submitted: string;
}

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [RouterLink, ConfirmDialogComponent],
  templateUrl: './dashboard-page.component.html',
})
export class DashboardPageComponent {
  readonly view = signal<'table' | 'cards'>('table');
  readonly searchQuery = signal('');
  readonly filter = signal('all');
  readonly avatarTints = AVATAR_TINTS;

  private readonly _loadError = signal<string | null>(null);
  private readonly _loaded = signal(false);
  private readonly _submissions = signal<Submission[]>([]);

  readonly loading = computed(() => !this._loaded());
  readonly loadError = computed(() => this._loadError());
  readonly allSubmissions = computed(() => this._submissions());
  readonly filtered = computed(() => {
    const f = this.filter();
    const needle = this.searchQuery().toLowerCase();
    return this.allSubmissions().filter((r) => {
      if (f !== 'all' && displayStatus(r.status) !== f) return false;
      if (needle) {
        const haystack = [r.student.name, r.student.email, r.github, r.id]
          .join(' ').toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
  });

  readonly showDeleteDialog = signal(false);
  readonly pendingDeleteId = signal<string | null>(null);
  readonly deleteLoading = signal(false);

  constructor(private router: Router, private evalService: EvaluationService) {
    this.evalService.getSubmissions().subscribe((res) => {
      this._loaded.set(true);
      if (!res.success || !res.data) {
        this._loadError.set(res.error?.message ?? 'Failed to load submissions.');
        return;
      }
      this._submissions.set(res.data.submissions.map((s): Submission => ({
        id: s.submission_id,
        student: deriveStudent(s),
        github: s.github_repo_url,
        status: s.status,
        score: s.ai_score ?? s.deterministic_score,
        submitted: formatDate(s.created_at),
      })));
    });
  }

  get latestAssignmentId(): string | null {
    return localStorage.getItem('maple.latestAssignmentId');
  }

  onSearch(e: Event): void {
    this.searchQuery.set((e.target as HTMLInputElement).value);
  }

  avatarColor(tint: number): string {
    return this.avatarTints[tint % this.avatarTints.length];
  }

  displayStatus(raw: string): string {
    return displayStatus(raw);
  }

  badgeTone(status: string): string {
    return badgeTone(status);
  }

  viewStatus(r: Submission): void {
    this.router.navigate(['/status', r.id], {
      state: { studentLabel: r.student.name },
    });
  }

  copyId(id: string): void {
    navigator.clipboard?.writeText(id);
  }

  openDeleteDialog(id: string, event: Event): void {
    event.stopPropagation();
    this.pendingDeleteId.set(id);
    this.showDeleteDialog.set(true);
  }

  onDeleteConfirmed(): void {
    const id = this.pendingDeleteId();
    if (!id) return;
    this.deleteLoading.set(true);
    this.evalService.deleteSubmission(id).subscribe(res => {
      this.deleteLoading.set(false);
      if (res.success) {
        this._submissions.update(list => list.filter(s => s.id !== id));
        this.showDeleteDialog.set(false);
        this.pendingDeleteId.set(null);
      }
    });
  }

  onDeleteCancelled(): void {
    this.showDeleteDialog.set(false);
    this.pendingDeleteId.set(null);
  }
}
