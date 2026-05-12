import { Component, ElementRef, OnInit, ViewChild, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';

import { EvaluationService } from '../../services/evaluation.service';
import { RepositoryService } from '../../services/repository.service';
import { RubricService } from '../../services/rubric.service';
import { RepositoryItem, RubricListItem } from '../../utils/api.types';

@Component({
  selector: 'app-submit-page',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  templateUrl: './submit-page.component.html',
})
export class SubmitPageComponent implements OnInit {
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

  readonly urlMode = signal<'manual' | 'picker'>('manual');
  readonly repos = signal<RepositoryItem[]>([]);
  readonly reposLoading = signal(false);
  readonly reposError = signal<string | null>(null);

  // Rubric mode
  readonly rubricMode = signal<'library' | 'upload'>('upload');
  readonly savedRubrics = signal<RubricListItem[]>([]);
  readonly selectedRubricId = signal('');
  rubricIdError = false;

  constructor(
    private evaluationService: EvaluationService,
    private repositoryService: RepositoryService,
    private rubricService: RubricService,
    private router: Router,
  ) {
    this.rubricService.getAll().subscribe((res) => {
      if (res.success && res.data && res.data.rubrics.length > 0) {
        this.savedRubrics.set(res.data.rubrics);
        this.selectedRubricId.set(res.data.rubrics[0].rubric_id);
      }
    });
  }

  ngOnInit(): void {
    const state = history.state as { prefillUrl?: string };
    if (state?.prefillUrl) {
      this.form.controls.githubUrl.setValue(state.prefillUrl);
    }
  }

  switchMode(mode: 'manual' | 'picker'): void {
    this.urlMode.set(mode);
    if (mode === 'picker' && this.repos().length === 0 && !this.reposLoading()) {
      this.loadRepos();
    }
  }

  loadRepos(): void {
    this.reposLoading.set(true);
    this.reposError.set(null);
    this.repositoryService.listRepositories().subscribe(res => {
      this.reposLoading.set(false);
      if (res.success && res.data) {
        this.repos.set(res.data.repositories);
      } else {
        this.reposError.set(res.error?.message ?? 'Failed to load repositories.');
      }
    });
  }

  onRepoPicked(event: Event): void {
    const url = (event.target as HTMLSelectElement).value;
    this.form.controls.githubUrl.setValue(url);
  }

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

  onRubricSelect(event: Event): void {
    this.selectedRubricId.set((event.target as HTMLSelectElement).value);
    this.rubricIdError = false;
  }

  onSubmit(): void {
    const isUpload = this.rubricMode() === 'upload';
    const isLibrary = this.rubricMode() === 'library';

    if (isUpload && !this.selectedFile) this.fileError = true;
    if (isLibrary && !this.selectedRubricId()) this.rubricIdError = true;

    if (this.form.invalid || (isUpload && !this.selectedFile) || (isLibrary && !this.selectedRubricId())) {
      this.form.markAllAsTouched();
      return;
    }

    const { githubUrl, assignmentId, studentId } = this.form.getRawValue();

    this.submitting = true;
    this.errorMessage = null;
    this.form.disable({ emitEvent: false });

    this.evaluationService
      .submitEvaluation(
        githubUrl!,
        assignmentId!,
        isUpload ? this.selectedFile : null,
        studentId || null,
        isLibrary ? this.selectedRubricId() : null,
      )
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
