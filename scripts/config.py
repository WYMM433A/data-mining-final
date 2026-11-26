"""Shared paths and thresholds for the IT job-market KDD pipeline."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
PROFILE_DIR = OUTPUT_DIR / "00_source_profile"
STEP_01_DIR = OUTPUT_DIR / "01_collection_log"
STEP_02_DIR = OUTPUT_DIR / "02_quality_filters"
STEP_03_DIR = OUTPUT_DIR / "03_job_family"
STEP_04_DIR = OUTPUT_DIR / "04_text_cleaning_and_groups"
STEP_05_DIR = OUTPUT_DIR / "05_skill_candidates"
STEP_05_V2_DIR = OUTPUT_DIR / "05_skill_candidates_v2"
STEP_06_DIR = OUTPUT_DIR / "06_skill_extraction"
STEP_07_DIR = OUTPUT_DIR / "07_validation_sample"
STEP_08_DIR = OUTPUT_DIR / "08_validation_results"
STEP_09_DIR = OUTPUT_DIR / "09_job_skill_matrix"
STEP_10_DIR = OUTPUT_DIR / "10_descriptive_statistics"
STEP_11_DIR = OUTPUT_DIR / "11_association_rules"
STEP_12_DIR = OUTPUT_DIR / "12_similarity"
STEP_13_DIR = OUTPUT_DIR / "13_clustering"
STEP_14_DIR = OUTPUT_DIR / "14_titles_vs_clusters"
STEP_15_DIR = OUTPUT_DIR / "15_decision_tree"
STEP_16_DIR = OUTPUT_DIR / "16_dashboard"
RESOURCE_DIR = PROJECT_ROOT / "resources"

RANDOM_SEED = 42
MIN_DESCRIPTION_WORDS = 50
SHORT_DESCRIPTION_WORDS = 100
ENGLISH_MIN_TOKENS = 20
ENGLISH_MIN_STOPWORD_SHARE = 0.12
DATE_PROXY_DAYS = 31
NEAR_DUPLICATE_COSINE = 0.95
MIN_CANDIDATE_DOCUMENT_FREQUENCY = 5
MATRIX_MIN_SKILL_SHARE = 0.01
MATRIX_MAX_SKILL_SHARE = 0.60

PLANNED_KEYWORDS = [
    "Data Analyst", "Business Intelligence Analyst", "Business Intelligence Developer",
    "Reporting Analyst", "Analytics Engineer", "Data Scientist", "Machine Learning Engineer",
    "AI Engineer", "NLP Engineer", "Computer Vision Engineer", "Software Engineer",
    "Frontend Developer", "Backend Developer", "Full Stack Developer", "Mobile App Developer",
    "DevOps Engineer", "Cloud Engineer", "Site Reliability Engineer", "Platform Engineer",
    "Infrastructure Engineer", "Cybersecurity Analyst", "Security Engineer", "Network Engineer",
    "Information Security Analyst", "Data Engineer", "Database Administrator", "Database Developer",
    "Data Architect", "QA Engineer", "Automation Test Engineer", "Software Test Engineer",
    "ERP Consultant", "Salesforce Developer", "SAP Consultant",
]

ACCEPTED_VARIANTS = {
    "securityengineeer": ("Security Engineer", "Accepted typo variant; verify returned titles during review."),
    "salesforcedeveloper": ("Salesforce Developer", "Accepted spacing variant."),
    "analyticsengineers": ("Analytics Engineer", "Accepted plural variant."),
    "backenddeveloper": ("Backend Developer", "Accepted spacing variant."),
    "qualityassuranceengineer": ("QA Engineer", "Accepted expanded-name variant."),
    "qualityassuranceautomationengineer": (
        "Automation Test Engineer", "Accepted expanded-name variant."),
}

SEARCH_FAMILY_BY_STEM = {
    "ai_engineer": "AI & Machine Learning",
    "computer_vision_engineer": "AI & Machine Learning",
    "data_scientist": "AI & Machine Learning",
    "machine_learning_engineer": "AI & Machine Learning",
    "nlp_engineer": "AI & Machine Learning",
    "cloud_engineer": "Cloud, DevOps & Infrastructure",
    "devops_engineer": "Cloud, DevOps & Infrastructure",
    "infrastructure_engineer": "Cloud, DevOps & Infrastructure",
    "platform_engineer": "Cloud, DevOps & Infrastructure",
    "site_reliability_engineer": "Cloud, DevOps & Infrastructure",
    "sales_force_engineer": "Enterprise Software & IT Systems",
    "erp_consultant": "Enterprise Software & IT Systems",
    "sap_consultant": "Enterprise Software & IT Systems",
    "cybersecurity_analyst": "Cybersecurity & Networking",
    "information_security_analyst": "Cybersecurity & Networking",
    "network_engineer": "Cybersecurity & Networking",
    "security_engineer": "Cybersecurity & Networking",
    "data_architect": "Database & Data Infrastructure",
    "data_engineer": "Database & Data Infrastructure",
    "database_administrator": "Database & Data Infrastructure",
    "database_developer": "Database & Data Infrastructure",
    "mobile_app_developer": "Software Development & Engineering",
    "back_end_developer": "Software Development & Engineering",
    "frontend_developer": "Software Development & Engineering",
    "full_stack_developer": "Software Development & Engineering",
    "software_engineer": "Software Development & Engineering",
    "analytics_engineers": "Data & Business Intelligence",
    "business_intelligence_analyst": "Data & Business Intelligence",
    "business_intelligence_developer": "Data & Business Intelligence",
    "data_analyst": "Data & Business Intelligence",
    "reporting_analyst": "Data & Business Intelligence",
    "quality_assurance_automation_engineer": "QA & Software Testing",
    "quality_assurance_engineer": "QA & Software Testing",
    "software_test_engineer": "QA & Software Testing",
}

TITLE_FAMILIES = [
    "data_bi", "ai_ml", "software", "cloud_devops", "cyber_network",
    "database_data", "qa_testing", "enterprise_it", "other",
]
