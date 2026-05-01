# Written Reflection — MAPLE A1, Milestone 3
| AI Systems | Spring 2026

---

# Notes about AI-First Development

One of the unexpected outcomes of AI-first development is that for better or worse, it begins to diminish the social nature of group development. 

This is due in part to our extensive documentation. For example, we have AI generate each milestone markdown file to pre-delegate our tasks based on skill sets outlined in our design document. Each milestone task is assigned to a person and specifies which other tasks it depends on, whether those are owned by the same person or someone else on the team. 

After each coding session is completed we individually generate a markdown file with a description of our changes, as well as an audit, which runs through the entire codebase and checks its alignment with the expectations of our design doc and our milestone doc. Any issues are then outlined in a markdown file and attributed to the individual (or individuals) most likely responsible for the issue. 

All that's left to do is message the group and say you've pushed--everything else is in the markdown. 

We know that one of the major reasons we were assigned teams for this project was because of the isolative nature of working with AI, but we would be remiss not to mention that the second you introduce AI to your codebase, your team will inherently become more isolated. You then have to make a concious choice to  keep communicating with eachother (i.e pushing for in-person meetings, hashing out problems by talking to eachother rather than back and forth through audit files, and making joint decisions about the minor details that the AI misses, even when you feel like you can take the lead and do it on your own.)

# AI as a Workflow Partner

AI was integral to MAPLE A1's implementation across all three milestones, functioning as a prompt engineer, code generator, and debugger. AI shaped nearly every non-trivial decision in our work.

One concrete example was the cache key design. The initial approach used the raw commit hash as the cache key, but during testing it became clear that the same commit could produce different evaluation results if the rubric changed. AI helped us reason through the collision scenario: a submission already cached against one rubric would silently return a stale result for a different rubric. The fix was to fingerprint the rubric content separately and key on `commit_hash::rubric_digest`. AI also surfaced the normalization edge cases — whitespace differences and key ordering in JSON rubrics could produce different digests for semantically identical rubrics — which led to the `text_whitespace_canonicalization` and `json_canonicalization` paths in `cache.py`.

---

# Biggest Technical Challenge

The most difficult problem in Milestone 3 was blocked integration of the full pipeline: the LLM service `complete()` method was a stub through most of the milestone, meaning the three-pass evaluation pipeline we built had no live model to call. This forced a design decision on whether to block integration or build graceful degradation around the missing dependency.

A second challenge was the `CriterionScore.recommendation` field. The schema defined it per-criterion, but the submission response handler was flattening all recommendations into a top-level array and dropping the per-criterion values. The audit caught this as a low-severity data-loss bug at `submissions.py:118–122`. AI helped trace it to the serialization step rather than the scoring logic, which narrowed the fix considerably.

---

# Design Deviations

Several implementation details diverged from the original design doc, each with a documented rationale.

**LLM Provider Chain:** The design doc assumed a single primary model. During M3 implementation, we switched from Vertex AI to the native Gemini API to avoid Google Cloud authentication overhead in the dev environment, and added a three-model fallback chain (Gemini Pro → Gemini Flash → GPT-4o) with exponential backoff. This was the right call for iteration speed, but it means production costs and latency will vary significantly depending on which fallback tier is hit.

**Instructor Review Columns:** The M3 migration added `review_status` and `instructor_notes` to `evaluation_results`, which was not in the original schema. This was a scope addition driven by the requirement that AI feedback not be visible to students until an instructor approves it — a safeguard against surfacing hallucinated or low-confidence scores directly.


