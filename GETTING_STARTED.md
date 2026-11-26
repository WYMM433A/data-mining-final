# Getting Started — A Guide for First-Time Readers

Welcome. This explains, in order, **what's been done so far**, **how to make sense of the
files you're looking at**, and **exactly what to open next** depending on which part of the
analysis (RQ1–RQ4) you're picking up. For the full original project design (roles, timeline,
study references), see [IT_Job_Market_Project_Plan_v2.md](./IT_Job_Market_Project_Plan_v2.md).
For a one-page status snapshot, see [README.md](./README.md). This file is the narrative
walkthrough in between those two.

---

## 1. The big picture

We scraped ~10,000 US IT job postings from LinkedIn, cleaned the text, built a dictionary of
**440 canonical technical skills**, extracted which skills appear in which posting, validated
that extraction against human judgment, and turned the result into a **Job × Skill matrix** —
one row per job posting, one 0/1 column per skill. That matrix is the input to four analyses
(association rules, similarity, clustering, and a decision-tree classifier) that haven't been
started yet — that's the next phase, and probably what you're here to do.

| Research question | What it asks |
|---|---|
| **RQ1** | Which technical skills are frequently requested together? |
| **RQ2** | Which postings have similar requirements despite different titles? |
| **RQ3** | Do postings form recurring skill-based profiles when titles are ignored? |
| **RQ4** | How well do conventional job titles represent the actual skill requirements? |

---

## 2. How we got here (the pipeline, in order)

Each step below is a numbered script in `scripts/`, run in order, each reading the previous
step's output. You don't need to rerun any of this — it's already done — but understanding the
chain helps explain why the final files look the way they do.

1. **Collection** — 34 LinkedIn searches across 8 IT job families (AI/ML, cloud/DevOps,
   cybersecurity, data/BI, database, enterprise IT, QA, software) → 10,188 raw rows, 8,882
   distinct job IDs.
2. **Merge + quality filters** — dropped postings with no title/description or under 50 words →
   8,879 postings kept.
3. **Job family tagging** — each posting's **title** (not the search keyword that found it) is
   matched against ordered rules to assign one of the 8 families, or `other` if nothing matches.
   This matters for RQ4: the question is "do skills predict the *title's* family," so the label
   has to come from the title.
4. **Text cleaning + deduplication** — removed boilerplate (legal/benefits text), collapsed
   byte-identical postings into "description groups" (6,532 groups), then found 373 pairs that
   were near-duplicates (≥95% similar text) and — after checking title + location, not just text
   similarity — merged the 74 that were confirmed to be the same posting reposted twice. Final:
   **6,458 unique description groups** across the 8,879 postings.
5. **Skill dictionary** — this was the largest single effort. Started from an existing
   AI-assisted cleaned dictionary (964 candidate skills), audited it against real posting text,
   fixed real problems found along the way (duplicate entries, a split `AWS`/`Amazon Web
   Services`, ambiguous abbreviations, generic words like "cloud" or "testing" masquerading as
   skills), and added skills that were missing but clearly present in the text (e.g. `Data
   Quality`, `Prompt Engineering`, `Incident Response`). A later cross-check against an external
   technology taxonomy added 21 more confirmed-real skills (e.g. `Active Directory`, `Azure SQL`,
   `React Native`). Landed on **440 skills across 6 categories** (Programming Languages,
   Frameworks & Libraries, Platforms & Infrastructure, Software & Tools, Technical Concepts,
   Technical Practices).
6. **Extraction** — scanned every unique description for each of the 440 skills and their known
   aliases (e.g. "K8s" → `Kubernetes`), using word-boundary matching plus extra rules for
   ambiguous terms (a bare "R" or "Go" needs surrounding context to count) and a few negative
   checks (e.g. `Artificial Intelligence (AI)` doesn't count a hiring-disclosure boilerplate
   sentence as a real mention).
7. **Validation** — 120 postings were independently annotated twice (by different methods/
   people) to check whether the extraction was actually right. Result: **Precision 89.8%, Recall
   97.0%, F1 93.3%** — clears the 85% target the project set for itself.
