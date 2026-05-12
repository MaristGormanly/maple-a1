import { Component, ElementRef, OnDestroy, ViewChild, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { FormsModule } from '@angular/forms';
import { concatMap, of } from 'rxjs';

import { RubricService } from '../../services/rubric.service';
import { RubricListItem } from '../../utils/api.types';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-rubrics-page',
  standalone: true,
  imports: [FormsModule, ConfirmDialogComponent],
  templateUrl: './rubrics-page.component.html',
})
export class RubricsPageComponent implements OnDestroy {
  @ViewChild('newFileInput') newFileInputRef!: ElementRef<HTMLInputElement>;

  private rubricService = inject(RubricService);
  private sanitizer = inject(DomSanitizer);
  private http = inject(HttpClient);

  readonly rubrics = signal<RubricListItem[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);

  // New rubric dialog
  readonly showNewDialog = signal(false);
  readonly newTitle = signal('');
  readonly newNotes = signal('');
  newFile: File | null = null;
  readonly creating = signal(false);
  readonly createError = signal<string | null>(null);

  // Delete dialog
  readonly pendingDeleteId = signal<string | null>(null);
  readonly deleteLoading = signal(false);

  // Per-card editable state
  readonly editMap = new Map<string, { title: string; notes: string; saving: boolean }>();

  // Per-rubric blob URLs for PDF preview (avoids iframe auth issues)
  readonly fileBlobUrls = new Map<string, SafeResourceUrl>();
  private readonly _blobObjectUrls: string[] = [];

  constructor() {
    this._loadRubrics();
  }

  private _loadRubrics(): void {
    this.loading.set(true);
    this.loadError.set(null);
    this.rubricService.getAll().subscribe((res) => {
      this.loading.set(false);
      if (res.success && res.data) {
        this.rubrics.set(res.data.rubrics);
        for (const r of res.data.rubrics) {
          this.editMap.set(r.rubric_id, {
            title: r.title,
            notes: r.notes ?? '',
            saving: false,
          });
          if (r.has_file && this.rubricService.isPdf(r.filename)) {
            this._loadPdfBlob(r.rubric_id);
          }
        }
      } else {
        this.loadError.set(res.error?.message ?? 'Failed to load rubrics.');
      }
    });
  }

  private _loadPdfBlob(rubricId: string): void {
    this.rubricService.fetchFileBlob(rubricId).subscribe({
      next: (blob) => {
        const objectUrl = URL.createObjectURL(blob);
        this._blobObjectUrls.push(objectUrl);
        this.fileBlobUrls.set(
          rubricId,
          this.sanitizer.bypassSecurityTrustResourceUrl(objectUrl),
        );
        // Force signal update so template re-renders
        this.rubrics.update((list) => [...list]);
      },
      error: () => {
        // PDF preview unavailable — card will show filename fallback
      },
    });
  }

  ngOnDestroy(): void {
    for (const url of this._blobObjectUrls) {
      URL.revokeObjectURL(url);
    }
  }

  // ── Dialog helpers ──────────────────────────────────────────────────────────

  openNewDialog(): void {
    this.newTitle.set('');
    this.newNotes.set('');
    this.newFile = null;
    this.createError.set(null);
    this.showNewDialog.set(true);
  }

  closeNewDialog(): void {
    if (this.creating()) return;
    this.showNewDialog.set(false);
  }

  triggerNewFileInput(): void {
    this.newFileInputRef?.nativeElement.click();
  }

  onNewFileChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.newFile = input.files?.[0] ?? null;
  }

  getValue(event: Event): string {
    return (event.target as HTMLInputElement | HTMLTextAreaElement).value;
  }

  // ── Create rubric ───────────────────────────────────────────────────────────

  createRubric(): void {
    if (!this.newTitle().trim()) {
      this.createError.set('Title is required.');
      return;
    }
    this.creating.set(true);
    this.createError.set(null);

    const stubPayload = {
      title: this.newTitle().trim(),
      notes: this.newNotes().trim() || null,
      total_points: 0,
      criteria: [
        { name: 'General', max_points: 0, levels: [{ label: 'N/A', points: 0, description: '' }] },
      ],
    };

    this.http
      .post<any>(`${this.rubricService.url}`, stubPayload)
      .pipe(
        concatMap((res) => {
          if (!res.success) {
            throw new Error(res.error?.message ?? 'Failed to create rubric');
          }
          const rubricId: string = res.data.rubric_id;
          if (this.newFile) {
            return this.rubricService.uploadFile(rubricId, this.newFile);
          }
          return of(res);
        }),
      )
      .subscribe({
        next: () => {
          this.creating.set(false);
          this.showNewDialog.set(false);
          this._loadRubrics();
        },
        error: (err: Error) => {
          this.creating.set(false);
          this.createError.set(err.message);
        },
      });
  }

  // ── Per-card editing ────────────────────────────────────────────────────────

  onTitleInput(rubricId: string, event: Event): void {
    const entry = this.editMap.get(rubricId);
    if (entry) entry.title = (event.target as HTMLInputElement).value;
  }

  onNotesInput(rubricId: string, event: Event): void {
    const entry = this.editMap.get(rubricId);
    if (entry) entry.notes = (event.target as HTMLTextAreaElement).value;
  }

  saveRubric(rubricId: string): void {
    const entry = this.editMap.get(rubricId);
    if (!entry || entry.saving) return;
    entry.saving = true;

    this.rubricService.update(rubricId, entry.title, entry.notes || null).subscribe((res) => {
      entry.saving = false;
      if (res.success && res.data) {
        this.rubrics.update((list) =>
          list.map((r) => (r.rubric_id === rubricId ? { ...r, ...res.data! } : r)),
        );
      }
    });
  }

  // ── Delete ──────────────────────────────────────────────────────────────────

  openDeleteDialog(rubricId: string): void {
    this.pendingDeleteId.set(rubricId);
  }

  get showDeleteDialog(): boolean {
    return this.pendingDeleteId() !== null;
  }

  onDeleteConfirmed(): void {
    const id = this.pendingDeleteId();
    if (!id) return;
    this.deleteLoading.set(true);

    this.rubricService.delete(id).subscribe((res) => {
      this.deleteLoading.set(false);
      if (res.success) {
        this.pendingDeleteId.set(null);
        const blobUrl = this.fileBlobUrls.get(id);
        if (blobUrl) {
          this.fileBlobUrls.delete(id);
        }
        this.editMap.delete(id);
        this.rubrics.update((list) => list.filter((r) => r.rubric_id !== id));
      }
    });
  }

  isPdf(filename: string | null): boolean {
    return this.rubricService.isPdf(filename);
  }
}
