#!/usr/bin/env python3
"""
Sync script for GitHub Profile README (routparam12)
Fetches:
1. Latest Substack articles (cards with cover image, title, date & time posted in IST, domain)
2. Latest GitHub projects (cards with title, description, date & time posted in IST, language, stars)
"""

import os
import re
import html
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
import json

GITHUB_USERNAME = "routparam12"
SUBSTACK_FEED = "https://paramjeetrout.substack.com/feed"
SUBSTACK_DOMAIN = "paramjeetrout.substack.com"
README_PATH = "README.md"

PROJECTS_START = "<!-- PROJECTS:START -->"
PROJECTS_END = "<!-- PROJECTS:END -->"
SUBSTACK_START = "<!-- SUBSTACK:START -->"
SUBSTACK_END = "<!-- SUBSTACK:END -->"

# IST (Indian Standard Time): UTC+05:30
IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_SUBSTACK_IMG = "https://substackcdn.com/image/fetch/w_160,c_limit,f_auto,q_auto:good,fl_progressive:steep/https%3A%2F%2Fsubstack-post-media.s3.amazonaws.com%2Fpublic%2Fimages%2Fsubstack-icon.png"


def fetch_url(url: str, headers: dict = None) -> bytes:
    req_headers = {"User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) {GITHUB_USERNAME}-profile-sync"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read()


def format_iso_to_ist(iso_str: str) -> str:
    """Format ISO 8601 UTC timestamp to IST: 'Oct 02, 2026 · 11:15 PM IST'"""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%b %d, %Y · %I:%M %p IST")
    except Exception:
        return iso_str


def format_rfc822_to_ist(rfc_str: str) -> str:
    """Format RFC 822 timestamp (GMT/UTC) to IST: 'Oct 02, 2026 · 08:38 AM IST'"""
    try:
        dt = parsedate_to_datetime(rfc_str)
        dt_ist = dt.astimezone(IST)
        return dt_ist.strftime("%b %d, %Y · %I:%M %p IST")
    except Exception:
        return rfc_str


def get_latest_substack(limit: int = 3) -> str:
    print(f"Fetching Substack feed from {SUBSTACK_FEED}...")
    xml_data = fetch_url(SUBSTACK_FEED)
    root = ET.fromstring(xml_data)
    items = root.findall(".//item")[:limit]

    cards = []
    for item in items:
        title = html.escape(item.find("title").text or "").strip()
        link = (item.find("link").text or "").strip()
        pub_date = (item.find("pubDate").text or "").strip()
        formatted_ist = format_rfc822_to_ist(pub_date)

        raw_desc = item.find("description").text or ""
        clean_desc = re.sub(r"<[^<]+?>", "", raw_desc)
        snippet = " ".join(clean_desc.split())[:120]
        if len(clean_desc) > 120:
            snippet += "..."
        snippet = html.escape(snippet)

        enc = item.find("enclosure")
        img_url = enc.attrib.get("url") if enc is not None else DEFAULT_SUBSTACK_IMG

        card = f"""<table width="100%">
  <tr>
    <td width="160" align="center" valign="middle">
      <a href="{link}" target="_blank">
        <img src="{img_url}" width="160" style="border-radius: 8px; max-width: 100%; display: block;" alt="{title}" />
      </a>
    </td>
    <td valign="middle">
      <a href="{link}" target="_blank">
        <strong>{title}</strong>
      </a>
      <br/>
      <sub>{snippet}</sub>
      <br/><br/>
      <sub>📅 <b>Posted:</b> {formatted_ist} &nbsp;•&nbsp; 🌐 <a href="https://{SUBSTACK_DOMAIN}" target="_blank">{SUBSTACK_DOMAIN}</a></sub>
    </td>
  </tr>
</table>"""
        cards.append(card)

    cards_html = "\n".join(cards)
    footer = f"""\n> 💡 *I write about RAG systems, data architecture, and practical GenAI — follow on [Substack](https://{SUBSTACK_DOMAIN}) or [X](https://x.com/Paramjeet_r)*"""
    return f"{cards_html}\n{footer}"


def get_latest_projects(limit: int = 4) -> str:
    print(f"Fetching GitHub repositories for {GITHUB_USERNAME}...")
    headers = {}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/users/{GITHUB_USERNAME}/repos?per_page=100"
    raw_json = fetch_url(url, headers=headers)
    repos = json.loads(raw_json.decode("utf-8"))

    # Filter out forks, profile repo, and archived repos
    filtered = [
        r for r in repos
        if not r.get("fork") and r.get("name") != GITHUB_USERNAME and not r.get("archived")
    ]

    # Sort by created_at descending (newest posted project first)
    filtered.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    selected = filtered[:limit]

    cards = []
    for r in selected:
        name = html.escape(r.get("name") or "")
        url = r.get("html_url") or ""
        desc = (r.get("description") or "").strip()
        if not desc:
            desc = "Open-source project and implementation."
        desc = html.escape(desc)

        created_ist = format_iso_to_ist(r.get("created_at") or "")
        updated_ist = format_iso_to_ist(r.get("pushed_at") or r.get("updated_at") or "")
        lang = r.get("language") or "General"
        stars = r.get("stargazers_count", 0)
        stars_badge = f"&nbsp;•&nbsp; ⭐ {stars}" if stars > 0 else ""

        card = f"""<table width="100%">
  <tr>
    <td valign="top">
      <strong><a href="{url}" target="_blank">🚀 {name}</a></strong>
      <p>{desc}</p>
      <sub>📅 <b>Posted:</b> {created_ist} &nbsp;•&nbsp; 🔄 <b>Updated:</b> {updated_ist} &nbsp;•&nbsp; 💻 <code>{lang}</code>{stars_badge}</sub>
    </td>
  </tr>
</table>"""
        cards.append(card)

    return "\n".join(cards)


def replace_section(content: str, start_marker: str, end_marker: str, replacement: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_marker)})(.*?)({re.escape(end_marker)})",
        re.DOTALL
    )
    if not pattern.search(content):
        print(f"Warning: Marker pair {start_marker} ... {end_marker} not found.")
        return content
    return pattern.sub(rf"\1\n{replacement}\n\3", content)


def main():
    if not os.path.exists(README_PATH):
        raise FileNotFoundError(f"{README_PATH} not found in current directory.")

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme_content = f.read()

    # 1. Update Substack section
    try:
        substack_html = get_latest_substack(limit=3)
        readme_content = replace_section(
            readme_content, SUBSTACK_START, SUBSTACK_END, substack_html
        )
        print("Updated Substack section.")
    except Exception as e:
        print(f"Error fetching/updating Substack: {e}")

    # 2. Update Projects section
    try:
        projects_html = get_latest_projects(limit=4)
        readme_content = replace_section(
            readme_content, PROJECTS_START, PROJECTS_END, projects_html
        )
        print("Updated Projects section.")
    except Exception as e:
        print(f"Error fetching/updating Projects: {e}")

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print("Sync completed successfully.")


if __name__ == "__main__":
    main()
