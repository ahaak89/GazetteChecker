import os
import json
import time
import re
import smtplib
import shutil
import keyring
import sys
from email.message import EmailMessage
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import logging
from requests.exceptions import RequestException
import fitz  # PyMuPDF

# =======================
# CONFIG — EDIT THESE
# =======================
GAZETTE_LIST_URLS = [
    "https://www.gazette.vic.gov.au/gazette_bin/recent_gazettes.cfm"
]

SEARCH_TERMS = [
    "acquisition",
    "declaration that a stratum",
    "designation of the project area",
    "designation of a project area",
    "notice of intention to acquire",
    "major transport projects facilitation act",
]

DOWNLOAD_DIR = "downloads"
STATE_FILE = "seen_urls.json"
LOG_FILE = "gazette_checker.log"
KEYRING_SERVICE_NAME = 'gazette-checker-service'

# Email (set SEND_EMAIL=False to test without sending)
SEND_EMAIL = True
SMTP_HOST = "mail.smtp2go.com"
SMTP_PORT = 80  # Port 80 as requested
SMTP_USER = os.getenv("GAZETTE_SMTP_USER", "huntvic.com.au")
EMAIL_FROM = "mortgages@huntvic.com.au"
EMAIL_TO = ["CompulsoryAcquisitionsGroup@huntvic.com.au", "ahaak@huntvic.com.au"]
EMAIL_SUBJECT_PREFIX = "Gazette Alert"

# Politeness / resilience
REQUEST_TIMEOUT = 20
RETRY_COUNT = 3
RETRY_SLEEP = 2
USER_AGENT = "Hunt&Hunt Gazette Watcher (contact: it@example.com)"

# =======================
# Setup Logging
# =======================
# This setup logs to both a file and the console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

# =======================
# File & Directory Management
# =======================
def clear_download_directory(dir_path):
    """Checks for and deletes the specified directory and its contents."""
    if os.path.exists(dir_path):
        try:
            shutil.rmtree(dir_path)
            logging.info(f"Successfully cleared old downloads directory: {dir_path}")
        except OSError as e:
            logging.error(f"Error clearing directory {dir_path}: {e.strerror}")

# =======================
# HTTP helper
# =======================
def http_get(url):
    last_err = None
    headers = {"User-Agent": USER_AGENT}
    for i in range(RETRY_COUNT):
        try:
            logging.info(f"Attempting to fetch {url} (attempt {i+1}/{RETRY_COUNT})...")
            r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            logging.info("Fetch successful.")
            return r
        except RequestException as e:
            last_err = e
            logging.warning(f"Error fetching {url}: {e}")
            if i < RETRY_COUNT - 1:
                logging.info(f"Retrying in {RETRY_SLEEP} seconds...")
                time.sleep(RETRY_SLEEP)
    raise last_err

# =======================
# Discovery
# =======================
def get_pdf_links():
    links = set()
    for list_url in GAZETTE_LIST_URLS:
        try:
            res = http_get(list_url)
            soup = BeautifulSoup(res.text, "html.parser")
        except RequestException as e:
            logging.error(f"Failed to fetch or parse {list_url}: {e}")
            continue

        for a in soup.select("a[href]"):
            href = a["href"].strip()
            full_url = urljoin(list_url, href)
            if full_url.lower().endswith(".pdf"):
                links.add(full_url)

    return sorted(links)

# =======================
# State & IO
# =======================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logging.error(f"Failed to load state file {STATE_FILE}: {e}. Starting with empty state.")
    return {"seen": []}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        logging.info(f"State saved to {STATE_FILE}.")
    except IOError as e:
        logging.error(f"Failed to save state file {STATE_FILE}: {e}")

