import { Component, inject, signal } from '@angular/core';
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

  readonly saving = signal(false);
  readonly saved = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly createdAssignmentId = signal<string | null>(null);

  create(): void {
    if (this.saving()) return;
    if (!this.title.trim() || !this.testSuiteRepoUrl.trim()) {
      this.errorMessage.set('Title and test suite repository are required.');
      return;
    }
    if (this.rubricId && !this.isValidUuid(this.rubricId)) {
      this.errorMessage.set('Rubric ID must be a valid UUID (or left blank).');
      return;
    }

    this.saving.set(true);
    this.errorMessage.set(null);

    this.assignments
      .create({
        title: this.title.trim(),
        test_suite_repo_url: this.testSuiteRepoUrl.trim() || null,
        rubric_id: this.rubricId.trim() || null,
        enable_lint_review: this.enableLintReview,
        language_override: this.languageOverride.trim() || null,
      })
      .subscribe((response) => {
        this.saving.set(false);
        if (response.success && response.data) {
          this.saved.set(true);
          this.createdAssignmentId.set(response.data.assignment_id);
        } else {
          this.errorMessage.set(
            response.error?.message ?? 'Could not create the assignment.',
          );
        }
      });
  }

  copyId(): void {
    const id = this.createdAssignmentId();
    if (id) {
      navigator.clipboard?.writeText(id);
    }
  }

  private isValidUuid(value: string): boolean {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
  }
}
