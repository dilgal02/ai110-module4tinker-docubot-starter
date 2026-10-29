# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> _Your answer here._

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> _Your answer here._

**What outputs does DocuBot produce?**

> _Your answer here._

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> _Your answer here._

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> _Your answer here._

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> _Your answer here._

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> _Your answer here._

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Unhelpful: asked for the codebase instead of answering | Helpful but hard to read: top section (AUTH.md "Token Generation") has the answer, buried in ~60 lines with two token-related sections that don't answer it | Helpful: one sentence naming `generate_access_token` in `auth_utils.py`, cites AUTH.md | RAG used the same evidence as retrieval only, condensed to the answer |
| How do I connect to the database? | Harmful: invented `DB_HOST`/`DB_PORT`/`DB_USER` variables and gave a Node.js `pg` example (project is Python, uses `DATABASE_URL`) | Helpful: top section is DATABASE.md "Connection Configuration" | Helpful: `DATABASE_URL`, SQLite `app.db` default, Postgres string format; cites DATABASE.md and SETUP.md | RAG correctly combined two files |
| Which endpoint lists all users? | Vague: listed `/users`, `/api/v1/users`, `/api/users` as guesses, no admin-only note | Harmful: false refusal ("I do not know"), best section scores 2, below the threshold of 3 | Harmful: same false refusal, LLM never called | Docs answer it: `GET /api/users`, admin only. Exact word matching misses "lists" vs "list" |
| How does a client refresh an access token? | Harmful: confident, detailed OAuth 2.0 flow (`/oauth/token`, `grant_type=refresh_token`, `client_secret`), none of which exists here | Partly helpful: "Client Workflow" mentions `/api/refresh`, but the `POST /api/refresh` section is not in the top 3 | Partly harmful: "call `/api/refresh` when it expires", cited but incomplete (no POST, no Bearer header) | Retrieval missed the key section; RAG summarized the wrong evidence confidently |
| What is the API rate limit? (off-topic) | Misleading: "Based on the documentation provided, there is no mention of an API rate limit", but it was given no documentation | Helpful: refused | Helpful: refused without calling the LLM | Before the threshold, retrieval returned AUTH.md "Client Workflow" just for the word "api" |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> **Naive LLM** looks most impressive when a question matches a common pattern (OAuth refresh, user tables, auth env vars). It then gives long, well formatted, specific answers built from general conventions, and uses phrases like "Based on the standard schema documentation" or "Based on the documentation provided" even though `naive_answer_over_full_docs` never sends it the docs. It is also inconsistent: the same users table question produced a request for the schema in one run and 10 invented fields in another.
>
> **Retrieval only** is clearly better when correctness matters more than readability. It can only show text that exists in the docs and it refuses off-topic questions instead of inventing an answer. The cost is that it returns raw sections (code blocks, a broken code fence copied from the source, related but irrelevant sections) and leaves the reader to find the actual answer.
>
> **RAG** is clearly better than both when retrieval finds the right section: it gives a short, direct answer and names the files it used, and it can combine sections from two files correctly (database connection). But it is only as good as retrieval. When the right section is missing (token refresh), it produces a confident, cited answer from the wrong evidence, which is harder to catch than a naive LLM mistake.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> **Failure case 1: RAG answers from incomplete evidence**
> - **Question:** "How does a client refresh an access token?"
> - **What happened:** Retrieval returned AUTH.md "Client Workflow", AUTH.md "Token Generation" and API_REFERENCE.md "POST /api/login", but not API_REFERENCE.md "POST /api/refresh". RAG answered "a client refreshes an access token when it expires by calling `/api/refresh`" and cited AUTH.md.
> - **What should have happened:** Retrieve the `POST /api/refresh` section and answer: send `POST /api/refresh` with `Authorization: Bearer <token>` and receive a new `access_token`. It should also flag that the docs disagree: AUTH.md says to refresh when the token expires, while API_REFERENCE.md says refresh takes an existing *valid* token.

> **Failure case 2: false refusal**
> - **Question:** "Which endpoint lists all users?"
> - **What happened:** Retrieval only and RAG both answered "I do not know based on these docs." The best matching section scored 2, below the evidence threshold of 3, because only the word "users" matched exactly ("lists" vs "list", "endpoint" vs "endpoints").
> - **What should have happened:** Answer `GET /api/users`, noting it is admin only and returns 403 for other accounts.

> **Failure case 3: naive LLM invents a schema**
> - **Question:** "Which fields are stored in the users table?"
> - **What happened:** Naive mode answered "Based on the standard schema documentation…" and listed 10 fields (`id`, `username`, `first_name`, `is_active`, `role`…). Only `email` and `password_hash` are real.
> - **What should have happened:** List the four documented columns: `user_id`, `email`, `password_hash`, `joined_at`.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> - When the topic is not covered anywhere in the docs, e.g. payment processing, API rate limits, OAuth login with Google, deployment, password reset.
> - When the question only overlaps the docs on generic words such as "api", "users" or "docs", so no section contains real evidence for the specific thing asked.
> - When the retrieved snippets are on the right topic but do not contain the specific fact asked for, so answering would mean filling the gap with a guess.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> - **Evidence threshold:** `retrieve` drops any section scoring below `MIN_EVIDENCE_SCORE = 3` (total query word hits). If nothing passes, both retrieval only and RAG mode answer "I do not know based on these docs.", and RAG skips the LLM call entirely. The value was chosen from measurements: off-topic questions scored at most 2, while most in-scope questions scored 3 to 10.
> - **Stopwords:** filler words ("how", "the", "is", "all"…) are ignored so they cannot count as evidence.
> - **Snippet limit:** retrieval returns at most 3 heading sections instead of whole files, so the LLM sees less unrelated text.
> - **Grounding prompt:** the RAG prompt tells the model to use only the snippets, not to invent functions, endpoints or configuration values, to reply exactly "I do not know based on the docs I have." when the snippets are not enough, and to name the files it relied on.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. _Limitation 1_
2. _Limitation 2_
3. _Limitation 3_

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. _Improvement 1_
2. _Improvement 2_
3. _Improvement 3_

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> _Your answer here._

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- _Guideline 1_
- _Guideline 2_
- _Guideline 3 (optional)_

---
