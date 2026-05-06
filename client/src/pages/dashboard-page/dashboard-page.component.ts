import { Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Router } from '@angular/router';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import { AVATAR_TINTS, StudentInfo, deriveStudent, formatDate } from '../../utils/student-display.util';
import { EvaluationService } from '../../services/evaluation.service';
import { SubmissionSummary } from '../../utils/api.types';

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
  imports: [RouterLink],
  templateUrl: './dashboard-page.component.html',
})
export class DashboardPageComponent {
  readonly view = signal<'table' | 'cards'>('table');
  readonly searchQuery = signal('');
  readonly filter = signal('all');
  readonly avatarTints = AVATAR_TINTS;

  private readonly _loaded = signal<{
    submissions: Submission[];
    error: string | null;
  } | null>(null);

  readonly loading = computed(() => this._loaded() === null);
  readonly loadError = computed(() => this._loaded()?.error ?? null);
  readonly allSubmissions = computed(() => this._loaded()?.submissions ?? []);
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

  constructor(private router: Router, private evalService: EvaluationService) {
    this.evalService.getSubmissions().subscribe((res) => {
      if (!res.success || !res.data) {
        this._loaded.set({ submissions: [], error: res.error?.message ?? 'Failed to load submissions.' });
        return;
      }
      this._loaded.set({
        submissions: res.data.submissions.map((s): Submission => ({
          id: s.submission_id,
          student: deriveStudent(s),
          github: s.github_repo_url,
          status: s.status,
          score: s.deterministic_score,
          submitted: formatDate(s.created_at),
        })),
        error: null,
      });
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
}
