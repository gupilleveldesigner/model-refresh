# Completion-check expiry review (Phase 2b)

## Why this step belongs in a refresh

A completion check is a fixed, **falsifiable** criterion for judging whether work is actually done (a test suite, an old-vs-new version parity comparison, pixel-diffing screenshots, a character-count limit check, etc.). It's the single reason a long autonomous task doesn't stop prematurely. But completion checks expire — after 2–3 model generations, they start passing everything, and a check that always passes is not a check anymore. **Because the expiry trigger is precisely "a new model shipped," a refresh that only diets context and skips renewing checks is only half a refresh.**

## Procedure

1. **Inventory completion checks** — collect anything acting as a "fixed pass/fail bar" across the user's projects, skills, and workflows. Look in: the project's test/QA gates, the pass criteria used by verification skills or verification subagents, "PASS conditions" written into CLAUDE.md/skills, and gate stages in pipelines. This includes not just automated tests but also procedural gates like "release only after an independent QA report says PASS." Don't sweep everything at once — **cap this audit at 3–5**. Priority: (1) checks used as the stop condition for autonomous/long-running work, (2) gates right before release/publish, (3) whichever has gone longest untouched. List the rest by **name only** under "next round" in the audit record. If the inventory is allowed to grow unbounded, this step ends up skipped entirely every time — that's literally what happened in the first audit.
2. **Ask each check: "can this still fail against the new model?"** Judge in this order, not by impression.
   - **a. Check failure history** — if it has failed recently, it's alive; keep it. Look for history in: the project's CI/test logs, FAIL records left by a verification subagent, and points in session transcripts where that gate actually forced rework. **Not finding history is different from there being no failures** — if you couldn't find it, go to (b).
   - **b. Mutation testing (the core test)** — deliberately feed the check a broken input and run it. Example: a document with a required section deleted, an answer that exceeds the character limit, a level JSON broken so it can't be cleared. If it still passes, **that's a confirmed expiry.** This one step turns "expiry candidate" from a guess into proof.
   - **c.** If the failure condition only targets a mistake type old models used to make (and the current model no longer makes), it's an expiry candidate.
   - **d.** If the pass/fail basis is subjective judgment like "run it and see if it looks good," it isn't a check at all — a candidate for creating one.

   A check you can't run mutation testing against (a manual QA gate, etc.) gets classified as **"unverified"** and reported as-is — don't call it expired or alive.
3. **Propose a rewrite direction** — an expiry candidate isn't discarded, it's replaced: rewrite it to target mistakes the new model **actually** makes now. The rewrite must itself be falsifiable — check yourself with "can this come out 'no'?"
4. **Report as its own section in Phase 3** — "Completion-check expiry review: alive / expiry candidates (with rewrite proposal) / areas with no check (proposal to create one)." Modifying or creating checks goes through the same approval gate as any other setup change.

## Caution

- An empty check inventory is itself a significant finding — it means completion is being judged entirely by feel, and the report should say so.
- A check passing doesn't automatically mean it's expired (the underlying code may have genuinely improved). Judge expiry by whether it **lost the ability to fail** — if it still passes when you deliberately feed it a broken input, that's a confirmed expiry.
