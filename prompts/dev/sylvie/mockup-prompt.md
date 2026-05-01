You are designing UI mockups for MAPLE A1 — "Marist Automated Programming Learning Environment" — a university-grade AI code submission evaluator. Students submit GitHub repository URLs; the system clones them, runs test suites in Docker, and uses an LLM pipeline to produce rubric-aligned scores that instructors approve or reject before students can see them.

The product lives at maple-a1.com. The audience is Marist College students and CS instructors. 

---

EXISTING COLOR VOCABULARY (pulled from current component code — build on this, don't contradict it):

Semantic colors already in use:
- Success / Pass:    #10b981 (green) and #d1fae5 bg / #065f46 text (Exemplary level badge)
- Info / Link:       #1e40af (blue) and #dbeafe bg (Proficient level badge, file paths)
- Warning / Review:  #f59e0b (amber) and #fde68a bg / #92400e text (human-review flags)
- Danger / Fail:     #ef4444 / #dc2626 (red) and #fee2e2 bg
- Neutral text:      #374151 (body), #6b7280 (meta/secondary)
- Borders:           #d1d5db (default card border)
- Backgrounds:       #f3f4f6 (header bars), #f9fafb (meta rows), #fff (card body)
- Developing level:  #fef9c3 bg / #854d0e text (yellow-warm, between warning and success)

These are all Tailwind-scale values. No brand primary color has been chosen yet — propose one 
(or a few options across different mockup variants).

Typography currently: no global font chosen. Monospace stack is SFMono-Regular, Consolas, 
Liberation Mono, Menlo. Body and UI text are unstyled browser defaults. No web fonts imported.

---

SCREENS TO MOCKUP (generate each as a separate artboard at 1440px wide desktop width, 
with a 375px mobile variant for screens 1–3):

SCREEN 1 — Submit Page (/submit)
The student submission entry point. Contains:
- A page heading ("Submit Repository for Evaluation" or a redesigned version)
- A form with exactly 3 fields:
    1. GitHub URL — text input, placeholder https://github.com/owner/repo, 
       validated against github.com URL format
    2. Assignment ID — text input, UUID format placeholder
    3. Rubric File — file upload input, accepts .json and .txt
- Each field has a label, required asterisk marker, and an inline error state below the input
- A submit button with two states: default ("Submit") and loading ("Submitting…", disabled)
- An error banner above the form (dismissible or auto-shown on API error)
Mockup requests: 
  A) Default / empty state  
  B) Validation error state (show all 3 fields with errors triggered)  
  C) Loading / submitting state

SCREEN 2 — Status Page — Loading & Polling state (/status/:id)
Shows while the system is processing. Contains:
- A status card with: Submission ID (monospace), Status badge (one of: Pending / Testing / 
  Evaluating / Awaiting Review / Completed / Failed), GitHub URL, Assignment ID, 
  Commit hash (12-char monospace abbreviation)
- A polling indicator (spinner, animated dots, progress bar — your choice)
- A "Submit another" link
- Badge color rules: green for Completed/Cached/Cloned, amber for Awaiting Review, 
  red for Failed/EVALUATION_FAILED, gray/blue for Pending/Testing/Evaluating

SCREEN 3 — Status Page — Full Evaluation Loaded (/status/:id, instructor view)
The most complex screen. Contains:
- Same top card with metadata (Submission ID, Status=Completed badge, URL, Assignment ID, 
  Commit hash)
- Evaluation summary row: Score (numeric, 0–100), Language (e.g. "python 3.12"), 
  Style guide, Tests run count, Passed count (green badge), Failed count (red badge), 
  Framework (e.g. "pytest")
- Instructor Review Panel (only visible to instructor, status=Awaiting Review):
    - Heading "Instructor Review"  
    - Info text: "AI feedback is pending your approval before it is released to the student."
    - Two buttons: Approve (green) + Reject (red/outlined)
    - Reject expansion: textarea for rejection notes + Submit Rejection + Cancel buttons
- AI Feedback section: a list of Criteria Score cards (see details below)
- Recommendations section: a diff viewer grouped by file (see details below)
- "Submit another" link

SCREEN 4 — Login / Register (not yet built — design from scratch)
Role-aware auth screen. Needs to handle:
- Toggle or tab between Login and Register
- Register: name, email, password, role selector (Student / Instructor)
- Login: email, password
- "Forgot password?" link
- Social/SSO option is optional — decide based on what fits the academic context
- No logo yet — placeholder or propose a maple leaf / code-editor inspired logomark

SCREEN 5 — Instructor Assignment Creation (not yet built)
Form screen for instructors to create a new assignment. Fields:
- Assignment title (text)
- Test suite repo URL (GitHub URL, same validation as submit page)
- Rubric (dropdown or file picker — rubrics are pre-created separately)
- Language override (optional text, e.g. "python 3.12")
- Enable lint review (toggle)
- Submit button

