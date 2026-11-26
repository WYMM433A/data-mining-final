"""Sample evidence snippets for the 16 'candidate' (generic-leaning) terms for manual hit-review.

For each term flagged mining_status == "candidate" in the shortlist, pulls up to 30 random
real evidence snippets from the Step 5.8 extraction output, so the team can judge whether each
hit is a genuine technical use. Output has a blank judgment column to fill in by hand.

Usage: after filling in `is_real_technical_use` (yes/no) for each row, rerun
`08_score_candidate_review.py` (not yet written) to compute per-term precision and decide
include/exclude, recording the outcome in the shortlist's mining_status/exclusion_reason.
"""

import pandas as pd

GROUPS_PATH = "outputs/06_skill_extraction_v2/job_skill_groups.csv"
OUT_PATH = "outputs/09_job_skill_matrix/candidate_hit_review.csv"
SAMPLE_SIZE = 30
RANDOM_SEED = 42


def main() -> None:
    groups = pd.read_csv(GROUPS_PATH)
    candidates = groups[groups.mining_status == "candidate"]

    samples = []
    for term, grp in candidates.groupby("canonical_skill"):
        n = min(SAMPLE_SIZE, len(grp))
        sampled = grp.sample(n=n, random_state=RANDOM_SEED)
        samples.append(sampled)
    review = pd.concat(samples, ignore_index=True)
    review = review[["canonical_skill", "category", "description_group_id", "match_alias", "evidence"]]
    review = review.sort_values(["canonical_skill", "description_group_id"]).reset_index(drop=True)
    review["is_real_technical_use"] = ""  # fill in: yes / no
    review["notes"] = ""

    review.to_csv(OUT_PATH, index=False)

    print(f"Wrote {len(review)} rows across {review.canonical_skill.nunique()} candidate terms to {OUT_PATH}")
    print(review.groupby("canonical_skill").size().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