def download_pdf(url, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    filename = os.path.basename(url.split("?")[0]) or (f"gazette_{int(time.time())}.pdf")
    path = os.path.join(dest_dir, filename)
    if os.path.exists(path):
        logging.info(f"File already exists: {path}. Skipping download.")
        return path
        
    logging.info(f"Downloading {url} to {path}...")
    r = http_get(url)
    with open(path, "wb") as f:
        f.write(r.content)
    logging.info("Download complete.")
    return path

# =======================
# PDF text extraction & Matching
# =======================
def extract_text_with_pymupdf(pdf_path):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    pages = []
    try:
        with fitz.open(pdf_path) as doc:
            for p in doc:
                pages.append(p.get_text("text") or "")
        logging.info(f"Extracted text from {len(pages)} pages of {pdf_path}.")
    except Exception as e:
        raise RuntimeError(f"Error extracting text from {pdf_path}: {e}")
    return pages

def find_matches(text_pages, terms):
    results = []
    compiled = [(t, re.compile(re.escape(t), re.IGNORECASE)) for t in terms]
    for i, page_text in enumerate(text_pages, start=1):
        for term, rx in compiled:
            for m in rx.finditer(page_text):
                start = max(m.start() - 120, 0)
                end = min(m.end() + 120, len(page_text))
                snippet = page_text[start:end].replace("\n", " ").strip()
                results.append({"term": term, "page": i, "snippet": snippet})
    return results

# =======================
# Email
# =======================
def build_email(subject_prefix, findings):
    if not findings:
        return None, None, None

    dt = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    subject = f"{subject_prefix}: {len(findings)} gazette(s) matched — {dt}"
    
    plain_lines = ["Automated alert: new Victoria Government Gazette issue(s) matched your search terms.\n"]
    html_lines = [
        '<html><body style="font-family: sans-serif;">'
        '<p>Automated alert: new Victoria Government Gazette issue(s) matched your search terms.</p>'
        '<ul style="list-style-type: none; padding-left: 0;">'
    ]

    for f in findings:
        plain_lines.append(f"\n• {f['filename']} ({f['url']})")
        html_lines.append(f'<li style="margin-bottom: 1em; border: 1px solid #ccc; padding: 10px; border-radius: 5px;"><p style="margin: 0;"><strong>File:</strong> {f["filename"]}<br><small><a href="{f["url"]}">{f["url"]}</a></small></p><hr style="border: 0; border-top: 1px solid #eee;">')
        
        for m in f["matches"]:
            plain_lines.append(f"  - Found Term: {m['term']} (Page: {m['page']})")
            plain_lines.append(f"    Context: …{m['snippet']}…")
            html_lines.append(f'<div style="margin-top: 10px; padding-left: 15px;"><p style="margin: 0;">Found Term: <strong>{m["term"]}</strong> (Page: {m["page"]})</p><p style="margin: 5px 0 0 0; font-size: 0.9em; color: #555; border-left: 3px solid #ddd; padding-left: 10px;"><em>…{m["snippet"]}…</em></p></div>')
        
        html_lines.append("</li>")

    html_lines.append("</ul></body></html>")
    
    html_body = "\n".join(html_lines)
    plain_body = "\n".join(plain_lines)
    
    return subject, html_body, plain_body

def send_email(subject, html_body, plain_body):
    if not SEND_EMAIL:
        logging.info("Email sending is disabled.")
        return True

    try:
        # Get the password from the system's credential store
        SMTP_PASS = keyring.get_password(KEYRING_SERVICE_NAME, 'smtp_password')
        
        if not SMTP_USER or not SMTP_PASS:
            logging.error("SMTP_USER is not set or password not found in keyring for service '%s'.", KEYRING_SERVICE_NAME)
            return False
            
    except Exception as e:
        logging.error(f"Failed to get password from keyring. Is keyring installed and the password set? Error: {e}")
        return False

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(EMAIL_TO)
    msg["Subject"] = subject
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype='html')

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        logging.info("Email sent successfully.")
        return True
    except smtplib.SMTPException as e:
        logging.error(f"Failed to send email: {e}")
        return False
        
# =======================
# Main
# =======================
def main():
    clear_download_directory(DOWNLOAD_DIR)
    
    logging.info("Starting gazette watch process.")
    state = load_state()
    seen = set(state.get("seen", []))
    
    try:
        pdf_urls = get_pdf_links()
    except RequestException as e:
        logging.critical(f"Initial discovery failed. Aborting script. Error: {e}")
        return

    new_urls = sorted([u for u in pdf_urls if u not in seen])
    if not new_urls:
        logging.info("No new gazette PDFs found. Exiting.")
        return

    logging.info(f"Found {len(new_urls)} new gazette PDFs to process.")
    findings = []
    
    for url in new_urls:
        logging.info(f"Processing new PDF: {url}")
        try:
            path = download_pdf(url, DOWNLOAD_DIR)
            pages = extract_text_with_pymupdf(path)
            matches = find_matches(pages, SEARCH_TERMS)
            if matches:
                logging.info(f"Found {len(matches)} matches in {os.path.basename(path)}.")
                findings.append({
                    "url": url,
                    "filename": os.path.basename(path),
                    "matches": matches
                })
            seen.add(url)
        except Exception:
            logging.exception(f"An error occurred while processing {url}. Marking as seen to prevent retries.")
            seen.add(url)

    state["seen"] = sorted(list(seen))
    save_state(state)

    if findings:
        subject, html_body, plain_body = build_email(EMAIL_SUBJECT_PREFIX, findings)
        if send_email(subject, html_body, plain_body):
            logging.info(f"Successfully sent alert for {len(findings)} gazette(s).")
        else:
            logging.error(f"Alert for {len(findings)} gazette(s) was generated but FAILED to send.")
    else:
        logging.info("New gazettes found, but no term matches. No email sent.")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Script failed due to a critical unhandled exception")
        sys.exit(1)