SCREEN 6 — Submissions List / Dashboard (not yet built, instructor view)
A table or card grid showing all submissions for an assignment. Columns or card fields:
- Student name/email, Submission ID (truncated), GitHub URL (truncated), 
  Status badge, Score (if available), Submitted timestamp, Actions (View, Approve/Reject shortcut)
Needs empty state, loading state, and a populated state.

---

COMPONENT DETAILS (embed these faithfully in Screens 2, 3, and 6):

Criteria Score Card (used in Screen 3's AI Feedback section):
- Card with subtle border; border turns amber (#f59e0b) and background #fffbeb when the 
  criterion is flagged NEEDS_HUMAN_REVIEW
- Header row: criterion name (bold, ~0.95rem) LEFT — score badge + level badge RIGHT
  - Score badge: large numeric score + "/100" small text
  - Level badge (pill/chip): 
      Exemplary   → bg #d1fae5  text #065f46  (green)
      Proficient  → bg #dbeafe  text #1e40af  (blue)
      Developing  → bg #fef9c3  text #854d0e  (warm yellow)
      Beginning   → bg #fee2e2  text #991b1b  (red)
      NEEDS HUMAN REVIEW → bg #fde68a  text #92400e (amber)
  - Optional "Needs Human Review" flag pill (same amber) when flagged
- Justification text paragraph below header (~0.88rem, #374151)
- Confidence indicator: "Confidence" label + progress bar (max-width 120px, height 5px) + 
  percentage text. Bar fill: green ≥75%, amber ≥50%, red <50%

Diff Viewer (used in Screen 3's Recommendations section):
- Heading "Recommendations"
- Per file: a card with a file-header bar (bg #f3f4f6, file path in monospace bold blue #1e40af)
- Per recommendation block inside a file: 
  - Meta bar (bg #f9fafb): "Lines X–Y" in monospace + optional italic gray rationale
  - Diff table in monospace font:
    - Added lines:   bg #dcfce7, gutter "+" in #bbf7d0 bg / #16a34a text
    - Removed lines: bg #fee2e2, gutter "-" in #fecaca bg / #dc2626 text
    - Hunk headers:  bg #dbeafe, gutter "⋯" in #bfdbfe bg / #1e40af text
    - Context lines: bg #fff

---

DESIGN DIRECTION VARIANTS:
Generate 3 distinct visual style variants for Screen 1 (Submit Page) and Screen 3 (Full Results) 
to help choose a direction. Label them:

Variant A — "Academic Dark" 
Dark gray/near-black background (#0f172a or #1e293b), white card panels, blue primary accent 
(#3b82f6 or #2563eb), clean sans-serif (Inter or DM Sans), subtle glow or shadow on cards, 
monospace elements feel like a terminal. Status badges are bright and high-contrast.

Variant B — "Clean Academic Light"  
White background, very light gray (#f8fafc) page canvas, deep navy primary (#1e3a5f or #1e40af), 
cards with 1px #e2e8f0 border and subtle box-shadow, generous whitespace, Inter or Geist font, 
feels like a modern university portal or GitHub Classroom.

Variant C — "Warm Maple"
Off-white/cream background (#fafaf9 or #fffdf7), a warm maple-leaf-inspired primary (deep amber 
#b45309 or terracotta #c2410c or burnt sienna), dark charcoal text (#1c1917), rounded corners 
(8–12px), friendly but professional. Card borders are warm (#e7e5e0). Monospace elements still 
technical. The "maple" name is reflected subtly in warmth, not in literal leaf imagery.

---

NAVIGATION SHELL (design for all screens):
No navigation currently exists — app.html is just <router-outlet>. Design a shell that works 
for all 6 screens with:
- A top header bar: logo/wordmark "MAPLE" or "MAPLE A1" on the left, navigation links 
  (Submit, Dashboard — shown only to instructors), and a user avatar/name + logout on the right
- Optional: a subtle left sidebar for the instructor dashboard view (Screen 6)
- No bottom navigation needed for desktop; consider bottom nav for mobile variants

---

LAYOUT CONSTRAINTS:
- Desktop artboard: 1440px wide, content max-width ~1080px or ~800px centered
- Cards: border-radius 8–12px, box-shadow subtle
- Form inputs: height ~40–44px, border-radius 6px, clear focus ring (blue or primary color)
- Buttons: height ~40px, border-radius 6px; primary (filled), secondary (outlined), danger (red)
- Monospace text: always use a code-style font; never render commit hashes or file paths in 
  the body font
- Status badges: pill shape (border-radius 9999px), ~0.75rem font, ~4px 10px padding
- Generate at 2x resolution for clarity

---

OUTPUT FORMAT:
For each artboard, generate:
1. The full-width screen at 1440px (or 375px for mobile variants)
2. A close-up callout of the most complex component on that screen
3. Label all screens clearly by screen number, variant letter, and state name
Total artboards: approximately 18–24 (6 screens × 3 variants for screens 1 & 3, 
single variant for screens 2, 4, 5, 6 + mobile variants for 1–3)