8. **The matrix** — one row per posting, one column per skill that appeared often enough to be
   useful (≥15 times, not more than 60% of postings), built in two parallel views (explained
   below).

If you want the full blow-by-blow (every specific bug found and fixed, every merge/split
decision and why), that level of detail exists in a local project log that isn't in this repo —
ask whoever's been running the pipeline if you need it. This guide only covers what you need to
start analyzing.

---

## 3. How to read the files you actually have

Open `outputs/09_job_skill_matrix/` — this is the one folder with everything you need.

### `job_skill_matrix_description_level.csv` — **use this one for your analysis**
One row per unique job posting (reposts already collapsed). Columns:

- `job_id` — one representative posting ID for that description group (use it to look up the
  title/company in `job_metadata.csv`, below)
- `description_group_id` — the dedup group this posting belongs to (use this if you need to
  group by posting in cross-validation, per the plan's Step 6.5 design)
- `job_family` — one of `ai_ml`, `cloud_devops`, `cyber_network`, `data_bi`, `database_data`,
  `enterprise_it`, `qa_testing`, `software` — **this is your RQ4 classification target.** Never
  use it as a feature for clustering/rules/similarity, only as a label to check results against.
- **412 skill columns**, each 0 or 1 (e.g. `Python`, `AWS`, `Docker`, `Machine_Learning`). Spaces
  and slashes in skill names were replaced with `_` and `-` so they're valid column names.

**Concrete example — row 1 of the file is job `4487789285`, titled "Data Scientist, Mid"
(`ai_ml` family), with 15 skills turned on:** `Artificial Intelligence (AI)`, `Data Analytics`,
`Data Quality`, `Data Science`, `Data Visualization`, `Databricks`, `ETL/ELT`, `Machine
Learning`, `Power BI`, `PySpark`, `Python`, `Qlik`, `SQL`, `Spark`, `Tableau` — everything else is
0 for that row. That's the shape of every row: a sparse 0/1 vector over 412 possible skills.

**6,135 rows × 412 columns, density ~3.5%** — meaning on average each posting has about 13–14 of
the 412 skills marked, and the rest are 0. That sparsity is expected and normal for this kind of
data (see `matrix_summary.txt` for exact stats).

### `job_skill_matrix_listing_level.csv` — the "did deduplication matter?" check view
Same 412 columns, same structure, but **one row per individual posting including reposts**
(8,373 rows). The project plan asks you to run your main analyses on this too and report whether
results change — it exists specifically for that comparison, not as a second primary dataset.

### `skill_shortlist_final.csv` — the skill dictionary
Look up a skill's **category** here when you need to group columns (e.g. "show me only
Programming Languages skills"). Columns: `canonical_skill`, `category`, `total_doc_freq`
(how often it appeared, aggregate), `mining_status` (`include` = one of the 412 matrix columns),
`family_adjacent`, `parent`. Example:

| canonical_skill | category | mining_status |
|---|---|---|
| Python | Programming Languages | include |
| AWS | Platforms & Infrastructure | include |
| Docker | Platforms & Infrastructure | include |

Category breakdown of the 440 skills actually used in mining:

| Category | Count |
|---|---|
| Platforms & Infrastructure | 108 |
| Software & Tools | 100 |
| Frameworks & Libraries | 72 |
| Technical Concepts | 69 |
| Technical Practices | 53 |
| Programming Languages | 38 |

### `job_metadata.csv` — human-readable lookup (title, company, location)
The matrix files deliberately don't carry title/company text (keeps the file small and focused
on the binary features). If you need to **read** a posting — to name a cluster, pick an
illustrative example for the report, or judge a "cross-title" similarity pair — look its `job_id`
up here:

| job_id | title | company | location | job_family | description_group_id |
|---|---|---|---|---|---|

### `matrix_summary.txt`
Quick-reference stats for both views: row/column counts, density, top 20 skills, postings per
family. Check this first if you just want a sanity check before loading the full CSVs.

