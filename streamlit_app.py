import re
import streamlit as st
import openai
from github import Github
from urllib.parse import urlparse
import pandas as pd

# --- App Config ---
st.set_page_config(
    page_title="Akifa.ai: EU AI Act Risk Analyzer",
    layout="wide",
    initial_sidebar_state="expanded",
)

official_legislation_url = "https://eur-lex.europa.eu/eli/reg/2024/1689"
# --- Branding & Logo ---
with st.sidebar:
    #st.image("https://your-corporate-logo-url.com/logo.png", width=150)
    st.markdown("### EU AI Act Risk Analyzer")
    st.markdown("**Version:** [OJ_L_202401689](%s)" % official_legislation_url)

# --- Header & Metrics ---
st.title("🔍 Akifa.ai Enterprise")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Repos Scanned", 7)
col2.metric("Data Sources Found", 11)
col3.metric("Identified Issues", 10)
col4.metric("Compliance Score", "85%", delta="+5%")

st.markdown("---")

# --- Input URL ---
github_url = st.text_input("Enter the GitHub repository URL:", placeholder="https://github.com/owner/repo")
if not github_url:
    st.info("🔁 Waiting for repository URL input...")
    st.stop()

# --- Fetch & Extract Metadata ---
with st.spinner("Scanning repository and extracting metadata..."):
    def extract_metadata(github_url: str) -> dict:
        token = st.secrets.get("GITHUB_TOKEN")
        gh = Github(token) if token else Github()
        path = urlparse(github_url).path.lstrip("/")
        owner, name = path.split("/")[:2]
        repo = gh.get_repo(f"{owner}/{name}")

        try:
            readme = repo.get_readme().decoded_content.decode()
        except:
            readme = ""
        try:
            req = repo.get_contents("requirements.txt")
            reqs = req.decoded_content.decode().splitlines()
        except:
            reqs = []

        languages    = repo.get_languages()
        topics       = repo.get_topics()
        license_id   = repo.get_license().license.spdx_id if repo.get_license() else "NONE"
        stars        = repo.stargazers_count
        forks        = repo.forks_count
        issues       = repo.open_issues_count
        last_push    = repo.pushed_at.isoformat()
        size_kb      = repo.size
        try:
            repo.get_contents(".github/workflows")
            has_ci = True
        except:
            has_ci = False
        contribs     = repo.get_contributors().totalCount

        blob = (readme + "\n" + "\n".join(reqs)).lower()
        tags = [kw for kw in ["finance","health","education","surveillance"] if kw in blob]

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
            "domain": tags[0] if tags else "General",
            "biometric_data": "biometric" in blob,
            "human_in_loop": "human-in-the-loop" in blob
        }

    metadata = extract_metadata(github_url)

# --- Display Core Summary ---
st.header("📊 Repository Analysis Summary")
with st.expander("Show Detailed Metadata", expanded=False):
    st.json(metadata)

# --- Charts & Graphs (Native) ---
st.subheader("Language Distribution (bytes %)")
lang_df = pd.DataFrame.from_dict(metadata['languages'], orient='index', columns=['bytes'])
lang_df['pct'] = lang_df['bytes'] / lang_df['bytes'].sum() * 100
st.bar_chart(lang_df['pct'])

# --- Domain & Topics Overview ---
st.subheader("Domain & Repository Topics")
# Single domain tag metric
st.metric("Domain Tag", metadata['domain'])
# GitHub topics list
if metadata['topics']:
    st.write("**Topics:** " + ", ".join(metadata['topics']))
else:
    st.info("No GitHub topics identified.")

# --- Compliance Stats (Native) ---
st.subheader("🔒 EU AI Act Compliance Metrics")
# Compliance-focused checks (drop CI, focus on biometric & oversight)
c1, c2 = st.columns(2)
c1.metric("Biometric Data Used", "Yes" if metadata['biometric_data'] else "No")
c2.metric("Human Oversight", "Yes" if metadata['human_in_loop'] else "No")

# Risk factor summary
total_factors = 2  # biometric_data, oversight
factors_present = sum([metadata['biometric_data'], not metadata['human_in_loop']])
st.metric("Risk Factors Present", f"{factors_present}/{total_factors}")

# Act-specific guidance
if metadata['biometric_data']:
    st.info("⚠️ Biometric processing is listed as a high-risk use under Annex II of the EU AI Act.")
if metadata['biometric_data'] and not metadata['human_in_loop']:
    st.warning("❗ High-risk features detected without explicit human oversight — Article 14 requires adequate human-in-the-loop measures.")

# Additional repository health stats
st.subheader("📈 Repository Health Metrics")

h1, h2, h3, h4 = st.columns(4)
h1.metric("Stars", metadata['stars'])
h2.metric("Forks", metadata['forks'])
h3.metric("Open Issues", metadata['open_issues'])
h4.metric("Contributors", metadata['contributors'])

# --- LLM-powered Classification ---
st.subheader("💡 EU AI Act Risk Classification & Justification")
summary = (
    f"Summary (first 5000 chars): {metadata['readme_summary']}\n"
    f"Tags: {', '.join(metadata['tags']) or 'None'}\n"
    f"Domain: {metadata['domain']}\n"
    f"Requirements: {', '.join(metadata['requirements']) or 'None'}\n"
    f"Languages: {', '.join(f'{lang} ({pct:.0f}%)' for lang, pct in metadata['languages'].items())}\n"
    f"License: {metadata['license']}\n"
    f"Stats: Stars={metadata['stars']}, Forks={metadata['forks']}, Issues={metadata['open_issues']}, CI={'Yes' if metadata['has_ci'] else 'No'}\n"
    f"Biometric Data: {'Yes' if metadata['biometric_data'] else 'No'}\n"
    f"Human-in-the-loop: {'Yes' if metadata['human_in_loop'] else 'No'}"
)

openai.api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI()
thread = client.beta.threads.create()
thread_id = thread.id
client.beta.threads.messages.create(
    thread_id=thread_id,
    role="user",
    content="Here’s the project summary for EU AI Act classification:\n\n" + summary
)
run = client.beta.threads.runs.create_and_poll(thread_id=thread_id, assistant_id="asst_DnkOcoj4OjCx5tu94QUp6X2L")
if run.status != "completed":
    st.error(f"Run status: {run.status}")
    st.stop()

steps_page = client.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run.id)
tool_steps = [s for s in steps_page.data if getattr(s, 'type', None) == 'tool_calls']
file_search_step = next(s for s in tool_steps if any(hasattr(tc, 'file_search') for tc in s.step_details.tool_calls))
step_detail = client.beta.threads.runs.steps.retrieve(
    thread_id=thread_id, run_id=run.id, step_id=file_search_step.id,
    include=['step_details.tool_calls[*].file_search.results[*].content']
)

st.markdown("---")
st.markdown("### Risk Assessment & References")
page = client.beta.threads.messages.list(thread_id=thread_id)
assistant_msg = next(m for m in page.data if m.role == 'assistant')
st.write(assistant_msg.content[0].text.value)
shown = set()
for ann in assistant_msg.content[0].text.annotations:
    if ann.type == 'file_citation':
        idx = int(re.match(r"【\d+:(\d+)†source】", ann.text).group(1))
        chunk = step_detail.step_details.tool_calls[0].file_search.results[idx].content[0].text
        if ann.text not in shown:
            st.markdown(f"**{ann.text}**")
            st.write(chunk)
            st.markdown('---')
            shown.add(ann.text)
