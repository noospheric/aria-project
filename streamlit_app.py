import re
import streamlit as st
import openai
from github import Github
from urllib.parse import urlparse

def extract_metadata(github_url: str) -> dict:
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


def extract_file_citation_blurbs(message):
    """
    Given a single assistant Message, return a list of
    {snippet, file_id, raw_marker} dicts for each FileCitationAnnotation.
    """
    if not message.content:
        return []

    block      = message.content[0]
    text_obj   = block.text
    full_value = text_obj.value
    blurbs     = []

    for ann in text_obj.annotations:
        if ann.type == "file_citation":
            snippet = full_value[ann.start_index:ann.end_index]
            blurbs.append({
                "snippet":    snippet,
                "file_id":    ann.file_citation.file_id,
                "raw_marker": ann.text
            })
    return blurbs



# --- Streamlit UI ---
st.title("Akifa.ai")
st.subheader("EU AI Act Risk Analyzer")
github_url = st.text_input("Enter the GitHub repository URL:")

#system_message = {
#    "role": "system",
#    "content": "You are a compliance expert on the EU AI Act. Classify systems into the correct risk category: Unacceptable, High, Limited or Minimal. Provide a concise justification in bullet points."
#}

if github_url:
    st.info("🔁 Fetching metadata…")
    metadata = extract_metadata(github_url)
else:
    st.stop()

# Build LLM prompt
summary =  f"""
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
{metadata['license']}

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
"""
    
#print(summary)
openai.api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI()
    
# ———————————————————————————————
# 4️⃣ Create a Thread for this user interaction
# ———————————————————————————————
thread = client.beta.threads.create()
thread_id = thread.id

# 5️⃣ Add the user’s “message” containing your summary
client.beta.threads.messages.create(
    thread_id=thread_id,
    role="user",
    content=(
        "Here’s the project summary for EU AI Act classification:\n\n"
        f"{summary}"
    )
)

# … your Streamlit UI up through running the assistant …
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread_id,
    assistant_id="asst_DnkOcoj4OjCx5tu94QUp6X2L",
)

# Once it’s done, grab the assistant message:
if run.status != "completed":
    st.error(f"Run status: {run.status}")
    st.stop()

# 2️⃣ Grab the run ID into local
run_id    = run.id    # <-- this must exist on the run object

# 3️⃣ List all steps for that run
steps_page = client.beta.threads.runs.steps.list(
    thread_id=thread_id,
    run_id=run_id,
)
# 2️⃣ Filter down to only the tool_calls steps:
tool_steps = [
    s for s in steps_page.data
    if getattr(s, "type", None) == "tool_calls"
]

# 3️⃣ Find the step that actually ran file_search:
file_search_step = next(
    s for s in tool_steps
    if any(hasattr(tc, "file_search") for tc in s.step_details.tool_calls)
)

# 5️⃣ Retrieve that single step *with* chunk contents
step_detail = client.beta.threads.runs.steps.retrieve(
    thread_id=thread_id,
    run_id=run_id,
    step_id=file_search_step.id,
    include=["step_details.tool_calls[*].file_search.results[*].content"],
)

# 6️⃣ Pull out the raw file_search results
file_search_results = []
for tc in step_detail.step_details.tool_calls:
    if hasattr(tc, "file_search"):
        file_search_results = tc.file_search.results
        break

# 7️⃣ Now get the assistant’s message and its annotations
page          = client.beta.threads.messages.list(thread_id=thread_id)
assistant_msg = next(m for m in page.data if m.role == "assistant")
text_obj      = assistant_msg.content[0].text

# 8️⃣ Map each annotation to its chunk
blurbs = []
for ann in text_obj.annotations:
    if ann.type != "file_citation":
        continue
    m = re.match(r"【\d+:(\d+)†source】", ann.text)
    if not m:
        continue
    idx = int(m.group(1))
    if idx < len(file_search_results):
        blurbs.append({
            "marker": ann.text,
            "chunk":  file_search_results[idx].content[0].text,
            "score":  file_search_results[idx].score,
        })

# 9️⃣ Display
st.markdown("### AI Risk Assessment")
st.write(text_obj.value)

st.markdown("### References")
shown_markers = set()
for b in blurbs:
    if b['marker'] not in shown_markers:
        st.write(f"**{b['marker']}**")
        st.write(b["chunk"])
        st.write("---")
        shown_markers.add(b['marker'])