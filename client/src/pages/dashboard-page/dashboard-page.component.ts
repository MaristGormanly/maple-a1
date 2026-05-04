import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Router } from '@angular/router';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import { EvaluationService } from '../../services/evaluation.service';
import { SubmissionSummary } from '../../utils/api.types';

interface Student {
  name: string;
  email: string;
  initials: string;
  tint: number;
}

interface Submission {
  id: string;
  student: Student;
  github: string;
  status: string;
  score: number | null;
  submitted: string;
}

const AVATAR_TINTS = [
  'oklch(0.6 0.12 265)',
  'oklch(0.6 0.12 155)',
  'oklch(0.62 0.14 55)',
  'oklch(0.58 0.14 25)',
  'oklch(0.55 0.12 315)',
  'oklch(0.6 0.12 195)',
  'oklch(0.55 0.13 85)',
  'oklch(0.58 0.14 355)',
];

function tintIndex(studentId: string): number {
  let sum = 0;
  for (let i = 0; i < studentId.length; i++) sum += studentId.charCodeAt(i);
  return sum % AVATAR_TINTS.length;
}

function deriveStudent(summary: SubmissionSummary): Student {
  const email = summary.student_email ?? summary.student_id;
  const prefix = email.split('@')[0];
  const name = prefix
    .replace(/[._-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const parts = name.trim().split(' ').filter(Boolean);
  const initials = parts.length >= 2
    ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
    : name.slice(0, 2).toUpperCase();
  return { name, email: summary.student_email ?? '', initials, tint: tintIndex(summary.student_id) };
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard-page.component.html',
})
export class DashboardPageComponent implements OnInit {
  view: 'table' | 'cards' = 'table';
  searchQuery = '';
  filter = 'all';
  allSubmissions: Submission[] = [];
  loading = true;
  loadError: string | null = null;
  avatarTints = AVATAR_TINTS;

  constructor(private router: Router, private evalService: EvaluationService) { }

  ngOnInit(): void {
    this.evalService.getSubmissions().subscribe((res) => {
      this.loading = false;
      if (!res.success || !res.data) {
        this.loadError = res.error?.message ?? 'Failed to load submissions.';
        return;
      }
      this.allSubmissions = res.data.submissions.map((s): Submission => ({
        id: s.submission_id,
        student: deriveStudent(s),
        github: s.github_repo_url,
        status: s.status,
        score: s.deterministic_score,
        submitted: formatDate(s.created_at),
      }));
    });
  }

  get latestSubmissionId(): string | null {
    return localStorage.getItem('maple.latestSubmissionId');
  }

  get latestAssignmentId(): string | null {
    return localStorage.getItem('maple.latestAssignmentId');
  }

  get filtered(): Submission[] {
    return this.allSubmissions.filter((r) => {
      if (this.filter !== 'all' && this.displayStatus(r.status) !== this.filter) return false;
      if (this.searchQuery) {
        const needle = this.searchQuery.toLowerCase();
        const haystack = [r.student.name, r.student.email, r.github, r.id].join(' ').toLowerCase();
        if (!haystack.includes(needle)) return false;
      }
      return true;
    });
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

  viewLatestSubmission(): void {
    if (this.latestSubmissionId) {
      this.router.navigate(['/status', this.latestSubmissionId]);
    }
  }

  copyId(id: string): void {
    navigator.clipboard?.writeText(id);
  }
}
