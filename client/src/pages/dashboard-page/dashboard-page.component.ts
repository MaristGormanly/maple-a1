import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Router } from '@angular/router';
import { badgeTone, displayStatus } from '../../utils/status-display.util';

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

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard-page.component.html',
})
export class DashboardPageComponent {
  view: 'table' | 'cards' = 'table';
  searchQuery = '';
  filter = 'all';
  allSubmissions: Submission[] = [];
  avatarTints = AVATAR_TINTS;

  constructor(private router: Router) { }

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
