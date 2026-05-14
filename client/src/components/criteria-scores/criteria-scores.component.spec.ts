import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CriteriaScoresComponent } from './criteria-scores.component';

describe('CriteriaScoresComponent', () => {
  let fixture: ComponentFixture<CriteriaScoresComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CriteriaScoresComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(CriteriaScoresComponent);
  });

  it('renders the matched rubric standard when present', () => {
    fixture.componentInstance.criteriaScores = [
      {
        criterion_name: 'Architecture and Design',
        score: 87.5,
        level: 'STRONG',
        rubric_standard: 'Strong organization with clear logical divisions.',
        rubric_weight: '20%',
        justification: 'The codebase is organized into cohesive modules.',
        confidence: 0.9,
        reasoning_details: {
          score_reasoning: 'The score follows the matched strong rubric level.',
          confidence_reasoning: 'Confidence is high because evidence is consistent.',
          evidence: 'Rubric standard and repository structure.',
          uncertainty: 'No major uncertainty.',
          limitations: 'Only submitted files were evaluated.',
        },
      },
    ];

    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Rubric standard');
    expect(text).toContain('20%');
    expect(text).toContain('Strong organization with clear logical divisions.');
    expect(text).toContain('Evaluation rationale');
    expect(text).toContain('The score follows the matched strong rubric level.');
  });

  it('omits the debug rationale when no reasoning details are present', () => {
    fixture.componentInstance.criteriaScores = [
      {
        criterion_name: 'Correctness',
        score: 100,
        level: 'EXEMPLARY',
        justification: 'All tests passed.',
        confidence: 0.95,
      },
    ];

    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).not.toContain('Evaluation rationale');
  });

  it('formats the new score level labels for display', () => {
    expect(fixture.componentInstance.levelLabel('NEEDS_IMPROVEMENT')).toBe('Needs Improvement');
    expect(fixture.componentInstance.levelLabel('WEAK')).toBe('Weak');
    expect(fixture.componentInstance.levelLabel('ACCEPTABLE')).toBe('Acceptable');
    expect(fixture.componentInstance.levelLabel('STRONG')).toBe('Strong');
    expect(fixture.componentInstance.levelLabel('EXEMPLARY')).toBe('Exemplary');
  });
});
