"""Export a small job metadata lookup table (Step 5.10b, companion to the matrix).

The job-skill matrix views carry `job_id`, `description_group_id`, and `job_family`
but no human-readable title/company/location, since the full listing table
(`jobs_listing.csv`) is too large to ship alongside the matrix. This script pulls
just the lightweight identifying columns so analysts can label representative
postings, pick cross-title pairs, or name clusters without needing the big file.
"""

from pathlib import Path

import pandas as pd

JOBS_LISTING = Path("outputs/04_text_cleaning_and_groups/jobs_listing.csv")
OUT_PATH = Path("outputs/09_job_skill_matrix/job_metadata.csv")

COLUMNS = {
    "id": "job_id",
    "title": "title",
    "companyName": "company",
    "location": "location",
    "job_family": "job_family",
    "description_group_id": "description_group_id",
}


def main() -> None:
    jobs = pd.read_csv(JOBS_LISTING, usecols=list(COLUMNS), low_memory=False)
    jobs = jobs.rename(columns=COLUMNS)[list(COLUMNS.values())]
    jobs.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(jobs)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