### What you *don't* need to open
- `job_skill_groups.csv` / `job_skill_listing.csv` (in `outputs/06_skill_extraction_v2/`) — the
  per-posting evidence snippets (which sentence triggered each match). Useful only if you need to
  trace a specific matrix cell back to the original wording for a report appendix; not needed to
  run any of the four analyses.
- Anything under `outputs/00_source_profile/`, `02_quality_filters/`, `03_job_family/`,
  `04_text_cleaning_and_groups/` — these are intermediate pipeline stages (raw/cleaned
  description text) and were deliberately **not pushed to this repo** (some individual files
  exceed GitHub's size limits, and none of it is needed downstream of the matrix). If you ever
  need to rebuild them, rerun `scripts/01_build_collection_log.py` through
  `scripts/04b_merge_near_duplicates.py` in order against `data/raw/`.

---

## 4. What to open next, by research question

All four analyses start the same way: load `job_skill_matrix_description_level.csv`, set aside
`job_id` / `description_group_id` / `job_family` as metadata (never as features), and use the 412
skill columns as your binary feature matrix.

```python
import pandas as pd

df = pd.read_csv("outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv")
meta_cols = ["job_id", "description_group_id", "job_family"]
skill_cols = [c for c in df.columns if c not in meta_cols]
X = df[skill_cols]          # 6,135 x 412 binary matrix — your actual feature data
labels = df["job_family"]   # only for RQ4 evaluation, never a feature
```

- **RQ1 (association rules)** — feed `X` to FP-Growth (e.g. `mlxtend.frequent_patterns`). Use
  `skill_shortlist_final.csv`'s `category` column if you want to also mine within a category or
  within a `job_family` subset. See plan Section 6.1 for thresholds (support ~2%, lift ≥1.2).
- **RQ2 (similarity)** — compute Jaccard/cosine between rows of `X`. Use `job_metadata.csv` to
  pull titles for any pair you want to inspect or report on. See plan Section 6.2.
- **RQ3 (clustering)** — hierarchical (Jaccard distance) and K-means (TF-IDF + SVD) on `X`.
  Never include `job_family` as a feature — it's only for comparing against clusters afterward.
  See plan Section 6.3.
- **RQ4 (titles vs. skills)** — crosstab clusters against `labels`, then train a decision tree
  with `X` as features and `labels` as the target, grouping cross-validation folds by
  `description_group_id` so near-identical postings never split across train/test. See plan
  Sections 6.4–6.5.

For every method, also run it against `job_skill_matrix_listing_level.csv` and report whether the
results change — that's the dedup-sensitivity check the project plan asks for.

---

## 5. Things worth knowing before you dig in

- **The two matrix views share the exact same 412 columns**, computed once from the
  deduplicated population — they're directly comparable, by design.
- **The dictionary is hand-curated and evidence-checked**, not a generic off-the-shelf skill
  list. Every merge, split, or addition was checked against real posting text first. If something
  looks off (a skill missing, two skills that seem like duplicates), check the actual job text
  before assuming it's a mistake — and before changing the dictionary yourself, since extraction
  and the matrix would need to be rebuilt to match.
- **`Artificial Intelligence (AI)` has a known precision ceiling.** It's the single most common
  skill in the matrix (appears in ~51% of postings) and some of those hits are real false
  positives from company branding ("Shield AI") or vague marketing language — confirmed by two
  independent validation rounds, not something to chase further.
- **Validation (93.3% F1) was scored against an earlier, smaller dictionary** (372 skills vs. the
  current 440 — the dictionary has grown twice since, once from an evidence-based category audit
  and once from an external technology-taxonomy cross-check) — treat it as representative of
  overall pipeline quality, not a literal up-to-the-minute number.
- **Nothing in `outputs/` is meant to be hand-edited.** If a number looks wrong, the fix belongs
  in the script that generates that file, followed by rerunning it — not a manual CSV edit.
