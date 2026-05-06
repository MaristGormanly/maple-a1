import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { AssignmentService } from '../../services/assignment.service';
import { AssignmentData, AssignmentListResponse } from '../../utils/api.types';
import { ConfirmDialogComponent } from '../../components/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-assignments-page',
  standalone: true,
  imports: [RouterLink, ConfirmDialogComponent],
  templateUrl: './assignments-page.component.html',
})
export class AssignmentsPageComponent {
  private assignmentService = inject(AssignmentService);
  readonly router = inject(Router);

  readonly searchQuery = signal('');
  private readonly _response = signal<AssignmentListResponse | null>(null);
  private readonly _assignments = signal<AssignmentData[]>([]);

  readonly loading = computed(() => this._response() === null);
  readonly loadError = computed(() => {
    const r = this._response();
    return r && (!r.success || !r.data) ? (r.error?.message ?? 'Failed to load assignments.') : null;
  });
  readonly allAssignments = computed(() => this._assignments());
  readonly filtered = computed(() => {
    const needle = this.searchQuery().toLowerCase();
    if (!needle) return this.allAssignments();
    return this.allAssignments().filter(a =>
      [a.title, a.test_suite_repo_url ?? '', a.language_override ?? '']
        .join(' ').toLowerCase().includes(needle));
  });

  readonly showDeleteDialog = signal(false);
  readonly pendingDeleteId = signal<string | null>(null);
  readonly deleteLoading = signal(false);
  readonly deleteError = signal<string | null>(null);

  constructor() {
    this.assignmentService.getAll().subscribe(res => {
      this._response.set(res);
      this._assignments.set(res.data?.assignments ?? []);
    });
  }

  viewAssignment(a: AssignmentData): void {
    this.router.navigate(['/assignments', a.assignment_id]);
  }

  onSearch(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  openDeleteDialog(id: string, event: Event): void {
    event.stopPropagation();
    this.pendingDeleteId.set(id);
    this.deleteError.set(null);
    this.showDeleteDialog.set(true);
  }

  onDeleteConfirmed(): void {
    const id = this.pendingDeleteId();
    if (!id) return;
    this.deleteLoading.set(true);
    this.assignmentService.delete(id).subscribe(res => {
      this.deleteLoading.set(false);
      if (res.success) {
        this._assignments.update(list => list.filter(a => a.assignment_id !== id));
        this.showDeleteDialog.set(false);
        this.pendingDeleteId.set(null);
      } else {
        this.deleteError.set(res.error?.message ?? 'Delete failed.');
      }
    });
  }

  onDeleteCancelled(): void {
    this.showDeleteDialog.set(false);
    this.pendingDeleteId.set(null);
  }
}
