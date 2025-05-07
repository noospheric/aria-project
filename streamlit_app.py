import os
import streamlit as st
import openai
from github import Github
from urllib.parse import urlparse

def extract_metadata(github_url: str) -> dict:
    from urllib.parse import urlparse
    from github import Github
    import os

    token = st.secrets["GITHUB_TOKEN"]
    gh    = Github(token) if token else Github()
    path  = urlparse(github_url).path.lstrip("/")
    owner, name = path.split("/")[:2]
    repo  = gh.get_repo(f"{owner}/{name}")

    # Basic README + requirements (as before)…
    try:
        readme = repo.get_readme().decoded_content.decode()
    except:
        readme = ""
    try:
        req = repo.get_contents("requirements.txt")
        reqs = req.decoded_content.decode().splitlines()
    except:
        reqs = []

    # New fields:
    languages    = repo.get_languages()        # byte counts by language
    topics       = repo.get_topics()           # GitHub topics
    license_id   = (repo.get_license().license.spdx_id 
                    if repo.get_license() else "NONE")
    stars        = repo.stargazers_count
    forks        = repo.forks_count
    issues       = repo.open_issues_count
    last_push    = repo.pushed_at.isoformat()
    size_kb      = repo.size
    # CI check:
    try:
        repo.get_contents(".github/workflows")
        has_ci = True
    except:
        has_ci = False
    # Contributors (may be rate-limited on big repos):
    contribs = repo.get_contributors().totalCount

    # Heuristic tags/domain (as before)…
    blob = (readme + "\n" + "\n".join(reqs)).lower()
    tags = [kw for kw in ["finance","health","education","surveillance"]
            if kw in blob]

    return {
        "readme_summary": readme[:5000] + ("…" if len(readme)>5000 else ""),
        "tags": tags,
        "requirements": reqs,
        "languages": languages,
        "topics": topics,
        "license": license_id,
        "stars": stars,
        "forks": forks,
        "open_issues": issues,
        "last_push": last_push,
        "size_kb": size_kb,
        "has_ci": has_ci,
        "contributors": contribs,
        "domain": tags[0] if tags else "general",
        "biometric_data": "biometric" in blob,
        "human_in_loop": "human-in-the-loop" in blob
    }

# --- Streamlit UI ---
st.title("Akifa.ai")
st.subheader("EU AI Act Risk Analyzer")
github_url = st.text_input("Enter the GitHub repository URL:")

system_message = {
    "role": "system",
    "content": "You are a compliance expert on the EU AI Act. Classify systems into the correct risk category: Unacceptable, High, Limited or Minimal. Provide a concise justification in bullet points."
}

if github_url:
    st.info("🔁 Fetching metadata…")
    metadata = extract_metadata(github_url)

    # Build LLM prompt
    prompt =  f"""
Classify this AI system by EU AI Act risk level and give a short explanation.

Summary (first 5000 chars):
{metadata['readme_summary']}

Tags:
{', '.join(metadata['tags']) or 'None'}

Domain:
{metadata['domain']}

Requirements:
{', '.join(metadata['requirements']) or 'None'}

Languages (byte %):
{', '.join(f"{lang} ({pct:.0%})" for lang, pct in metadata['languages'].items())}

Topics:
{', '.join(metadata['topics']) or 'None'}

License:
{license}

Stats:
 • Stars: {metadata['stars']}
 • Forks: {metadata['forks']}
 • Open issues: {metadata['open_issues']}
 • Last push: {metadata['last_push']}
 • Size (KB): {metadata['size_kb']}
 • CI configured: {"Yes" if metadata['has_ci'] else "No"}
 • Contributors: {metadata['contributors']}

Biometric data used:
{"Yes" if metadata['biometric_data'] else "No"}

Human-in-the-loop:
{"Yes" if metadata['human_in_loop'] else "No"}

Based on all the above, what is the EU AI risk level and why?
Itemize your assesment.
"""
    
    user_message = {
    "role": "user",
    "content": prompt
    }

    print(prompt)
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=[system_message, user_message]
        )
        answer = resp.choices[0].message.content
        st.markdown("### 🧠 AI Risk Assessment")
        st.success(answer)

    except Exception as e:
        st.error(f"API Error: {e}")
