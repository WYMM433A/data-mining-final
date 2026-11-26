"""Extract the curated 234-skill shortlist from job descriptions (Step 5.8 v2).

Unlike the old `06_extract_skills.py` (which matched against the superseded
`resources/skill_dictionary.csv`), this script matches against the cleaned,
curated shortlist built in `outputs/09_job_skill_matrix/skill_shortlist_final.csv`,
using the alias variants recorded in `skill_extraction/Normalization & Alias
Mapping.csv`, plus a small set of manual alias/context overrides for the merges
and ambiguous terms decided during the shortlist review.

Two output views are produced, per the project plan's Step 5.4 design:
- description-group level (main view, one row per unique description)
- listing level (check view, expanded to every individual posting)
"""

import re
from pathlib import Path

import pandas as pd

SHORTLIST_PATH = Path("outputs/09_job_skill_matrix/skill_shortlist_final.csv")
MAPPING_PATH = Path("skill_extraction/Normalization & Alias Mapping.csv")
JOBS_DESC_PATH = Path("outputs/04_text_cleaning_and_groups/jobs_desc.csv")
JOBS_LISTING_PATH = Path("outputs/04_text_cleaning_and_groups/jobs_listing.csv")
OUT_DIR = Path("outputs/06_skill_extraction_v2")

USABLE_ACTIONS = {"Retained", "Normalized / reclassified", "Alias merged", "Confirmed"}
BOUNDARY_LEFT = r"(?<![A-Za-z0-9+#])"
BOUNDARY_RIGHT = r"(?![A-Za-z0-9+#])"
CUE_WINDOW = 100

# Extra alias text for canonicals that absorbed a merge/compound during shortlist curation.
# The Normalization & Alias Mapping sheet does not know about these manual decisions.
MANUAL_ALIASES = {
    "AWS": ["AWS", "Amazon Web Services (AWS)", "Amazon Web Services", "GovCloud", "AWS GovCloud"],
    "PostgreSQL": ["PostgreSQL", "Postgres"],
    ".NET": [".NET", ".NET Core"],
    "HTML": ["HTML", "HTML5"],
    "firewalls": ["firewalls", "firewall"],
    "CloudFormation": ["CloudFormation", "AWS CloudFormation"],
    "Databricks": ["Databricks", "Azure Databricks"],
    "VMware": ["VMware", "VMware vSphere"],
    "VPC": ["VPC", "VPCs"],
    "Agentic AI": ["Agentic AI", "agentic AI"],
    "JavaScript": ["JavaScript", "JavaScript/TypeScript"],
    "TypeScript": ["TypeScript", "JavaScript/TypeScript"],
    "Artificial Intelligence (AI)": ["AI", "Artificial Intelligence", "AI/ML"],
    "Machine Learning": ["Machine Learning", "ML", "AI/ML"],
    "GitLab": ["GitLab", "GitLab CI/CD"],
    "CI/CD": ["CI/CD", "GitLab CI/CD", "CI-CD"],
    "ETL/ELT": ["ETL", "ETL/ELT", "ELT"],
    "Agile": ["Agile", "Agile/Scrum"],
    "Scrum": ["Scrum", "Agile/Scrum"],
    "Power BI": ["PowerBI", "Power BI", "Microsoft Power BI"],
    "VPNs": ["VPNs", "VPN"],
    "VLANs": ["VLANs", "VLAN"],
    "runbooks": ["runbooks", "runbook"],
    "playbooks": ["playbooks", "playbook"],
    "embeddings": ["embeddings", "embedding"],
    "IaC": ["IaC", "Infrastructure as Code"],
    "REST API": ["REST API", "REST APIs", "RESTful API", "RESTful APIs"],
    "Agentic AI": ["Agentic AI", "agentic AI", "agentic"],
    "IAM": ["IAM", "Identity Management"],
    "Incident Response": ["Incident Response", "Incident Management"],
}

# Validation (Step 5.9) found these real gaps: a negative-cue check for AI's "hiring/interview
# AI-disclosure" boilerplate false positives, and an "agentic" bare-word needs a nearby cue since
# it is also used as a plain adjective unrelated to AI (e.g. "agentic auth").
def _ai_disclosure_check(text, match):
    window = text[max(0, match.start() - 120):match.end() + 120]
    boilerplate = re.search(
        r"disclosure|during\b.{0,30}\binterviews?|hiring process|application process|"
        r"recruiting process|screen candidates|applicant tracking|job application|"
        r"a note on ai|within the work environment|"
        r"generate (?:your |their )?(?:application|resume|cover letter)",
        window, re.I)
    # Company/product branding: "<Name> AI is the leading/a venture-backed/transforming..."
    company_descriptor = re.search(
        r"\bAI\b\s+is\s+(?:a|the|an)\s+\w*\s*(?:leading|venture-backed|first|transforming|"
        r"next generation|autonomy platform|operating system)",
        window, re.I)
    return not bool(boilerplate or company_descriptor)


