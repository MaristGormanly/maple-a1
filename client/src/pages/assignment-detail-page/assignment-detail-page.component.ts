import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { AssignmentService } from '../../services/assignment.service';
import { EvaluationService } from '../../services/evaluation.service';
import { AssignmentData, SubmissionSummary } from '../../utils/api.types';
import { badgeTone, displayStatus } from '../../utils/status-display.util';
import {
  AVATAR_TINTS,
  StudentInfo,
  deriveStudent,
  formatDate,
} from '../../utils/student-display.util';

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
export class AssignmentDetailPageComponent implements OnInit {
  assignment: AssignmentData | null = null;
  submissions: SubmissionRow[] = [];
  loading = true;
  loadError: string | null = null;
  searchQuery = '';
  avatarTints = AVATAR_TINTS;

  constructor(
    private route: ActivatedRoute,
    public router: Router,
    private assignmentService: AssignmentService,
    private evalService: EvaluationService,
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    forkJoin({
      assignment: this.assignmentService.getById(id),
      submissions: this.evalService.getSubmissions(),
    }).subscribe(({ assignment, submissions }) => {
      this.loading = false;

      if (!assignment.success || !assignment.data) {
        this.loadError = assignment.error?.message ?? 'Assignment not found.';
        return;
      }
      this.assignment = assignment.data;

      if (submissions.success && submissions.data) {
        this.submissions = submissions.data.submissions
          .filter((s) => s.assignment_id === id)
          .map((s): SubmissionRow => ({
            id: s.submission_id,
            student: deriveStudent(s),
            github: s.github_repo_url,
            status: s.status,
            score: s.deterministic_score,
            submitted: formatDate(s.created_at),
          }));
      }
    });
  }

  get filteredSubmissions(): SubmissionRow[] {
    if (!this.searchQuery) return this.submissions;
    const needle = this.searchQuery.toLowerCase();
    return this.submissions.filter((r) => {
      const haystack = [r.student.name, r.student.email, r.github, r.id]
        .join(' ')
        .toLowerCase();
      return haystack.includes(needle);
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

  viewSubmission(r: SubmissionRow): void {
    this.router.navigate(['/status', r.id], {
      state: { studentLabel: r.student.name },
    });
  }
}
