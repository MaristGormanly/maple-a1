import { Component, ElementRef, ViewChild } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { EvaluationService } from '../../services/evaluation.service';

@Component({
  selector: 'app-submit-page',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './submit-page.component.html',
})
export class SubmitPageComponent {
  @ViewChild('fileInput') fileInputRef!: ElementRef<HTMLInputElement>;

  form = new FormGroup({
    // Optional display label only — the backend derives student_id from
    // the JWT `sub` claim and never sees this field. Capped at 120 chars
    // to keep history.state small.
    studentId: new FormControl('', [Validators.maxLength(120)]),
    githubUrl: new FormControl('', [
      Validators.required,
      Validators.pattern(/^https:\/\/(www\.)?github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\/?$/),
    ]),
    assignmentId: new FormControl('', [
      Validators.required,
      Validators.pattern(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i),
    ]),
  });

  selectedFile: File | null = null;
  fileError = false;
  submitting = false;
  errorMessage: string | null = null;

  constructor(
    private evaluationService: EvaluationService,
    private router: Router
  ) { }

  onFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.fileError = false;
  }

  clearFile(event: Event): void {
    event.stopPropagation();
    this.selectedFile = null;
    if (this.fileInputRef) this.fileInputRef.nativeElement.value = '';
  }

  triggerFileInput(): void {
    if (!this.submitting) this.fileInputRef?.nativeElement.click();
  }

  onSubmit(): void {
    if (!this.selectedFile) this.fileError = true;
    if (this.form.invalid || !this.selectedFile) {
      this.form.markAllAsTouched();
      return;
    }

    const { githubUrl, assignmentId, studentId } = this.form.getRawValue();

    this.submitting = true;
    this.errorMessage = null;
    this.form.disable({ emitEvent: false });

    this.evaluationService
      .submitEvaluation(githubUrl!, assignmentId!, this.selectedFile, studentId || null)
      .pipe(
        finalize(() => {
          this.submitting = false;
          this.form.enable({ emitEvent: false });
        }),
      )
      .subscribe((response) => {
        if (response.success && response.data) {
          localStorage.setItem('maple.latestSubmissionId', response.data.submission_id);
          localStorage.setItem('maple.latestAssignmentId', response.data.assignment_id ?? '');
          this.router.navigate(['/status', response.data.submission_id], {
            state: { data: response.data, studentLabel: studentId ?? null },
          });
        } else {
          this.errorMessage = response.error?.message ?? 'Submission failed — check the console for details.';
        }
      });
  }

  get showStudentErr(): boolean {
    const c = this.form.controls.studentId;
    return c.touched && c.invalid;
  }

  get showUrlErr(): boolean {
    const c = this.form.controls.githubUrl;
    return c.touched && c.invalid;
  }

  get showIdErr(): boolean {
    const c = this.form.controls.assignmentId;
    return c.touched && c.invalid;
  }
}