NEGATIVE_CHECKS = {
    "Artificial Intelligence (AI)": _ai_disclosure_check,
}

# The 5 ambiguous terms with proven context regex, reused verbatim from the old
# 06_extract_skills.py (pattern, validity-check function operating on surrounding text).
def _r_rule(text, match):
    after = text[match.end():match.end() + 40]
    before = text[max(0, match.start() - 40):match.start()]
    valid_after = re.match(r"\s*(?:,|/|\)|and\b|or\b|programming\b|language\b|studio\b|shiny\b)", after, re.I)
    valid_before = re.search(r"\b(?:Python|SAS|SQL|Stata|SPSS)\s*(?:,|/|and\b|or\b)\s*$", before, re.I)
    return bool(valid_after or valid_before)


def _c_rule(text, match):
    after = text[match.end():match.end() + 20]
    return bool(re.match(r"\s*(?:/C\+\+|,|and\s+C\+\+|programming\b)", after, re.I))


REUSED_RULES = {
    "R": {"pattern": re.compile(r"(?<![A-Za-z0-9])R(?![A-Za-z0-9])"), "check": _r_rule},
    "C": {"pattern": re.compile(r"(?<![A-Za-z0-9])C(?![A-Za-z0-9+#])"), "check": _c_rule},
    "Swift": {"pattern": re.compile(r"\bSwift\b"), "cues": ["iOS", "Xcode", "Objective-C", "SwiftUI"]},
    "Spark": {"pattern": re.compile(r"\b(?:Apache\s+Spark|PySpark|Spark\s+SQL|Spark)\b"),
              "cues": ["Hadoop", "Scala", "Databricks"]},
    "Excel": {"pattern": re.compile(r"\b(?:Microsoft Excel|MS Excel|Excel)\b(?!\s+(?:in|at|as|under)\b)")},
    "Golang": {"pattern": re.compile(r"\bGolang\b|(?<![A-Za-z0-9])Go(?=\s*(?:,|\)|programming\b))")},
}

# New context-cue rules for the 24 additional ambiguous terms flagged during curation.
# A match only counts if at least one cue word/phrase appears within CUE_WINDOW characters.
CONTEXT_CUES = {
    "Lambda": ["AWS", "serverless", "function", "event-driven", "trigger"],
    "Ruby": ["Rails", "gem", "programming", "RSpec", "Sinatra"],
    "Chef": ["Puppet", "Ansible", "cookbook", "configuration management", "infrastructure automation", "recipe"],
    "Puppet": ["Chef", "Ansible", "configuration management", "infrastructure automation", "manifest"],
    "Cursor": ["AI", "IDE", "code editor", "coding assistant", "copilot"],
    "Claude": ["Anthropic", "AI", "LLM", "chatbot", "model", "assistant"],
    "Apex": ["Salesforce", "trigger", "SOQL", "Visualforce", "class"],
    "Oracle": ["database", "SQL", "PL/SQL", "RDBMS", "DBA", "Oracle Database", "tablespace"],
    "Windows": ["Server", "OS", "operating system", "Active Directory", "desktop"],
    "Cucumber": ["BDD", "Gherkin", "Selenium", "feature file", "automation", "testing"],
    "Transformers": ["Hugging Face", "NLP", "BERT", "model", "PyTorch", "attention", "architecture"],
    "Maven": ["Apache Maven", "build", "pom.xml", "Gradle", "Java", "dependency"],
    "Gemini": ["Google", "AI", "LLM", "chatbot", "model"],
    "Pinecone": ["vector", "database", "embeddings", "AI", "RAG", "index"],
    "Groovy": ["Jenkins", "Gradle", "scripting", "JVM", "pipeline"],
    "Flask": ["Python", "API", "web framework", "Django", "route", "Werkzeug"],
    "Toad": ["Oracle", "database", "SQL", "Quest"],
    "SAS": ["statistical", "analytics", "programming", "data", "SAS Institute", "macro"],
    "Codex": ["OpenAI", "AI", "code generation", "coding assistant", "Copilot"],
    "Snowflake": ["data warehouse", "cloud", "SQL", "ETL", "Snowpipe", "data platform"],
    "Confluence": ["Atlassian", "Jira", "wiki", "documentation"],
    "Helm": ["Kubernetes", "chart", "k8s", "deploy"],
    "MCP": ["Model Context Protocol", "AI", "LLM", "agent", "server", "Claude"],
    "RAG": ["retrieval", "LLM", "AI", "vector", "embeddings", "generation", "augmented"],
    "Agentic AI": ["AI", "agent", "tool", "autonomous", "LLM", "automation"],
}


