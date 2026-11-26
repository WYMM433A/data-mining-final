"""Create a blinded 120-description annotation sample and a separate key (Step 5.9 v2).

Rebuilt against the current Step 4 tables and the new 230-skill extraction
(`outputs/06_skill_extraction_v2/job_skill_listing.csv`, mining_status == "include"),
replacing the stale sample that was built from the deleted old Step 6 output.
"""

import pandas as pd

from common import write_csv
from config import RANDOM_SEED, STEP_04_DIR, STEP_07_DIR, TITLE_FAMILIES

JOB_SKILL_LISTING = "outputs/06_skill_extraction_v2/job_skill_listing.csv"


def main() -> None:
    jobs = pd.read_csv(STEP_04_DIR / "jobs_desc.csv", encoding="utf-8-sig", low_memory=False)
    pairs = pd.read_csv(JOB_SKILL_LISTING, encoding="utf-8-sig")
    pairs = pairs[pairs.mining_status == "include"]  # the final 230-skill mining set only

    families = [family for family in TITLE_FAMILIES if family != "other"]
    eligible = jobs.loc[pd.to_numeric(jobs.n_words, errors="coerce").ge(80) & jobs.job_family.isin(families)].copy()

    selected = []
    family_shortfalls = []
    for family in families:
        pool = eligible.loc[eligible.job_family.eq(family)]
        take = min(15, len(pool))
        if take < 15:
            family_shortfalls.append({"job_family": family, "available": len(pool), "target": 15, "shortfall": 15 - take})
        if take:
            selected.append(pool.sample(n=take, random_state=RANDOM_SEED))
    sample = pd.concat(selected, ignore_index=True) if selected else eligible.iloc[0:0].copy()
    if len(sample) < 120:
        remaining = eligible.loc[~eligible.id.isin(sample.id)]
        fill = remaining.sample(n=min(120 - len(sample), len(remaining)), random_state=RANDOM_SEED)
        sample = pd.concat([sample, fill], ignore_index=True)
    sample = sample.sample(frac=1, random_state=RANDOM_SEED).reset_index(drop=True)
    sample.insert(0, "val_id", [f"VAL{index:04d}" for index in range(1, len(sample) + 1)])

    annotation = sample[["val_id", "id", "job_family", "title", "description_clean"]].rename(columns={"id": "job_id"})
    annotation["annotator1_skills"] = ""
    annotation["annotator2_skills"] = ""
    annotation["gold_skills"] = ""
    annotation["notes"] = ""

    hidden = pairs.merge(sample[["id", "val_id"]], left_on="job_id", right_on="id", how="inner")
    extracted = (hidden.groupby(["val_id", "job_id"]).canonical_skill
                 .apply(lambda values: ";".join(sorted(set(values)))).reset_index(name="extracted_skills"))
    if extracted.empty:
        extracted = pd.DataFrame(columns=["val_id", "job_id", "extracted_skills"])

    STEP_07_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(annotation, STEP_07_DIR / "validation_for_annotators.csv")
    write_csv(extracted, STEP_07_DIR / "validation_extracted.csv")
    write_csv(pd.DataFrame(family_shortfalls, columns=["job_family", "available", "target", "shortfall"]),
              STEP_07_DIR / "family_sample_shortfalls.csv")

    readme = """# Skill annotation instructions (v2 - rebuilt against the 230-skill mining dictionary)

Each annotator should work independently. Read the complete job description and list every
technical skill the posting asks for: tools, programming languages, platforms, frameworks, and
technical methods. Use canonical names from
`outputs/09_job_skill_matrix/skill_shortlist_final.csv` (mining_status = include) when possible.
Write unseen skills as `NEW:<name>`. Skip generic phrases and soft skills. Separate entries with
semicolons. Leave the notes field for ambiguity; do not view `validation_extracted.csv` before
finishing.

After both annotators finish, compare their lists and adjudicate every disagreement into
`gold_skills`. Enter `NONE` if adjudication concludes a description has no technical skills.
Preserve new skill names so the dictionary can be reviewed.
"""
    (STEP_07_DIR / "README_annotation.md").write_text(readme, encoding="utf-8")

    print(f"Annotation sample created: {len(annotation)} descriptions; target was 120.")
    if family_shortfalls:
        print("Family sample shortfalls:")
        print(pd.DataFrame(family_shortfalls).to_string(index=False))
    else:
        print("All 8 families reached their 15-posting target.")
    print("Extracted-skill key is stored separately; do not share it with annotators before annotation.")


if __name__ == "__main__":
    main()
