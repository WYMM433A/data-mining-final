"""Build the Job x Skill matrix from the v2 extraction (Step 5.10).

Produces two views per the project plan's Step 5.4 design:
- description-group level (main view; template reposts do not inflate counts)
- listing level (check view; every individual posting)

The eligible column set is computed ONCE from the description-level (deduplicated)
population, then applied identically to both views, so "description-level vs.
listing-level" comparisons aren't confounded by a shifting feature set. The dictionary
was already carefully hand-curated (Step 5.7), so the only mining-time cut is a low
absolute-count floor to avoid single-digit noise columns, not a relative-share floor
that would drop real, clean technologies for being merely uncommon.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

JOBS_DESC = Path("outputs/04_text_cleaning_and_groups/jobs_desc.csv")
JOBS_LISTING = Path("outputs/04_text_cleaning_and_groups/jobs_listing.csv")
JOB_SKILL_LISTING = Path("outputs/06_skill_extraction_v2/job_skill_listing.csv")
SHORTLIST = Path("outputs/09_job_skill_matrix/skill_shortlist_final.csv")
OUT_DIR = Path("outputs/09_job_skill_matrix")
MIN_ABSOLUTE_COUNT = 15
MAX_SHARE = 0.60
MIN_SKILLS_PER_ROW = 3


def select_columns(jobs_desc: pd.DataFrame, group_pairs: pd.DataFrame) -> list[str]:
    """Decide the final column set once, from the deduplicated description-level population."""
    family_rows = jobs_desc.loc[~jobs_desc.job_family.eq("other")].copy()
    n_skills = group_pairs.groupby("description_group_id").canonical_skill.nunique()
    family_rows["n_skills"] = family_rows["description_group_id"].map(n_skills).fillna(0).astype(int)
    skilled = family_rows.loc[family_rows.n_skills.ge(MIN_SKILLS_PER_ROW)]

    eligible_pairs = group_pairs[group_pairs.description_group_id.isin(set(skilled.description_group_id))]
    skill_counts = eligible_pairs.groupby("canonical_skill").description_group_id.nunique()
    share = skill_counts / max(len(skilled), 1)
    selected = skill_counts[(skill_counts >= MIN_ABSOLUTE_COUNT) & (share <= MAX_SHARE)].index.tolist()
    return sorted(selected)


def build_view(jobs: pd.DataFrame, pairs: pd.DataFrame, id_col: str, view_name: str, selected: list[str]):
    input_count = len(jobs)
    family_rows = jobs.loc[~jobs.job_family.eq("other")].copy()

    n_skills = pairs.groupby(id_col).canonical_skill.nunique()
    family_rows["n_skills"] = family_rows[id_col].map(n_skills).fillna(0).astype(int)
    skilled = family_rows.loc[family_rows.n_skills.ge(MIN_SKILLS_PER_ROW)].copy()

    column_names = [s.replace(" ", "_").replace("/", "-") for s in selected]
    name_map = dict(zip(selected, column_names))

    relevant_pairs = pairs[pairs.canonical_skill.isin(selected) & pairs[id_col].isin(set(skilled[id_col]))]
    pair_set = set(zip(relevant_pairs[id_col], relevant_pairs.canonical_skill))
    rows = []
    for _, row in skilled.sort_values(id_col).iterrows():
        rid = row[id_col]
        record = {"job_id": row.get("id", rid), "description_group_id": row["description_group_id"],
                  "job_family": row["job_family"]}
        for skill in selected:
            record[name_map[skill]] = int((rid, skill) in pair_set)
        rows.append(record)

    wide = pd.DataFrame(rows)
    if wide.empty:
        wide = pd.DataFrame(columns=["job_id", "description_group_id", "job_family", *column_names])
    n_used = wide[column_names].sum(axis=1) if column_names else pd.Series(0, index=wide.index, dtype=int)
    wide = wide.loc[n_used.ge(MIN_SKILLS_PER_ROW)].reset_index(drop=True)

    wide.to_csv(OUT_DIR / f"job_skill_matrix_{view_name}.csv", index=False)
    (OUT_DIR / f"matrix_columns_{view_name}.json").write_text(json.dumps(column_names, indent=2), encoding="utf-8")

    data, indices, indptr = [], [], [0]
    for _, row in wide.iterrows():
        for idx, name in enumerate(column_names):
            if int(row[name]) == 1:
                data.append(1)
                indices.append(idx)
        indptr.append(len(data))
    np.savez_compressed(
        OUT_DIR / f"job_skill_matrix_{view_name}.npz",
        format=np.asarray("csr"), shape=np.asarray([len(wide), len(column_names)], dtype=np.int64),
        data=np.asarray(data, dtype=np.uint8), indices=np.asarray(indices, dtype=np.int32),
        indptr=np.asarray(indptr, dtype=np.int32),
    )

    density = wide[column_names].to_numpy().mean() if column_names and len(wide) else 0.0
    per_row = wide[column_names].sum(axis=1) if column_names and len(wide) else pd.Series(dtype=int)
    summary = [
        f"=== {view_name} view ===",
        f"Input rows: {input_count}",
        f"After excluding 'other' family: {len(family_rows)}",
        f"After >=3 raw mining-eligible skills: {len(skilled)}",
        f"Final matrix rows: {len(wide)}",
        f"Skill columns: {len(column_names)}",
        f"Density: {density:.4%}",
        f"Median skills per row: {per_row.median() if len(per_row) else 0}",
        "Rows per family:",
        wide.job_family.value_counts().sort_index().to_string() if len(wide) else "(none)",
        "Top 20 skills:",
        wide[column_names].sum().sort_values(ascending=False).head(20).to_string() if column_names and len(wide) else "(none)",
    ]
    return wide, column_names, summary


def main() -> None:
    shortlist = pd.read_csv(SHORTLIST)
    mining_skills = set(shortlist.loc[shortlist.mining_status == "include", "canonical_skill"])

    pairs_all = pd.read_csv(JOB_SKILL_LISTING)
    pairs = pairs_all[pairs_all.canonical_skill.isin(mining_skills)].copy()

    jobs_desc = pd.read_csv(JOBS_DESC, low_memory=False)
    jobs_listing = pd.read_csv(JOBS_LISTING, low_memory=False)

    # Description-group level (main view): dedupe to one row per group before counting.
    group_pairs = pairs[["description_group_id", "canonical_skill"]].drop_duplicates()

    # Column set decided once, from the deduplicated (bias-resistant) description-level population.
    selected_columns = select_columns(jobs_desc, group_pairs)
    print(f"Unified column set (from description-level population): {len(selected_columns)} skills")

    _, _, summary_group = build_view(jobs_desc, group_pairs, "description_group_id", "description_level",
                                      selected_columns)

    # Listing level (check view): every individual posting, same columns as the main view.
    listing_pairs = pairs.rename(columns={"job_id": "id"})
    _, _, summary_listing = build_view(jobs_listing, listing_pairs, "id", "listing_level", selected_columns)

    all_summary = summary_group + [""] + summary_listing
    (OUT_DIR / "matrix_summary.txt").write_text("\n".join(all_summary), encoding="utf-8")
    print("\n".join(all_summary))


if __name__ == "__main__":
    main()