# Compound slash/multi-term strings found in the raw candidates (e.g. "AWS/GCP", "Docker/Kubernetes")
# were left unresolved in "Needs Review". Each constituent canonical below now also matches the
# compound phrase, so a posting mentioning the compound credits every skill named in it.
EXTRA_ALIASES = {
    "AWS": ["AWS/GCP", "AWS/Azure/GCP"],
    "GCP": ["AWS/GCP", "AWS/Azure/GCP"],
    "Azure": ["AWS/Azure/GCP"],
    "Docker": ["Docker/Kubernetes", "Docker Kubernetes"],
    "Kubernetes": ["Docker/Kubernetes", "Docker Kubernetes", "EKS/Kubernetes", "Kubernetes/EKS",
                   "Kubernetes/OpenShift"],
    "EKS": ["EKS/Kubernetes", "Kubernetes/EKS"],
    "OpenShift": ["Kubernetes/OpenShift"],
    "Prometheus": ["Prometheus/Grafana"],
    "Grafana": ["Prometheus/Grafana"],
    "Jira": ["JIRA/Confluence"],
    "Confluence": ["JIRA/Confluence"],
    "React": ["React/TypeScript"],
    "TypeScript": ["React/TypeScript"],
    "Kotlin": ["Kotlin/Java"],
    "Java": ["Kotlin/Java"],
    "Ansible": ["Ansible Terraform"],
    "Terraform": ["Ansible Terraform", "Terraform/CloudFormation"],
    "AWS CloudFormation": ["Terraform/CloudFormation"],
    "lakehouse": ["Lakehouse/Warehouse"],
    "Data Warehousing": ["Lakehouse/Warehouse"],
}


def build_alias_lookup(shortlist: pd.DataFrame, mapping: pd.DataFrame) -> dict[str, list[str]]:
    usable = mapping[mapping.action.isin(USABLE_ACTIONS)]
    grouped = usable.groupby("canonical_skill")["original_term"].apply(list).to_dict()
    aliases = {}
    for canonical in shortlist.canonical_skill:
        if canonical in MANUAL_ALIASES:
            aliases[canonical] = list(MANUAL_ALIASES[canonical])
        else:
            aliases[canonical] = list(dict.fromkeys(grouped.get(canonical, []) + [canonical]))
        if canonical in EXTRA_ALIASES:
            aliases[canonical] = list(dict.fromkeys(aliases[canonical] + EXTRA_ALIASES[canonical]))
    return aliases


def compile_patterns(shortlist: pd.DataFrame, aliases: dict[str, list[str]]) -> list[dict]:
    compiled = []
    for row in shortlist.to_dict("records"):
        name = row["canonical_skill"]
        if name in REUSED_RULES:
            rule = REUSED_RULES[name]
            compiled.append({**row, "pattern": rule["pattern"], "rule_type": "reused",
                              "check": rule.get("check"), "cues": rule.get("cues")})
        elif name in CONTEXT_CUES:
            alternatives = [BOUNDARY_LEFT + re.escape(a) + BOUNDARY_RIGHT for a in aliases[name]]
            pattern = re.compile("(?:" + "|".join(alternatives) + ")")
            compiled.append({**row, "pattern": pattern, "rule_type": "context_cue",
                              "check": None, "cues": CONTEXT_CUES[name]})
        else:
            alternatives = [BOUNDARY_LEFT + re.escape(a) + BOUNDARY_RIGHT for a in aliases[name]]
            pattern = re.compile("(?:" + "|".join(alternatives) + ")", re.I)
            compiled.append({**row, "pattern": pattern, "rule_type": "plain",
                              "check": NEGATIVE_CHECKS.get(name), "cues": None})
    return compiled


