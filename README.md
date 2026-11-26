# Beyond Job Titles: Discovering Hidden Skill Relationships and Job Profiles in US IT Job Postings

Introduction to Data Mining course project. We collected US IT job postings, extracted technical
skills from the description text, and are building a **Job-Skill Matrix** to mine skill relationships,
similarity between postings, clustering-based skill profiles, and how well job titles predict actual
skill requirements.

## Research questions

| ID | Question |
|---|---|
| RQ1 | Which technical skills are frequently requested together? |
| RQ2 | Which postings have similar requirements despite different titles? |
| RQ3 | Do postings form recurring skill-based profiles when titles are ignored? |
| RQ4 | How well do conventional job titles represent the actual skill requirements? |

**New to this repo? Start with [GETTING_STARTED.md](./GETTING_STARTED.md)** — a walkthrough of
what's been done, how to read the data files, and exactly what to open next for RQ1–4.

The full plan — methods, owners, timeline, dashboard design, report outline, study references —
is in [IT_Job_Market_Project_Plan_v2.md](./IT_Job_Market_Project_Plan_v2.md). This README is only
a quick entry point and a current-status summary.

## Current status

The data pipeline (collection → cleaned, deduplicated postings → skill dictionary → skill
extraction → validation → job-skill matrix) is **done**. The RQ1–RQ4 analyses (association rules,
similarity, clustering, titles-vs-skills, decision tree) and the dashboard are **not started yet** —
that's the next phase.

| Stage | Status | Key numbers |
|---|---|---|
| Data collection | Done | 10,188 raw rows, 8,882 distinct job IDs, 8 job families |
| Cleaning & deduplication | Done | 8,879 postings retained, 6,458 unique description groups |
| Skill dictionary | Done | 440 mining skills (444 total), 6 categories |
| Skill extraction | Done | validated at Precision 89.8% / Recall 97.0% / **F1 93.3%** on 120 sampled postings (scored against an earlier, smaller dictionary — see GETTING_STARTED.md) |
| Job-Skill Matrix | Done | description-level **6,135 rows × 412 columns** (main view), listing-level 8,373 × 412 (duplicate-effect check view) |
| RQ1–RQ4 analyses, dashboard | **Not started** | next step for whoever picks this up |

## Where to start if you're picking up the analysis work

Use the matrix directly — it's already deduplicated, filtered, and uses canonical skill names as columns:

- `outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv` — **main analysis view**, one row
  per unique job posting (reposts collapsed), 412 binary skill columns. Use this for association rules,
  similarity, clustering, and the classifier.
- `outputs/09_job_skill_matrix/job_skill_matrix_listing_level.csv` — **check view**, one row per
  individual posting (reposts included). Run your main analyses on this too and report whether results
  change, per the plan's Step 5.4 design.
- `outputs/09_job_skill_matrix/skill_shortlist_final.csv` — the skill dictionary (canonical name,
  category, status) if you need to look up or group skills by category.
- `outputs/09_job_skill_matrix/matrix_summary.txt` — quick stats on both matrix views.

Both views share the exact same 412 columns, so they're directly comparable.

## Repository layout

```
data/raw/                         Raw scraped files, one per search keyword, never edited
resources/                        Shared rules (title_family_rules.csv)
skill_extraction/                 Original cleaned-dictionary export (kept for audit trail)
scripts/                          Numbered pipeline scripts, run in order from the project root
outputs/                          Every generated file, grouped by the pipeline step that creates it
IT_Job_Market_Project_Plan_v2.md  Full project plan: methods, roles, timeline, references
```

Each step under `outputs/` is produced by one script in `scripts/`. Scripts are numbered in run
order (01, 02, 03, 04, 04b, 05_skill_candidates_v2, 06_extract_skills_v2,
07_make_validation_sample_v2, 09_build_matrix_v2, ...) and read their inputs directly from the
previous step's output folder. Run them from the project root, e.g.:

```powershell
cd data-mining-final
python scripts\04_text_cleaning_and_groups.py
```

## Key design decisions worth knowing before you touch the data

- **Two matrix views, same columns.** The description-level view is the main one — it collapses
  reposted/duplicate postings so a heavily-reposted template job doesn't skew frequency counts, rule
  support, or cluster sizes. The listing-level view exists only to sanity-check whether results change
  with reposts included.
- **The skill dictionary (`skill_shortlist_final.csv`) is hand-curated and evidence-checked**, not a
  generic seed list — every addition, merge, or split was verified against real job-posting text before
  being applied. If you want to add or change a skill, check real posting text first, not just
  intuition.
- **`Artificial Intelligence (AI)` has a known precision ceiling** — some false positives are inherent
  (company branding like "Shield AI", vague marketing language), confirmed by two independent
  validation rounds. This is a documented, accepted limitation, not a bug to chase.
- **No git safety net on generated files.** Everything under `outputs/` is regenerated by rerunning the
  scripts, not hand-edited — if you need to change something, change the script and rerun, rather than
  editing a CSV directly.
