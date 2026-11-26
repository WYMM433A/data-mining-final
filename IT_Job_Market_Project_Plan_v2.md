# Beyond Job Titles: Discovering Hidden Skill Relationships and Job Profiles in US IT Job Postings

**Course:** Introduction to Data Mining
**Team:** 3 members
**Duration:** about one month (adjust the week numbers to your real deadline)
**Data format:** CSV files only (no SQL database)
**Final product:** CSV result files, an interactive dashboard, a final report, and a presentation

---

## Current status (updated 2026-11-26)

Steps 5.1–5.10 (collection through the job-skill matrix) are **done**. The rest of this document is still the project's design and is accurate as written, except where a step below has an **Actual:** note — those mark the few places where the real implementation used different file names or a different method than originally planned, so the reasoning in each step's "what/why/how" still applies even though the exact file to open has changed.

| Stage | Status | Key numbers |
|---|---|---|
| Collection (Section 3) | Done | 10,188 raw rows across 34 source files, 8,882 distinct job IDs |
| Steps 5.1–5.3 — inspect, merge, quality filters | Done | 8,879 postings retained |
| Step 5.4 — deduplication | Done (extended beyond the original plan) | 6,458 unique description groups after an added Step 4b pass; see the Step 5.4 note |
| Step 5.5 — job family from title | Done | 8 families + `other`, rules in `resources/title_family_rules.csv` |
| Step 5.6 — text cleaning | Done | boilerplate and repeated company templates removed, protected sentences logged |
| Step 5.7 — skill dictionary | Done, by a different method than planned | **440 mining skills** (444 total incl. 4 excluded) in `outputs/09_job_skill_matrix/skill_shortlist_final.csv`; see the Step 5.7 note |
| Step 5.8 — extraction | Done | `outputs/06_skill_extraction_v2/` |
| Step 5.9 — validation | Done | Precision 89.8%, Recall 97.0%, **F1 93.3%** on 120 postings — clears the 85% target; see the Step 5.9 note on rescoring |
| Step 5.10 — job-skill matrix | Done | description-level **6,135 rows × 412 columns** (main view), listing-level 8,373 rows × 412 columns (check view) |
| Step 5.11 and RQ1–RQ4 (Section 5.11, Section 6) | **Not started** | This is the next work: descriptive stats, then association rules, similarity, clustering, and the decision tree |

**Start here for RQ1–RQ4 work:** `outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv` (main analysis view) and `_listing_level.csv` (duplicate-effect check), both already filtered and using canonical skill names as columns.

---

## 0. How to read this document

This plan answers five things for each part of the project: **what to do, why, how, who does it, and where to study it.**

Three decisions shape everything else:

1. **Every method is chosen to answer a specific research question.** A method that does not answer a question is not in the project (Section 2 explains what we deliberately leave out).
2. **Data is stored in CSV files only.** The three-table design from the earlier plan (`jobs`, `skills`, `job_skills`) is kept, but each table is a CSV file. A database adds setup work and does not change any result at this size (about 6,000–8,000 postings).
3. **A decision tree classifier is added** to answer RQ4 from a second angle: how well do skills determine the job family?

---

## 1. Project at a glance

### 1.1 Objective
Analyze recently advertised US IT jobs to find which skills appear together, which jobs have similar requirements despite different titles, which skill-based profiles exist, and how well conventional job titles describe what jobs actually require.

### 1.2 Research questions

| ID | Question |
|---|---|
| **RQ1** | Which technical skills are frequently requested together? |
| **RQ2** | Which postings have similar requirements despite different titles? |
| **RQ3** | Do postings form recurring skill-based profiles when titles are ignored? |
| **RQ4** | How well do conventional job titles (job families) represent the actual skill requirements? |

### 1.3 In scope
- US IT job postings from the past month, collected with the Apify service (with instructor approval) from 8 job families.
- Technical skills extracted from the description text.
- Four analyses: association rules, similarity, clustering, and the titles-versus-skills comparison (with a decision tree).
- A CSV-based interactive dashboard.

### 1.4 Out of scope
- Non-IT jobs, non-US jobs, non-English postings.
- Salary prediction or a hiring/recommendation system for real users.
- A database server, cloud hosting, or user accounts.
- Deep learning, large neural models, or SVM-style black boxes.
- Any claim about the whole US IT job market. The data shows only what was advertised in the collection window under our search terms.
- Collecting data with logins, cookies, or by bypassing access controls.

---

## 2. The right tool for the right purpose

| Question | What we need to know | Tool | Why this tool |
|---|---|---|---|
| **RQ1** | Which skills co-occur, and how strongly? | **Association rules (FP-Growth)** with support, confidence, lift | Built for "items that appear together in baskets". Each posting is a basket of skills. Lift tells us if the link is real or just because both skills are common. |
| **RQ2** | Which postings ask for similar things? | **Jaccard similarity** on skill sets (main), cosine (comparison) | Skill data is *asymmetric binary*: two postings both lacking Kubernetes is not a similarity. Jaccard ignores shared absence, which is exactly this case. |
| **RQ3** | Are there recurring skill profiles? | **Hierarchical clustering with Jaccard distance** (main) and **K-means on reduced data** (second opinion) | Hierarchical + Jaccard fits binary data; K-means is the standard baseline. If two different methods find similar groups, the profiles are more believable. |
| **RQ4a** | Do discovered profiles match job families? | **Cluster × family crosstab, ARI, NMI, purity** | These are the standard tools for comparing a clustering against known labels. |
| **RQ4b** | How well do skills predict the job family, and which families get confused? | **Decision tree classifier** with confusion matrix, macro-F1, cross-validation | Gives a direct accuracy number for "titles vs skills" and readable rules about which skills separate families. |
| (All) | Can we trust the data? | Descriptive statistics, duplicate analysis, **skill extraction validation (precision, recall, F1)** | Every result depends on the extracted skills. |

### Deliberately NOT used (and why)

| Method | Why we leave it out |
|---|---|
| Apriori vs ECLAT comparison | Gives the same answer as FP-Growth; adds no insight. (Apriori may be run once on a small subset only to confirm results match.) |
| K-medoids, DBSCAN/OPTICS/HDBSCAN, spectral, biclustering | We have no question they answer that hierarchical + K-means cannot. DBSCAN-type methods work poorly on sparse, high-dimensional binary data. |
| SVM, neural networks, ensembles | We do not need maximum prediction accuracy; we need readable explanations. A decision tree gives rules. |
| Chi-square as the main RQ4 test | With thousands of rows it is almost always significant and says nothing about strength. ARI/NMI and the crosstab are more informative. |
| SQL database | The data fits in CSV files; a database adds work but no new result. |
| Salary analysis | Salary is mostly missing and not part of our questions. |