# "Azure DevOps" is a specific product (CI/CD + project tooling), not a reference to the Azure
# cloud platform or the general DevOps practice. Validation found both being over-credited whenever
# only "Azure DevOps" appeared. Mask that phrase out before matching these two canonicals alone.
SUPPRESS_WHEN_PART_OF = {
    "Azure": re.compile(r"\bAzure\s+DevOps\b", re.I),
    "DevOps": re.compile(r"\bAzure\s+DevOps\b", re.I),
    "Spring": re.compile(r"\bSpring\s+Boot\b", re.I),
    "Artificial Intelligence (AI)": re.compile(r"\bVertex\s+AI\b", re.I),
}


def first_valid_match(text: str, skill: dict):
    if skill["canonical_skill"] in SUPPRESS_WHEN_PART_OF:
        text = SUPPRESS_WHEN_PART_OF[skill["canonical_skill"]].sub(lambda m: " " * len(m.group(0)), text)
    for match in skill["pattern"].finditer(text):
        if skill["check"] is not None:
            if not skill["check"](text, match):
                continue
        elif skill["cues"]:
            window = text[max(0, match.start() - CUE_WINDOW):match.end() + CUE_WINDOW]
            if not any(re.search(re.escape(cue), window, re.I) for cue in skill["cues"]):
                continue
        return match.start(), match.end(), match.group(0)
    return None


def main() -> None:
    shortlist = pd.read_csv(SHORTLIST_PATH)
    mapping = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig")
    jobs_desc = pd.read_csv(JOBS_DESC_PATH, encoding="utf-8-sig", low_memory=False)
    jobs_listing = pd.read_csv(JOBS_LISTING_PATH, encoding="utf-8-sig", low_memory=False)

    aliases = build_alias_lookup(shortlist, mapping)
    skills = compile_patterns(shortlist, aliases)
    print(f"Compiled {len(skills)} skill patterns "
          f"({sum(s['rule_type']=='reused' for s in skills)} reused-rule, "
          f"{sum(s['rule_type']=='context_cue' for s in skills)} context-cue, "
          f"{sum(s['rule_type']=='plain' for s in skills)} plain).")

    records = []
    n_desc = len(jobs_desc)
    for i, job in enumerate(jobs_desc.to_dict("records")):
        text = str(job["description_clean"])
        for skill in skills:
            found = first_valid_match(text, skill)
            if found is None:
                continue
            start, end, alias = found
            evidence = text[max(0, start - 60):min(len(text), end + 60)].replace("\n", " ").strip()
            records.append({
                "description_group_id": job["description_group_id"],
                "canonical_skill": skill["canonical_skill"],
                "category": skill["category"],
                "mining_status": skill["mining_status"],
                "family_adjacent": skill["family_adjacent"],
                "match_alias": alias,
                "evidence": evidence,
            })
        if (i + 1) % 1000 == 0:
            print(f"  scanned {i + 1}/{n_desc} descriptions...")

    job_skill_groups = pd.DataFrame(records)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    job_skill_groups.to_csv(OUT_DIR / "job_skill_groups.csv", index=False)

    listing_links = jobs_listing[["id", "description_group_id"]].rename(columns={"id": "job_id"})
    job_skill_listing = listing_links.merge(job_skill_groups, on="description_group_id", how="inner")
    job_skill_listing.to_csv(OUT_DIR / "job_skill_listing.csv", index=False)

    n_descriptions = len(jobs_desc)
    n_listings = len(jobs_listing)
    summary = (job_skill_groups.groupby(["canonical_skill", "category", "mining_status", "family_adjacent"])
               .description_group_id.nunique().reset_index(name="n_descriptions"))
    listing_counts = job_skill_listing.groupby("canonical_skill").job_id.nunique()
    summary["n_listings"] = summary.canonical_skill.map(listing_counts).fillna(0).astype(int)
    summary["share_of_descriptions"] = (summary.n_descriptions / n_descriptions).round(4)
    summary = summary.sort_values("n_descriptions", ascending=False)
    summary.to_csv(OUT_DIR / "skills_summary.csv", index=False)

    print(f"\nDescriptions scanned: {n_descriptions}; listings expanded to: {n_listings}")
    print(f"Group-level skill matches: {len(job_skill_groups)}; listing-level: {len(job_skill_listing)}")
    print(f"Descriptions with 0 skills found: "
          f"{n_descriptions - job_skill_groups.description_group_id.nunique()}")
    print("\nTop 20 skills by description count:")
    print(summary.head(20)[["canonical_skill", "category", "n_descriptions", "n_listings"]].to_string(index=False))


if __name__ == "__main__":
    main()
