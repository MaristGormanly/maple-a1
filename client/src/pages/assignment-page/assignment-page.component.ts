import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AssignmentService } from '../../services/assignment.service';

@Component({
  selector: 'app-assignment-page',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './assignment-page.component.html',
})
export class AssignmentPageComponent {
  private assignments = inject(AssignmentService);

  title = 'CMPT 220 / HW6 — Graph Algorithms';
  testSuiteRepoUrl = 'https://github.com/cmpt220-marist/hw6-tests';
  languageOverride = '';
  rubricId = '';
  enableLintReview = true;

  saving = false;
  saved = false;
  errorMessage: string | null = null;
  createdAssignmentId: string | null = null;

  create(): void {
    if (this.saving) return;
    if (!this.title.trim() || !this.testSuiteRepoUrl.trim()) {
      this.errorMessage = 'Title and test suite repository are required.';
      return;
    }
    if (this.rubricId && !this.isValidUuid(this.rubricId)) {
      this.errorMessage = 'Rubric ID must be a valid UUID (or left blank).';
      return;
    }

    this.saving = true;
    this.errorMessage = null;

    this.assignments
      .create({
        title: this.title.trim(),
        test_suite_repo_url: this.testSuiteRepoUrl.trim() || null,
        rubric_id: this.rubricId.trim() || null,
        enable_lint_review: this.enableLintReview,
        language_override: this.languageOverride.trim() || null,
      })
      .subscribe((response) => {
        this.saving = false;
        if (response.success && response.data) {
          this.saved = true;
          this.createdAssignmentId = response.data.assignment_id;
        } else {
          this.errorMessage =
            response.error?.message ?? 'Could not create the assignment.';
        }
      });
  }

  copyId(): void {
    if (this.createdAssignmentId) {
      navigator.clipboard?.writeText(this.createdAssignmentId);
    }
  }

  private isValidUuid(value: string): boolean {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
  }
}
