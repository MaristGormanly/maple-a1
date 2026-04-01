import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { SubmissionData } from '../../utils/api.types';

@Component({
  selector: 'app-status-page',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './status-page.component.html',
})
export class StatusPageComponent implements OnInit {
  data: SubmissionData | null = null;
  submissionId: string | null = null;

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.submissionId = this.route.snapshot.paramMap.get('id');

    const state = history.state as { data?: SubmissionData };
    this.data = state?.data ?? null;

    // TODO (Milestone 2): If data is null, fetch submission status from
    // GET /api/v1/code-eval/submissions/:id using this.submissionId.
    // Poll on an interval until status transitions out of a pending state.
  }

  abbrev(value: string): string {
    return value.slice(0, 12);
  }
}
