import { Component } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';

import { EvaluationService } from '../../services/evaluation.service';

@Component({
  selector: 'app-submit-page',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './submit-page.component.html',
})
export class SubmitPageComponent {
  form = new FormGroup({
    githubUrl: new FormControl('', [
      Validators.required,
      Validators.pattern(/^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/),
    ]),
    assignmentId: new FormControl(''),
  });

  selectedFile: File | null = null;
  fileError = false;
  submitting = false;
  errorMessage: string | null = null;

  constructor(
    private evaluationService: EvaluationService,
    private router: Router
  ) {}

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.fileError = false;
  }

  onSubmit(): void {
    if (!this.selectedFile) {
      this.fileError = true;
    }
    if (this.form.invalid || !this.selectedFile) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting = true;
    this.errorMessage = null;

    const githubUrl = this.form.value.githubUrl!;
    const assignmentId = this.form.value.assignmentId || null;

    this.evaluationService
      .submitEvaluation(githubUrl, assignmentId, this.selectedFile)
      .subscribe((response) => {
        this.submitting = false;
        if (response.success && response.data) {
          this.router.navigate(['/status', response.data.submission_id], {
            state: { data: response.data },
          });
        } else {
          this.errorMessage = response.error?.message ?? 'Submission failed — check the console for details.';
        }
      });
  }
}
