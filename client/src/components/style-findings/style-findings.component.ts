import { Component, Input } from '@angular/core';
import { StyleFinding } from '../../utils/api.types';

@Component({
  selector: 'app-style-findings',
  standalone: true,
  imports: [],
  templateUrl: './style-findings.component.html',
})
export class StyleFindingsComponent {
  @Input() findings: StyleFinding[] = [];

  severityTone(severity: string): 'red' | 'amber' | 'blue' {
    if (severity === 'error') return 'red';
    if (severity === 'warning') return 'amber';
    return 'blue';
  }

  lineRangeLabel(finding: StyleFinding): string {
    const { start, end } = finding.line_range;
    return start === end ? `line ${start}` : `lines ${start}–${end}`;
  }
}
