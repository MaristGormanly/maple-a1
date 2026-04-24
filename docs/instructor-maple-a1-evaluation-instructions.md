# MAPLE A1 — Instructor Evaluation Instructions

This guide covers how an instructor configures GitHub access so the MAPLE A1 Code Submission Evaluator can clone and evaluate every student's assignment repository during the pilot.

For MVP, A1 operates as an **instructor-driven evaluator**: the instructor submits student GitHub repository URLs against an assignment, and the backend clones each repo using the **instructor's** Personal Access Token (PAT). Per Marist course convention, students are required to add the instructor as a collaborator on their assignment repository before the deadline.

---

## 1. Require students to add you as a collaborator

Include this requirement in the assignment spec. Each student must, in their assignment repository:

```
Settings → Collaborators → Add people → <instructor-github-username> → Read access
```

Or via the GitHub CLI (students can run this themselves):

```bash
gh api -X PUT repos/<student-username>/<repo-name>/collaborators/<instructor-username> \
  -f permission=pull
```

After sending the invite, the instructor must **accept** it — GitHub does not auto-accept collaborator invites. Accept pending invites in bulk:

```bash
gh api /user/repository_invitations --jq '.[].id' | \
  xargs -I{} gh api -X PATCH /user/repository_invitations/{}
```

---

## 2. Generate the instructor PAT

1. **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token.**
2. **Resource owner:** the instructor's personal account.
3. **Repository access:** *Only select repositories* → add every student repo the instructor has been invited to. (Re-edit the token each time a new student is added, or use a classic PAT with `repo` scope if managing per-repo selection becomes tedious for a 10-student pilot.)
4. **Repository permissions:** `Contents: Read-only`, `Metadata: Read-only`. Nothing else.
5. **Expiration:** align with semester end (e.g., 90 days). Rotate each term.
6. Copy the token once — GitHub will not show it again.

---

## 3. Install the PAT on the A1 server

On the DigitalOcean Droplet:

```bash
sudo -e /opt/maple-a1/.env
# set: GITHUB_PAT=github_pat_xxxxxxxxxxxxxxxxxxxx
sudo systemctl restart maple-a1
```

Verify by submitting one known-good student repo URL; expect `status: "cloned"` in the response. A `401 AUTHENTICATION_ERROR` means either the PAT lacks scope for that repo or the collaborator invite wasn't accepted.

---

## 4. Per-assignment checklist

- [ ] Assignment spec explicitly states: *"Add `<instructor-username>` as a read collaborator before the deadline — submissions on repos without collaborator access will not be graded."*
- [ ] Accept all pending invites (`gh api /user/repository_invitations`).
- [ ] Update the fine-grained PAT's repo selection to include any newly-added student repos (skip if using a classic `repo`-scoped PAT).
- [ ] Spot-check 2–3 clones before running the full batch:
  ```bash
  git clone https://<pat>@github.com/<student>/<repo>.git /tmp/check && rm -rf /tmp/check
  ```
- [ ] After the grading window closes, revoke the semester PAT and issue a fresh one next term.

---

## 5. Handling missing collaborator access

If a student forgets to add the instructor:

1. A1 returns `401 AUTHENTICATION_ERROR` on `POST /evaluate`; no credential leak occurs.
2. The instructor contacts the student to add them as a collaborator.
3. After the invite is accepted and (if fine-grained) the PAT's repo list is updated, re-submit — SHA caching ensures no duplicate work if the commit hash is unchanged.

---

## Related documentation

- [`design-doc.md`](./design-doc.md) — full system architecture and MVP scope notes
- [`deployment.md`](./deployment.md) — server environment variables, including `GITHUB_PAT`
- [`api-spec.md`](./api-spec.md) — `POST /evaluate` request/response contract and error codes
