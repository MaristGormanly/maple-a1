import { Component, Input } from '@angular/core';
import { CriterionScore, RubricCriterion } from '../../utils/api.types';

@Component({
  selector: 'app-criteria-scores',
  standalone: true,
  imports: [],
  templateUrl: './criteria-scores.component.html',
})
export class CriteriaScoresComponent {
  // Criteria arrive in rubric order from the API (Pass 3 preserves rubric criterion sequence).
  @Input() criteriaScores: CriterionScore[] = [];
  @Input() rubricCriteria: RubricCriterion[] = [];

  guidelineFor(c: CriterionScore): string | null {
    const criterion = this.rubricCriteria.find(r => r.name === c.criterion_name);
    if (!criterion) return null;
    const level = criterion.levels.find(l => l.label === c.level);
    return level?.description ?? null;
  }

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
