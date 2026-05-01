import { Component, Input } from '@angular/core';
import { CriterionScore } from '../../utils/api.types';

@Component({
  selector: 'app-criteria-scores',
  standalone: true,
  imports: [],
  templateUrl: './criteria-scores.component.html',
})
export class CriteriaScoresComponent {
  // Criteria arrive in rubric order from the API (Pass 3 preserves rubric criterion sequence).
  @Input() criteriaScores: CriterionScore[] = [];

  badgeTone(level: string): string {
    const map: Record<string, string> = {
      Exemplary: 'green', Proficient: 'green',
      Developing: 'amber', Beginning: 'red',
      NEEDS_HUMAN_REVIEW: 'amber',
    };
    return map[level] ?? 'neutral';
  }

  levelLabel(level: string): string {
    return level === 'NEEDS_HUMAN_REVIEW' ? 'Needs Review' : level;
  }

  confidencePct(confidence: number): number {
    return Math.round(confidence * 100);
  }

  confFillClass(confidence: number): string {
    if (confidence >= 0.75) return 'conf-fill--hi';
    if (confidence >= 0.5) return 'conf-fill--mid';
    return 'conf-fill--lo';
  }

  isNeedsReview(c: CriterionScore): boolean {
    return c.level === 'NEEDS_HUMAN_REVIEW';
  }
}
