"""
LinkedIn Opportunity Scanner
Runs daily via GitHub Actions at 6am PT.
Scans Gmail for LinkedIn job emails, extracts opportunities,
deduplicates, and writes to data/opportunities.json.
"""

import json
import os
import re
import base64
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ── Decode email body ─────────────────────────────────────────────────────────
def decode_part(data):
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def extract_body(payload, prefer="text/plain"):
    if not payload:
        return ""
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")
    if mime == prefer and body_data:
        return decode_part(body_data)
    if mime in ("text/plain", "text/html") and body_data:
        return decode_part(body_data)
    for part in payload.get("parts", []):
        result = extract_body(part, prefer)
        if result:
            return result
    return ""


# ── Extract LinkedIn job info ─────────────────────────────────────────────────
LINKEDIN_JOB_PATTERNS = [
    r"https?://(?:www\.)?linkedin\.com/jobs/view/\S+",
    r"https?://(?:www\.)?linkedin\.com/comm/jobs/view/\S+",
]

TITLE_PATTERNS = [
    # "Role at Company" style subjects
    r"^(?:New job|Job alert|Recommended).*?:\s*(.+?)\s+at\s+(.+?)(?:\s*[-|].*)?$",
    r"^(.+?)\s+at\s+(.+?)(?:\s*[-|].*)?$",
]

SUBJECT_KEYWORDS = [
    "job", "position", "role", "opportunity", "opening", "hiring",
    "recruiter", "career", "work", "engineer", "developer", "manager",
    "analyst", "designer", "scientist", "intern", "associate"
]

LINKEDIN_SENDER_DOMAINS = ["linkedin.com", "e.linkedin.com", "em.linkedin.com"]


def is_linkedin_job_email(headers, body):
    sender = headers.get("from", "").lower()
    subject = headers.get("subject", "").lower()
    is_linkedin = any(d in sender for d in LINKEDIN_SENDER_DOMAINS)
    if not is_linkedin:
        return False
    has_job_keyword = any(k in subject for k in SUBJECT_KEYWORDS)
    has_job_link = any(re.search(p, body) for p in LINKEDIN_JOB_PATTERNS)
    return has_job_keyword or has_job_link


def extract_job_link(body):
    for pattern in LINKEDIN_JOB_PATTERNS:
        matches = re.findall(pattern, body)
        if matches:
            # Clean trailing punctuation/quotes
            link = re.split(r'["\'\s<>]', matches[0])[0]
            return link
    return ""


def parse_title_company(subject, body):
    """Try to extract job title and company from subject line."""
    subject = re.sub(r"(?i)^re:\s*", "", subject).strip()
    subject = re.sub(r"(?i)^fwd?:\s*", "", subject).strip()

    # LinkedIn digest format: "search keyword": Company - Job Title [and more]
    # e.g. "vice president gtm": XBOW - Head of GTM Strategy and more
    linkedin_digest = re.match(
        r'^["\u201c\u201e][^"\u201c\u201d\u201e]+["\u201d\u201e]\s*:\s*'
        r'([A-Z][^\n\-]{2,50}?)\s*[-\u2013]\s*(.{5,}?)(?:\s+and\s+more.*)?$',
        subject,
        re.IGNORECASE,
    )
    if linkedin_digest:
        company = linkedin_digest.group(1).strip().rstrip(",. ")
        title = linkedin_digest.group(2).strip()
        return title[:80], company

    for pattern in TITLE_PATTERNS:
        m = re.match(pattern, subject, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(2).strip()

    # Try to pull company from body
    company_match = re.search(r"at\s+([A-Z][A-Za-z\s&.,'-]{2,40}?)(?:\s+is|\.|,|\n)", body)
    company = company_match.group(1).strip() if company_match else "Unknown"
    return subject[:80], company


def dedup_id(title, company, link):
    """Generate a stable ID for deduplication."""
    key = f"{title.lower().strip()}|{company.lower().strip()}|{link}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] LinkedIn scanner starting...")

    service = get_gmail_service()

    # Search Gmail for LinkedIn job emails (last 2 days to catch anything missed)
    query = "from:(linkedin.com OR e.linkedin.com) newer_than:2d"
    results = service.users().messages().list(
        userId="me", q=query, maxResults=50
    ).execute()

    messages = results.get("messages", [])
    print(f"Found {len(messages)} LinkedIn emails to check")

    # Load existing opportunities
    opp_file = "data/opportunities.json"
    try:
        with open(opp_file, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"opportunities": [], "applied": [], "lastScan": None}

    existing_ids = {opp.get("id") for opp in data.get("opportunities", [])}
    existing_ids |= {opp.get("id") for opp in data.get("applied", [])}

    new_opps = []

    for msg_ref in messages:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = {
                h["name"].lower(): h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }

            body = extract_body(msg.get("payload", {}))

            if not is_linkedin_job_email(headers, body):
                continue

            subject = headers.get("subject", "(no subject)")
            date_str = headers.get("date", "")
            title, company = parse_title_company(subject, body)
            link = extract_job_link(body)

            # Parse date
            try:
                dt = parsedate_to_datetime(date_str).isoformat()
            except Exception:
                dt = datetime.now(timezone.utc).isoformat()

            opp_id = dedup_id(title, company, link)

            if opp_id in existing_ids:
                print(f"  Skipping duplicate: {title[:50]}")
                continue

            opp = {
                "id": opp_id,
                "title": title,
                "company": company,
                "link": link,
                "date": dt,
                "status": "consider",
                "source": "gmail_scan",
                "added": datetime.now(timezone.utc).isoformat(),
            }

            new_opps.append(opp)
            existing_ids.add(opp_id)
            print(f"  + New opportunity: {title[:50]} @ {company[:30]}")

        except Exception as e:
            print(f"  Error processing message {msg_ref['id']}: {e}")

    # Prepend new opportunities (newest first)
    if new_opps:
        data["opportunities"] = new_opps + data.get("opportunities", [])
        print(f"Added {len(new_opps)} new opportunities")
    else:
        print("No new opportunities found")

    data["lastScan"] = datetime.now(timezone.utc).isoformat()

    with open(opp_file, "w") as f:
        json.dump(data, f, indent=2)

    print("Done. opportunities.json updated.")


if __name__ == "__main__":
    main()
