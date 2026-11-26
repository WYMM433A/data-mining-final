# Skill annotation instructions (v2 - rebuilt against the 230-skill mining dictionary)

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