**Optional only if time remains (clearly marked in each section):** Hopkins statistic, Naïve Bayes as a comparison to the decision tree, closed itemsets if the rule list is too redundant.

---

## 3. Data collection plan

### 3.1 Settings

| Setting | Decision |
|---|---|
| Source | Apify LinkedIn-jobs actor (the one tested: no login/cookies needed; confirm name, version, and price on its page) |
| Approval | **Written instructor approval before collecting** (email saved). Public job-posting fields only. |
| Country | United States |
| Date filter | Past month (set in the LinkedIn search URL or the actor's filter) |
| Per-keyword limit | Same limit for every keyword (target 300; check the actor's maximum-results setting) |
| Output | CSV or JSON, one file per keyword, never edited after export |
| Run order | One keyword per run; wait for "Succeeded" before the next |
| Budget | Set a maximum cost per run and a total cap before starting. The tested actor was listed at about $2 per 1,000 results; confirm the current price. |

**Why the same limit for every keyword:** otherwise popular titles (Software Engineer) swamp rare ones (NLP Engineer), and every later result is biased toward them.

**Why a past-month filter:** your tested run without a filter returned postings up to 8 months old. One consistent window makes the data comparable.

### 3.2 The 8 job families and 34 keywords

| No. | Job family | Keywords | Owner |
|---|---|---|---|
| 1 | Data & Business Intelligence | Data Analyst; Business Intelligence Analyst; BI Developer; Reporting Analyst; Analytics Engineer | **Member 1** |
| 2 | AI & Machine Learning | Data Scientist; Machine Learning Engineer; AI Engineer; NLP Engineer; Computer Vision Engineer | **Member 1** |
| 3 | Software Development & Engineering | Software Engineer; Frontend Developer; Backend Developer; Full Stack Developer; Mobile App Developer | **Member 2** |
| 4 | Cloud, DevOps & Infrastructure | DevOps Engineer; Cloud Engineer; Site Reliability Engineer; Platform Engineer; Infrastructure Engineer | **Member 2** |
| 5 | Cybersecurity & Networking | Cybersecurity Analyst; Security Engineer; Network Engineer; Information Security Analyst | **Member 3** |
| 6 | Database & Data Infrastructure | Data Engineer; Database Administrator; Database Developer; Data Architect | **Member 3** |
| 7 | QA & Software Testing | QA Engineer; Automation Test Engineer; Software Test Engineer | **Member 3** |
| 8 | Enterprise Software & IT Systems | ERP Consultant; Salesforce Developer; SAP Consultant | **Member 3** |

Split: Member 1 = 10 keywords, Member 2 = 10, Member 3 = 14. **Why Member 3 gets more:** collection runs are mostly waiting time, and Member 3's analysis work (clustering, classification) starts later than the others'.

**Priority tiers (use if time or budget runs short):**
- **Tier A (must collect):** the first two keywords of every family (16 keywords). This keeps all 8 families represented.
- **Tier B (collect if possible):** the remaining 18 keywords.

### 3.3 Expected size
- Raw: up to 34 × 300 = about **10,000** postings.
- After cleaning and de-duplication: about **60–75%**, so roughly **6,000–7,500** (estimate, replace with real numbers).
- Minimum acceptable: about **3,000** usable postings and about **100–150 per job family** (needed for the classifier). Families with fewer are merged or excluded from the classifier and reported.

### 3.4 Collection procedure (step by step)
1. **Day 1:** get instructor approval; agree on actor, version, settings, file names, and the shared folder. Create one collection log (CSV) all three members fill in.
2. **Day 1–2:** **pilot** with 3 keywords from different families (for example Data Analyst, DevOps Engineer, QA Engineer). Check: titles match the keyword, full descriptions, past-month dates, many companies, cost per 100 results, any personal data columns.
3. **Gate G1 (end of Day 2–3):** continue only if the pilot passes. If not, activate the Kaggle backup (Section 12).
4. **Days 2–6:** each member runs their keywords one by one with identical settings.
5. After every run: open the file, count rows, spot-check 5 postings, and add a row to the collection log.
6. **Stop rules:** if a run is blocked, fails repeatedly, or exceeds the budget, stop. Do not use workarounds. Report it to the team.
7. **Gate G2 (end of Day 7):** at least ~6,000 raw postings and all 8 families present. Otherwise, add Tier B keywords, lower targets, or use the Kaggle backup for missing families.

**Collection log columns:** keyword, job family, member, run date and time, actor name and version, country, date filter, result limit, rows returned, cost, file name, notes.

**Personal data rule:** never keep recruiter or poster names, photos, or profile links. Drop these columns when loading.

---

## 4. CSV files (the whole data model)

### 4.1 Folder layout
```
data/raw/                         exported files, never edited
resources/                        shared title-family rules (skill_dictionary.csv here is an old,
                                   superseded draft — the real dictionary lives in outputs/09_job_skill_matrix/)
skill_extraction/                 original cleaned-dictionary export (provenance/audit trail)
scripts/                          numbered pipeline scripts and shared path config
outputs/00_source_profile/         merged source profile and diagnostics
outputs/01_collection_log/         Step 1 outputs
outputs/02_quality_filters/        Step 2 outputs and review files
outputs/03_job_family/             Step 3 assignments and review files
outputs/04_text_cleaning_and_groups/ Step 4 (+ 4b dedup pass) listing and description tables — current, authoritative
outputs/05_skill_candidates_v2/    Step 5 candidate terms (1,608 raw candidates, no job IDs)
outputs/06_skill_extraction_v2/    Step 5.8 extracted skills: job_skill_groups.csv, job_skill_listing.csv, skills_summary.csv
outputs/07_validation_sample/      Step 5.9 annotation files (key kept separate), both annotation rounds
outputs/09_job_skill_matrix/       Step 5.7 dictionary (skill_shortlist_final.csv) + Step 5.10 matrix and feature files
outputs/10...16/                 analysis and dashboard outputs by step — not created yet
outputs/attrition.csv              shared row-removal log
```

Generated files are grouped by the step that creates them. Later scripts read inputs directly from earlier step folders. (An older `outputs/05_skill_candidates/` and `outputs/06_skill_extraction/`, without the `_v2` suffix, and a `08_validation_results/` folder from an earlier, abandoned scoring approach may still exist from the first pipeline attempt — the `_v2` folders and the validation rounds recorded directly in `07_validation_sample/` are the current, correct ones to use.)

### 4.2 Core data files

**`jobs.csv`** — one row per retained listing

| Column | Meaning |
|---|---|
| `job_id` | Unique ID (from the source) |
| `source_url` | Posting link without tracking parameters |
| `original_title` | Title exactly as advertised |
| `job_family` | One of the 8 families, **assigned from the title by rules, not from the search keyword** |
| `company`, `location`, `posted_date` | From the source |
| `employment_type`, `seniority_raw`, `industry` | From the source (seniority is often "Not Applicable") |
| `workplace_type` | Remote / Hybrid / Onsite / Unknown, only if the source supports it |
| `description_original` | Original text, never edited |
| `description_clean` | Cleaned text (markup and template sentences removed) |
| `scraped_date` | Collection date |
| `description_group_id` | ID shared by listings with the same description (template ads) |
| `duplicate_status` | Unique / Potential duplicate / Duplicate |
| `n_skills` | Number of skills found |

**`job_search_keywords.csv`** — which searches found each listing (`job_id`, `search_keyword`, `search_family`). A posting can be found by several keywords, so this must be its own table.

**`skills.csv`** — the dictionary: `skill_id`, `skill_name`, `category`, `aliases`, `n_jobs`, `share_of_jobs`, `use_in_mining` (true/false), `exclusion_reason`.

**`job_skills.csv`** — `job_id`, `skill_id`, `evidence` (the text snippet), `extraction_method`. One row per job and skill.

**`job_skill_matrix.csv`** — one row per job, one 0/1 column per skill used in mining, plus `job_id` and `job_family` (for interpretation only, never as a feature).

**Actual file names (the core model above is right, the names differ):**

| Planned name | Actual file | Notes |
|---|---|---|
| `jobs.csv` | `outputs/04_text_cleaning_and_groups/jobs_desc.csv` (one row per unique description, **use this for mining**) and `jobs_listing.csv` (one row per posting, has `job_id`) | `description_clean` keeps skill/qualification-bearing sentences; `description_similarity` strips all repeated templates for similarity work |
| `skills.csv` | `outputs/09_job_skill_matrix/skill_shortlist_final.csv` (dictionary: `canonical_skill`, `category`, `mining_status`, `family_adjacent`, `parent`, `reason`) + `outputs/06_skill_extraction_v2/skills_summary.csv` (real counts: `n_descriptions`, `n_listings`, `share_of_descriptions`) | No `skill_id`; `canonical_skill` is the key everywhere |
| `job_skills.csv` | `outputs/06_skill_extraction_v2/job_skill_groups.csv` (description-group level) and `job_skill_listing.csv` (listing level, has `job_id`) | Both have `canonical_skill`, `category`, `mining_status`, `match_alias`, and an `evidence` snippet — the link-table design is unchanged, only the name and the description/listing split |
| `job_skill_matrix.csv` | `outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv` (main view) and `_listing_level.csv` (check view), plus matching `.npz` sparse versions, `matrix_columns_*.json`, `matrix_summary.txt` | Both views share the exact same 412 columns, computed once from the description-level population, so they are directly comparable |

Everything else in this section (why three files, not one flat table; `job_id`/`skill_id`-style keys) is unchanged in the real data — only the file names differ from the original plan.

### 4.3 Result files
Analysis outputs are grouped by step: association rules in `outputs/11_association_rules/`, similarity in `outputs/12_similarity/`, clustering in `outputs/13_clustering/`, title-family comparison in `outputs/14_titles_vs_clusters/`, classifier outputs in `outputs/15_decision_tree/`, and extraction validation in `outputs/08_validation_results/`.

### 4.4 Why the three-file design stays even with CSV
"One job has many skills, one skill appears in many jobs" cannot be stored in one flat row without repeating or packing data. `job_skills.csv` is the link file, and the matrix is generated from it.

---

## 5. Step-by-step data pipeline

Each step lists **what, why, how, check, owner**.

### Step 5.1 — Inspect the raw files (Day 6–7, Member 1 with everyone's files)
- **What:** For each raw file record rows, columns, missing values, duplicate IDs/URLs, number of unique titles, companies, locations, date range, description length, and obviously irrelevant postings.
- **Why:** Problems found now cost minutes; found later they cost days.
- **Check:** One inspection table per file; flag any file where the date range, location, or columns differ from the agreed settings.
- **Status: Done.** 10,188 raw rows across 34 files, 8,882 distinct LinkedIn job IDs (1,183 found by multiple search terms). Two search-term variants (`Security Engineeer`, `Database+Administrator`) were accepted as typos/encoding artifacts rather than reprocessed.

### Step 5.2 — Merge into one table (Member 1)
- Convert all files to one common set of columns (the `jobs.csv` columns). Add `search_keyword` and `search_family` from the file/log.
- Drop personal and unnecessary columns (poster details, HTML, apply links, tracking IDs, company logos and addresses).
- Remove tracking parameters from links; convert dates to one format.
- **Check:** row count before and after merge matches the collection log.
- **Status: Done.** `scripts/merge_and_profile.py` → `outputs/00_source_profile/jobs_slim.csv`.

### Step 5.3 — Quality filters (Member 1)
Apply in this order; record removals in the attrition table and preserve review flags separately:

| Step | Rule | Why |
|---|---|---|
| 1 | Missing title or description removed | Cannot analyze skills without text |
| 2 | Description shorter than 50 words removed | Too little information |
| 3 | Language heuristic candidates flagged for manual review; keep records confirmed to be English | Dictionary is English; the heuristic can produce false positives |
| 4 | Posting dates compared with the available contributor date proxy; flag suspicious rows for review, do not treat the proxy as a confirmed collection date | Collection-run dates are missing |
| 5 | Irrelevant postings flagged and reviewed (for example non-IT roles that matched a keyword), then removed | Keeps the dataset on-topic |

Do not invent missing values. Salary and workplace type stay empty/Unknown when missing.

**Status: Done.** `scripts/02_quality_filters.py` → `outputs/02_quality_filters/jobs_filtered.csv`. Removed 1 row with empty title/description and 2 descriptions under 50 words; non-English and length-outlier flags were kept for review, not auto-removed (see `non_english_review.csv`).

### Step 5.4 — Deduplication (Member 1, reviewed by Member 2)

| Rule | Action |
|---|---|
| Same job ID or same cleaned URL | Same listing: keep one, keep all search keywords in `job_search_keywords.csv` |
| Same company + title + location | Same listing: keep one |
| Same company + identical description, different locations | **Group with a shared `description_group_id`; do not delete automatically** |
| Same company + near-identical description (very high text similarity) | Group as potential duplicates |
| Same title alone | Never enough evidence |

**Two analysis views:**
- **Description-level (main view):** one representative per description group. Used for rules, similarity, clustering, and classification, so template ads do not dominate.
- **Listing-level (check):** every listing. Run the main analyses on this too and report whether results change.

Your test run showed why: in 100 postings, 7 repeated an earlier description from the same company.

**Status: Done, extended beyond the original rule table above.** `scripts/04_text_cleaning_and_groups.py` builds `description_group_id` by **exact description hash**. Near-duplicates at cosine similarity ≥0.95 are flagged (not merged) in `near_duplicate_edges.csv` — 373 pairs. **Actual (added this session, `scripts/04b_merge_near_duplicates.py`, "Step 4b"):** those 373 pairs were classified by title + location match, not similarity score alone — only 74 pairs (20%) sharing the same normalized title *and* location were confirmed true duplicates and merged; 90 pairs (24%, same title/different location — same requisition posted to multiple offices) and 209 pairs (56%, different titles sharing a company boilerplate template) were left separate as genuinely distinct postings. Result: `jobs_desc.csv` has **6,458** unique description groups; `jobs_listing.csv` stays at 8,879 listings.

### Step 5.5 — Assign the job family from the title (Member 1)
- Write an **ordered list of title patterns**, first match wins (for example "data engineer" → Database & Data Infrastructure; "machine learning" → AI & ML).
- Review the 50 most common unmatched titles and a random sample of 50 matched ones; add exclusion patterns for false matches.
- Postings that match no family are flagged `other` and kept out of the classifier.
- **Why from the title and not the search keyword:** a search can return loosely related jobs, and the same posting can come from several searches. RQ4 is about titles, so the family must come from the title.

**Status: Done.** `scripts/03_assign_job_family.py`, rules in `resources/title_family_rules.csv` → `outputs/03_job_family/jobs_family.csv`.

### Step 5.6 — Text cleaning (Member 1)
- Remove HTML remnants, links, and extra whitespace. Keep `description_original` untouched.
- Remove explicit legal/benefits boilerplate. For repeated company sentences, preserve sentences with skill-dictionary terms or education, qualification, and experience signals in the skill-analysis text; log these protected sentences for review. Strip repeated company templates from the separate similarity text to reduce template-driven similarity.
- Derive education and experience indicators from the untouched raw description so text cleaning cannot erase their evidence.
- Check by reading 20 cleaned descriptions.

**Status: Done.** `scripts/04_text_cleaning_and_groups.py` → `outputs/04_text_cleaning_and_groups/jobs_desc.csv` / `jobs_listing.csv`. One real bug was found and fixed mid-project: the original skill-protection pattern referenced the old, superseded 197-skill `resources/skill_dictionary.csv` and missed the common "experience + verb-ing + preposition" phrasing (e.g. "experience working with X"); both were fixed and Step 4 rerun, recovering 447 previously wrongly-stripped skill-bearing sentences (confirmed by direct before/after comparison).

### Step 5.7 — Build the skill dictionary (Member 2 leads, Member 1 supports)
- **Seed lists:** O\*NET Technology Skills, ESCO, programming-language/framework lists, the Stack Overflow tag list.
- **Data-driven additions:** list frequent capitalized or tool-like terms in your own descriptions, keep those that are real skills.
- **Categories:** programming language, frontend, backend, database, cloud, DevOps, data engineering, AI/ML, cybersecurity, testing, enterprise platforms, other.
- **Aliases:** map alternative spellings to one name (K8s → Kubernetes). Do not merge different things (Java ≠ JavaScript).
- **Ambiguous names** need rules: R, Go, C, Rust, Swift, Spark, Excel (verb), Oracle. Use exact-case matching and context.
- **Why dictionary-based:** simple, explainable, and every extracted skill can be traced to evidence. It is the right start for a one-month project.

**Status: Done, by a different method than the seed-list approach above.** Instead of starting from O\*NET/ESCO seed lists, this project started from an existing LLM-assisted cleaned dictionary (964 candidate skills, in `skill_extraction/` — kept for provenance), audited it against real job text, and scoped it down to a hand-curated mining dictionary: **`outputs/09_job_skill_matrix/skill_shortlist_final.csv` — 444 total skills, 440 marked `mining_status = include`** (4 excluded after evidence review: `Statistics`, `alerting`, `guardrails`, `playbooks`). A later cross-check against an external technology taxonomy (checking ~280 candidate names against real posting text) added 21 more confirmed-real skills (e.g. `Active Directory`, `Azure SQL`, `React Native`, `jQuery`). Categories (6 used, out of the project's 10-category taxonomy; Certifications and Standards & Compliance excluded by scope decision):

  | Category | Count |
  |---|---|
  | Platforms & Infrastructure | 108 |
  | Software & Tools | 100 |
  | Frameworks & Libraries | 72 |
  | Technical Concepts | 69 |
  | Technical Practices | 53 |
  | Programming Languages | 38 |
  | **Total (include)** | **440** |

  Ambiguous names (R, C, Oracle, Snowflake, Chef, Puppet, RAG, MCP, and 23 more — 29 total) use **context-cue matching** (a nearby related word must also be present) instead of plain substring search, going further than the plan's "exact-case matching" for these specific terms.

### Step 5.8 — Extract skills (Member 2)
For every description: normalize text, search each skill and alias with word boundaries, store the standardized skill and the **evidence snippet**, and write `job_skills.csv`. Technical skills are the focus; soft skills (communication, teamwork) are not part of this IT-skill study unless you decide otherwise.

**Status: Done.** `scripts/06_extract_skills_v2.py` → `outputs/06_skill_extraction_v2/job_skill_groups.csv` (description-group level), `job_skill_listing.csv` (listing level, has `job_id` and the `evidence` snippet), `skills_summary.csv` (real per-skill counts). Alias lists come from `skill_extraction/Normalization & Alias Mapping.csv` plus manual overrides for every merge/split decision. Three match types beyond plain word-boundary matching: **context-cue** (29 ambiguous terms require a nearby related word), **reused regex** (6 terms: R, C, Golang, Swift, Spark, Excel, with validity checks), and **negative checks** (e.g. `Artificial Intelligence (AI)` rejects matches inside hiring-disclosure boilerplate and company-branding patterns). A **compound-overlap suppression** rule stops a multi-word skill's substring from also double-counting as a different standalone skill (found and fixed 3 times: `Azure DevOps` vs. `Azure`/`DevOps`, `Spring Boot` vs. `Spring`, `Vertex AI` vs. `AI` — no exhaustive scan for further cases has been done, so more may exist).

### Step 5.9 — Validate extraction (Member 2 and Member 1, both annotate)
- Sample about **120 postings, 15 per family**. Two people annotate independently which skills each posting really requires, then resolve differences.
- Compute **precision** (extracted skills that are right), **recall** (real skills that were found), and **F1**. Aim for about 85% or higher on both.
- Log the main errors, fix the dictionary, rerun once, and report before/after numbers.
- **Why:** if extraction is wrong, every rule, cluster, and classifier is built on wrong data.

**Status: Done, target met.** `scripts/07_make_validation_sample_v2.py` built the 120-posting stratified sample (`outputs/07_validation_sample/`). Two independent annotation rounds (not two people as planned, but equivalent independent checks): round 1 found and fixed a stale-metadata scoring bug and the compound-overlap bugs above; round 2 scored **Precision 89.8%, Recall 97.0%, F1 93.3%** — clears the 85% target. One decision made during this step: ground truth counts "any genuine mention" rather than only "required" skills, after confirming that distinction (not real extraction errors) was the dominant source of apparent precision loss. **Open item:** the dictionary has grown since this validation round (440 vs. the 372 skills it was scored against) — a fresh validation pass would give a fully current number; treat 93.3% as representative, not literally current. **Confirmed, documented limitation:** `Artificial Intelligence (AI)` precision has a real ceiling from ambiguous real-world usage (company branding like "Shield AI", vague business language) — independently reconfirmed by both annotation rounds, not cheaply fixable with more rules.

### Step 5.10 — Build the job-skill matrix (Member 3)
- From `job_skills.csv`, create one row per job and one 0/1 column per skill.
- **Filter columns:** keep a skill for mining only if it appears in about 1–2% or more of postings (rarer is noise) and in no more than about 60% (more common gives trivial rules). Record excluded skills and the reason in `skills.csv`.
- **Filter rows:** jobs with fewer than 3 skills are kept in the data but excluded from clustering and classification.
- **Check:** matrix dimensions and sparsity (share of zeros). Expect hundreds of columns that are mostly zero. This is normal.

**Status: Done, column filter changed from the plan.** `scripts/09_build_matrix_v2.py` → `outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv` (main view, **6,135 rows × 412 columns**) and `_listing_level.csv` (check view, 8,373 rows × 412 columns) — both views share exactly the same 412 columns, computed once from the description-level population so the two views stay directly comparable. **Actual column filter:** the planned 1–2% relative-share floor was replaced with a low **absolute** floor (≥15 occurrences) — the relative floor was cutting real, hand-curated skills (e.g. PHP, Django, ChatGPT) that happened to be rarer but were already confirmed genuine by evidence review, so a relative floor was double-penalizing them. The ≤60% ceiling was kept but never actually triggered (the most common skill, `Artificial Intelligence (AI)`, tops out around 51%). Row filter (≥3 skills, `job_family != other`) matches the plan.

### Step 5.11 — Descriptive analysis (Member 3, with Member 1)
Use the basic statistics from Lectures 3–4 where they answer a real question:
- Postings per job family (imbalance matters for the classifier).
- Skills per posting: mean, median, skewness, IQR and outliers.
- Description length and outliers.
- Top 30 skills overall and per family.
- Missing-value summary and duplicate rates.

Outputs feed the dashboard overview page and the data-quality report.

**Status: Not started.** This is the next step — use `job_skill_matrix_description_level.csv` as the input.

---

## 6. The data-mining methods in detail

**Status: not started.** Input is ready at `outputs/09_job_skill_matrix/job_skill_matrix_description_level.csv` (main view, 6,135 × 412) and `_listing_level.csv` (check view, 8,373 × 412) — both already use canonical skill names as columns and share the same column set, so no further preprocessing is required before beginning RQ1.

### 6.1 Association rules (RQ1) — Owner: Member 2

**Question:** Which skills appear together?
**Why this method:** Each posting is a basket of skills, which is exactly the setting association mining was designed for. It is the only method in our toolset that finds specific co-occurring skill combinations (for example `{Docker, Kubernetes} → {Terraform}`).

**Steps**
1. Use the description-level view and the mining skill columns only (Step 5.10 filters).
2. Run **FP-Growth** to find frequent itemsets. Start with a minimum support around 2% overall, and about 5% inside a single family (smaller groups need a higher threshold to avoid chance patterns). Limit itemset size to 3–4.
3. Build rules and keep those with confidence of about 0.4 or more and **lift of about 1.2 or more**.
4. **Remove trivial results:** skills that are in most postings (high confidence but lift near 1).
5. Mine **per job family** as well as overall. Compare: which rules are global and which belong to one family?
6. If the rule list is too repetitive, use **closed itemsets** (a pattern is dropped if a larger pattern has the same support).
7. Interpret each important rule in one plain sentence. Rules show association, not cause.

**Evaluation:** report support, confidence, and lift for every rule; the number of itemsets at several support thresholds (for example 1%, 2%, 3%, 5%); a sanity check that the main rules make sense to someone who knows IT.
**Pitfalls:** very low support gives chance patterns; very common skills dominate; symmetric duplicates (A→B and B→A) should be handled consistently.
**Outputs:** `frequent_itemsets.csv`, `rules.csv`, a skill co-occurrence network figure.
**Optional:** run Apriori once on a small subset to confirm the same itemsets as FP-Growth.

### 6.2 Similarity analysis (RQ2) — Owner: Member 2

**Question:** Which postings ask for similar things even when titles differ?
**Why this method:** Similarity measures compare two items directly. For binary skill sets, **Jaccard** (shared skills divided by all skills mentioned in either posting) is the correct measure because shared *absence* carries no information. **Cosine** is a good comparison measure.

**Steps**
1. Represent each posting as its set of mining skills.
2. Compute Jaccard (main) and cosine (comparison) between postings, keeping only the top 10 neighbors per posting so the result stays manageable.
3. Define **cross-title pairs:** postings from **different job families**, or (weaker) the same family with clearly different titles. Never compare a posting with itself or with its own duplicate group.
4. For each pair, list shared skills and skills unique to each posting.
5. **Evaluate with people:** sample about 40 query postings (stratified across families), take the top 5 matches from each method, and have two members independently judge each pair (could one person plausibly fit both jobs?). Write the judging rule first.
6. Report **Precision@5** for each measure, separately for cross-title pairs, plus **Cohen's kappa** between the two judges.

**Pitfalls:** postings with only a few skills match too easily (set a minimum of 3 skills); template ads inflate similarity (use the description-level view); similarity does not mean the jobs are identical.
**Outputs:** `similar_pairs.csv` (job_id pair, Jaccard, cosine, shared skills, different-title flag), the labelled evaluation sample, a short list of the most interesting cross-title examples for the report.

### 6.3 Clustering (RQ3) — Owner: Member 3

**Question:** Do postings form recurring skill profiles when titles are ignored?
**Why these methods:** Clustering groups unlabeled objects. **Hierarchical clustering with Jaccard distance** is the natural fit for binary data and gives a dendrogram that shows structure at several levels. **K-means** is the standard baseline. Agreement between the two strengthens the findings.

**Steps**
1. Use the matrix (Step 5.10), description-level view, jobs with at least 3 skills. Titles and families are **never** features.
2. **Hierarchical clustering:** Jaccard distance, **average linkage** (Ward linkage assumes Euclidean distance and is not suitable for Jaccard). If memory is a problem, use a representative sample, then assign the rest to the nearest cluster.
3. **K-means:** weight skills by how rare they are (TF-IDF style weighting), reduce dimensions with **SVD** (about 20–40 components, check explained variance), then run K-means with several random starts.
4. **Choosing the number of clusters (k):** test a range such as 5–15. Use the dendrogram, the elbow method (K-means), and the silhouette score (use the Jaccard distance for the hierarchical solution). Silhouette values on sparse skill data are often low (0.05–0.30); this is normal, so judge them together with stability and interpretability.
5. **Stability check:** repeatedly cluster random 80% subsets and compare results with ARI. High stability means a trustworthy solution.
6. **Interpret each cluster:** size, most common skills, **most distinctive skills** (share inside the cluster versus overall, i.e. lift), 3–5 representative postings, and the titles/families it contains. Give each cluster a name based on its actual skills, not before looking.
7. **Optional:** compute the Hopkins statistic first to check whether the data has any cluster structure.

**Pitfalls:** do not force a profile story if clusters are unstable; very large "general" clusters are common and should be reported honestly; K-means on raw binary data can be misleading, hence the SVD step and the comparison.
**Outputs:** `cluster_assignments.csv`, `cluster_profiles.csv`, dendrogram, 2-D scatter (from SVD), skill-by-cluster heatmap.

### 6.4 Titles versus profiles (RQ4a) — Owner: Member 3

**Question:** Do discovered profiles agree with job families?
**Why:** Comparing a clustering with known labels is exactly what ARI, NMI, and purity do.

**Steps**
1. Build the **cluster × job-family crosstab** (counts and percentages). This is likely the most informative figure in the project.
2. Compute **ARI** (agreement corrected for chance), **NMI**, and **purity**. Report them for both clustering methods.
3. For each family: the share of its postings in its most common cluster ("title purity"). For each cluster: how many families contribute at least 10% ("title diversity").
4. Interpret: **low agreement is a finding, not a failure.** It means skill profiles cross title boundaries.

**Outputs:** `family_cluster_crosstab.csv`, `cluster_vs_family_scores.csv`, plus examples of families that split into several profiles and profiles that mix families.

### 6.5 Classification with a decision tree (RQ4b) — Owner: Member 3, reviewed by Member 1

**Question:** How well do skills alone predict the job family, and which families get confused?
**Why this method:** Clustering shows which groups exist. Classification measures how much a title is *determined* by skills. It gives a single accuracy-style number, a list of confusable families, and **readable rules**. A decision tree is the right model here because it is interpretable (the goal) and works on binary features. We do not need a more accurate black-box model.

**Setup**
- **Target:** `job_family` (from the title rules, excluding `other`). **Features:** the binary skill columns only. No title words, company, or description text.
- **Baseline:** always predict the most common family. The tree must beat this to mean anything.
- **Validation:** **stratified 5-fold cross-validation, with folds grouped by description group** (or company) so near-identical postings never appear in both training and test data. This avoids falsely high scores.
- **Class imbalance:** families have very different sizes, so use balanced class weights and report **macro-F1** (average F1 across families) in addition to accuracy.
- **Controlling overfitting:** limit tree depth, require a minimum number of postings per leaf, and optionally prune after growing (these are the pre-pruning and post-pruning ideas from Lecture 9–10). Pick the settings by cross-validation.
- **Splitting measure:** use Gini; compare with entropy (information gain) once and note the difference.

**Outputs and interpretation**
- Confusion matrix (normalized by true family): which families are mistaken for which? These confusions *are* the finding, for example Data Engineer vs Backend, or AI Engineer vs Data Scientist.
- Per-family precision, recall, and F1.
- The tree's rules in readable form, and the top skills that separate families.
- A short comparison: low accuracy for a family means its postings do not have a distinctive skill set, so the title does not tell you what the job needs.

**Important caveat to state in the report:** the labels themselves come from titles, so the score measures *how much skills explain titles*, not "truth".
**Optional (small):** a Bernoulli **Naïve Bayes** classifier as a quick comparison, since it is the other basic classifier in the syllabus and takes a few lines of code.
**Outputs:** `classifier_scores.csv`, `classifier_confusion_matrix.csv`, `tree_rules.txt`, and the tree figure (shallow version for the report).

---

## 7. Evaluation summary

| Component | How we evaluate it | Success looks like |
|---|---|---|
| Data quality | Attrition table, duplicate rates, missing-value summary | Every removal step documented |
| Skill extraction | Two annotators on ~120 postings; precision, recall, F1 | About 85% or higher, with errors listed |
| Association rules | Support, confidence, lift; sanity review | Several interpretable rules with lift clearly above 1; results shown globally and per family |
| Similarity | Precision@5 from two judges, Cohen's kappa; cross-title subset | Clear comparison of Jaccard vs cosine with honest limits |
| Clustering | Silhouette, elbow/dendrogram, stability (ARI across resamples), interpretability | One chosen k with a stable, nameable set of profiles |
| Profiles vs titles | Crosstab, ARI, NMI, purity | A clear statement of where titles and skills agree or not |
| Classifier | Cross-validated macro-F1 vs baseline; confusion matrix | Beats baseline; confusions explained |
| Duplicates effect | Description-level vs listing-level results | Differences reported |

---

## 8. Dashboard (reads the CSV result files only)

Build with Streamlit and Plotly. Precompute everything; the app only loads CSV files.

| Page | Content |
|---|---|
| **1. Overview** | Number of unique listings, companies, skills; listings per family; top skills; location and posting-date distribution |
| **2. Skill relationships** | Select a skill and see its related skills with support, confidence, and lift; skill network; per-family toggle |
| **3. Job similarity** | Select a posting, see top similar postings with scores, shared and different skills; toggle "different job family only" |
| **4. Hidden profiles** | Cluster map, skills defining each cluster, cluster sizes, titles inside each cluster, the family-by-cluster heatmap |
| **5. Titles vs skills** | Confusion matrix and the main tree rules; *optional:* a box where a user ticks skills and sees the predicted family |

Keep the dashboard to roughly 20% of total effort. Build the page shells with sample data in Week 2 so final integration is only file replacement.

---

## 9. Task split for three people

### 9.1 Roles

| Member | Role | Main ownership | Methods to learn |
|---|---|---|---|
| **Member 1** | **Data Lead** | Collection of 10 keywords; merge, quality filters, deduplication, job-family rules; text cleaning; data-quality report; data dictionary; Overview page; reproducibility of the pipeline | Data cleaning and integration, de-duplication, descriptive statistics |
| **Member 2** | **Patterns & Similarity Lead** | Collection of 10 keywords; skill dictionary, extraction, validation; association rules; similarity analysis and its human evaluation; Skill and Similarity pages | Regular-expression text matching, precision/recall/F1, FP-Growth, Jaccard/cosine, Precision@K, Cohen's kappa |
| **Member 3** | **Profiles & Titles Lead** | Collection of 14 keywords; job-skill matrix; clustering; titles-versus-profiles comparison; decision tree classifier; Profiles and Titles pages; assembly of the dashboard | Hierarchical clustering, K-means, SVD, silhouette, ARI/NMI, decision trees, cross-validation, confusion matrix |

### 9.2 Why this split
- Each member owns one complete chain from data to answer: Data → cleaning (M1), Skills → patterns and similarity (M2), Matrix → profiles and titles (M3).
- Heavy early work (cleaning, extraction) sits with M1 and M2, while M3 takes the larger share of collection runs, which are mostly waiting time.
- No one is the only person who understands a stage: every output has a **named reviewer** (Section 9.4).

### 9.3 Week-by-week tasks

| Week | Member 1 — Data | Member 2 — Patterns & Similarity | Member 3 — Profiles & Titles |
|---|---|---|---|
| **1** | Approval request; agree settings; pilot; collect 10 keywords; inspect raw files; merge draft; start job-family title rules | Pilot support; collect 10 keywords; begin skill dictionary (seed lists, categories); study FP-Growth and Jaccard | Collect 14 keywords; keep the collection log; study clustering and decision trees; prepare analysis templates on the pilot data |
| **2** | Quality filters; deduplication (both views); family assignment and review; text cleaning; **data-quality report**; hand over `jobs.csv` (Day 10) | Finish dictionary and extraction; **validation round** (with M1); dictionary fix; hand over `job_skills.csv` and `skills.csv` (Day 10–11) | Build matrix and filters; descriptive statistics; run first clustering and tree tests on partial data; **Gate G3** check with M1 |
| **3** | Descriptive pages (Overview); duplicate-effect comparison (listing vs description view); review of M2's work; start data dictionary | **Association rules** (global and per family); **similarity** and cross-title pairs; start evaluation sample labelling | **Clustering** (both methods, choice of k, stability); **crosstab, ARI/NMI**; **decision tree** with cross-validation |
| **4** | Final reruns from raw data to check numbers; finish data dictionary and collection report; report sections: Data, Preprocessing | Finish human evaluation (Precision@5, kappa); Skill and Similarity dashboard pages; report sections: Association, Similarity | Titles page and Profiles page; assemble dashboard; report sections: Clustering, Titles vs profiles, Classification |
| **All** | Final report edit, presentation, demo rehearsal, limitations section | | |

### 9.4 Cross-review (every output is checked by someone else)

| Output | Owner | Reviewer |
|---|---|---|
| Merged `jobs.csv`, dedup decisions | M1 | M2 |
| Dictionary and extraction | M2 | M1 |
| Matrix, clusters, classifier | M3 | M1 (method), M2 (interpretation) |
| Rules and similarity | M2 | M3 |
| Dashboard | All pages built by owners | M3 assembles; M1 tests from a clean start |

### 9.5 Shared rules
1. One shared folder or Git repository; no one overwrites raw data or another person's files.
2. Every generated file in `outputs/` is created by a saved script, so it can be rerun from the project root.
3. Fixed random seeds for everything with randomness.
4. Short check-ins twice a week and a shared task list.
5. A decision log (one page): every choice such as thresholds, the number of clusters, and removed skills, with the reason.

---

## 10. Timeline and decision gates

| Phase | Days | Output |
|---|---|---|
| Setup, approval, pilot | 1–3 | Settings agreed; pilot report |
| Collection | 2–7 | Raw files; collection log |
| Merge, clean, deduplicate | 6–11 | `jobs.csv`; attrition table |
| Dictionary, extraction, validation | 4–11 | `skills.csv`, `job_skills.csv`; validation results |
| Matrix and descriptive analysis | 10–13 | `job_skill_matrix.csv`; descriptive figures |
| Rules, similarity, clustering, classification | 12–22 | Result CSV files |
| Evaluation, dashboard | 20–26 | Evaluation tables; dashboard |
| Report, presentation, rehearsal | 24–30 | Final report and slides |

| Gate | When | Pass condition |
|---|---|---|
| **G1** | Day 2–3 | Approval received; pilot passes (full descriptions, correct filters, acceptable cost) — **Cleared** |
| **G2** | Day 7 | About 6,000 or more raw postings, all 8 families present — **Cleared** (10,188 raw rows, 8,882 distinct job IDs, all 8 families present) |
| **G3** | Day 11 | About 4,000 or more usable postings (minimum 3,000); about 100–150 per family (otherwise merge or exclude those families from the classifier); extraction F1 about 85% or higher — **Cleared** (6,458 unique description groups / 8,879 listings; F1 93.3%, see Step 5.9 note on rescoring) |
| **G4** | Day 22 | All four analyses produced results; if not, cut optional parts first — **Not reached yet** (RQ1–RQ4 not started) |

**If time runs short, cut in this order:** optional items (Hopkins, Naïve Bayes, closed itemsets, the "predict family" demo box) → Tier B keywords → the dashboard's fifth page → listing-level comparison. **Never cut:** deduplication, extraction validation, the four core methods, or the decision tree.

---

## 11. Where to study each method

The syllabus follows **Han, Kamber & Pei, *Data Mining: Concepts and Techniques* (3rd edition)**, so its chapters are the best match. Chapter numbers can differ slightly by edition, so check your copy's table of contents. Library and online pages can change names, so search by the title if a link moves.

### 11.1 Core references
- **Han, Kamber & Pei — *Data Mining: Concepts and Techniques*:** Ch. 2 (Getting to Know Your Data: attribute types, Jaccard, cosine), Ch. 3 (Data Preprocessing), Ch. 6 (Frequent Patterns and Association Rules), Ch. 8 (Classification: Basic Concepts), Ch. 10 (Cluster Analysis: Basic Concepts, including evaluation).
- **Tan, Steinbach & Kumar — *Introduction to Data Mining*:** the association analysis, decision tree, and cluster analysis chapters give a second explanation in different words.
- **Leskovec, Rajaraman & Ullman — *Mining of Massive Datasets*** (free at mmds.org): the chapters on Finding Similar Items (Jaccard), Frequent Itemsets, and Clustering.

### 11.2 By method

| Method | Read first | Tool documentation | Watch or take |
|---|---|---|---|
| **Cleaning, de-duplication, descriptive statistics** (M1) | Han Ch. 2–3 | pandas documentation: "10 minutes to pandas", merge/join, working with text data | Any short pandas tutorial series |
| **Skill extraction and validation** (M2) | Han Ch. 8, the evaluation-measures section (precision, recall, F1) | Python `re` HOWTO; spaCy PhraseMatcher guide; O\*NET technology skills and ESCO pages for seed lists | A short tutorial on regular expressions |
| **FP-Growth and association rules** (M2) | Han Ch. 6 (downward closure, FP-tree, support/confidence/lift; closed itemsets if used) | mlxtend user guide: frequent patterns (fpgrowth, association_rules) | Coursera "Pattern Discovery in Data Mining" (University of Illinois, taught by Jiawei Han) |
| **Jaccard, cosine, Precision@K, kappa** (M2) | Han Ch. 2 (proximity); MMDS chapter on similar items | scikit-learn: pairwise metrics, `cohen_kappa_score` | A short video on cosine vs Jaccard similarity |
| **Hierarchical clustering, K-means, k selection** (M3) | Han Ch. 10 (K-means, hierarchical/AGNES, linkage, elbow, silhouette) | SciPy hierarchy (linkage, dendrogram, fcluster) and `pdist` with the Jaccard metric; scikit-learn User Guide: Clustering; TruncatedSVD (decomposition) | StatQuest (Josh Starmer) videos on K-means and hierarchical clustering; Coursera "Cluster Analysis in Data Mining" (Illinois) |
| **ARI, NMI, purity, Hopkins** (M3) | Han Ch. 10, evaluation of clustering | scikit-learn: clustering performance evaluation | Search "adjusted Rand index explained" |
| **Decision trees, cross-validation, confusion matrix, F1** (M3) | Han Ch. 8 (entropy, information gain, Gini, pruning, evaluation measures, cross-validation) | scikit-learn User Guide: Decision Trees; Cross-validation; Metrics (confusion matrix, classification report); Naive Bayes (optional) | StatQuest videos on decision trees and the confusion matrix |
| **Dashboard** (M3 + owners) | Streamlit and Plotly getting-started pages | Streamlit documentation; Plotly Python documentation | Streamlit official tutorials |

### 11.3 Suggested learning order (about 2–3 hours per person before starting their method)
1. Read the book section for your method (about 1 hour).
2. Watch one short video to see it explained visually (about 30 minutes).
3. Run the tool's documentation example on a tiny made-up dataset (about 1 hour).
4. Write down in three sentences what the method does, its main parameter, and how you will judge its output. Share it with the team; this becomes your report paragraph.

---

## 12. Risks and the Kaggle backup

| Risk | Impact | Mitigation |
|---|---|---|
| No instructor approval or the actor is blocked | No data | Stop rules; use backup |
| Cost exceeds budget | Fewer postings | Tier A first; cost caps |
| Uneven keyword volumes | Biased results and weak classifier for small families | Same limit per keyword; merge or exclude tiny families; macro-F1 |
| Search keyword is not the real job title | Wrong families | Families assigned from titles |
| Template ads | Inflated frequencies and similarity | Two views (description-level main) |
| Extraction errors | Wrong everything | Validation round and dictionary fix |
| Very common skills | Trivial rules and clusters | Maximum-share filter, lift |
| Clusters unstable | Weak RQ3 | Report honestly; compare two methods; use stability |
| Classifier overfits or leaks | Fake high accuracy | Grouped cross-validation, depth limits, baseline |
| Scope too big | Unfinished project | Tiers, gates, cut list |

**Kaggle backup.** Two datasets were identified: arshkon's *LinkedIn Job Postings (2023–2024)* (about 124,000 postings) and asaniczka's *1.3M LinkedIn Jobs & Skills (2024)*.
- **Triggers:** no approval by Day 3, a failed G1 or G2, or a failed G3 that cannot be repaired by more collection.
- **How it works:** convert both sources to the same `jobs.csv` columns, assign families from titles with the same rules, and the rest of the pipeline is unchanged. Develop and test cleaning on a Kaggle sample while Apify runs, so no one waits.
- **Mixing sources:** Kaggle data is from 2023–2024 and Apify data from 2026. Do not pool them blindly. Either choose one as the main dataset, or analyze them separately and compare. Keep a `source` column in every file.
- **Skills field in asaniczka's data** is messy (inconsistent wording, glued words, non-skills like degrees or licenses). Do not use it as ground truth. Use your own extraction on all sources and use that field only for ideas and cross-checking.

---

## 13. Report and presentation outline

### 13.1 Final report
1. Introduction: problem, motivation, research questions.
2. Data: source, approval, collection settings, keywords and families, size, limitations.
3. Preprocessing: cleaning, deduplication (two views), family assignment, attrition table.
4. Skill extraction: dictionary, method, validation results.
5. Methods and results: association rules; similarity; clustering; titles versus profiles; decision tree classification.
6. Dashboard.
7. Evaluation and discussion: answer RQ1–RQ4 directly.
8. Limitations and ethics: sample bias, search-term bias, extraction errors, similarity ≠ identical jobs, responsible data use.
9. Conclusion and future work.
10. Appendices: collection log, parameters, dictionary excerpt, labelling guideline, decision log.

### 13.2 Presentation story (10–15 minutes)
1. Two job titles, same work: titles are labels.
2. Discover: which skills travel together (best rules and network).
3. Compare: similar jobs with different titles (live example).
4. Group: the hidden profiles (cluster × family heatmap).
5. Evaluate: how well skills predict the title (confusion matrix and tree rules).
6. How much to trust it (validation and limitations), then demo.

> **Closing line:** Job titles tell us what companies call a position. Skill patterns tell us what the position actually requires.

---

## 14. Final checklist

**Data**
- [ ] Instructor approval saved *(not something this pipeline can verify — confirm with your instructor directly)*
- [x] Collection settings and log complete (actor, version, dates, limits, costs)
- [x] Raw files preserved and untouched
- [x] Personal columns removed
- [x] Attrition table complete; duplicate handling documented; both analysis views built
- [x] Job families assigned from titles and reviewed
- [x] At least about 3,000 usable postings; about 100–150 per family or documented merges

**Skills**
- [x] Dictionary documented, with aliases and ambiguous-term rules
- [x] Extraction validated on about 120 postings; precision, recall, F1 reported; one fix round done (rescoring against the current 440-skill dictionary is still open, see Step 5.9)
- [x] Matrix built with documented frequency filters

**Analysis**
- [ ] Association rules: thresholds compared, trivial rules removed, per-family results
- [ ] Similarity: Jaccard and cosine, cross-title pairs, Precision@5 and kappa
- [ ] Clustering: two methods, k chosen with evidence, stability checked, clusters named from skills
- [ ] Profiles vs titles: crosstab, ARI, NMI, purity
- [ ] Decision tree: baseline, grouped cross-validation, macro-F1, confusion matrix, readable rules
- [ ] Listing-level versus description-level comparison

**Delivery**
- [ ] Dashboard runs from the CSV result files on a clean machine
- [ ] Every number in the report matches a result file
- [ ] Limitations section honest about sampling, search terms, extraction errors, and the meaning of similarity
- [ ] Report, slides, demo script, and code folder complete
