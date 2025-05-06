import os
import streamlit as st
import openai
from github import Github
from urllib.parse import urlparse

def extract_metadata(github_url: str) -> dict:
    # --- set up client (token optional) ---
    token = os.getenv("GITHUB_TOKEN", "").strip()
    gh = Github(token) if token else Github()

    # --- parse owner/repo from URL ---
    path = urlparse(github_url).path.lstrip("/")
    owner, repo_name = path.split("/")[:2]
    repo = gh.get_repo(f"{owner}/{repo_name}")

    # --- fetch README ---
    try:
        readme = repo.get_readme().decoded_content.decode("utf-8")
    except Exception:
        readme = ""

    # --- fetch requirements.txt (if any) ---
    try:
        req = repo.get_contents("requirements.txt")
        req_txt = req.decoded_content.decode("utf-8")
        requirements = [line.strip() for line in req_txt.splitlines() if line and not line.startswith("#")]
    except Exception:
        requirements = []

    # --- simple keyword heuristics ---
    content_blob = (readme + "\n" + " ".join(requirements)).lower()
    tags = []
    for kw in ["credit", "finance", "education", "health", "surveillance", "biometric"]:
        if kw in content_blob:
            tags.append(kw)

    metadata = {
        "readme_summary": readme[:500] + ("…" if len(readme)>500 else ""),
        "tags": tags,
        "libraries": requirements,
        "biometric_data": "face" in content_blob or "biometric" in content_blob,
        "human_in_loop": "human-in-the-loop" in content_blob or "human in loop" in content_blob,
        "domain": tags[0] if tags else "general"
    }
    return metadata

# --- Streamlit UI ---
st.title("🔍 EU AI Act Risk Classifier")
github_url = st.text_input("Enter the GitHub repository URL:")

if github_url:
    st.info("🔁 Fetching metadata…")
    metadata = extract_metadata(github_url)

    # Build LLM prompt
    prompt = f"""
Classify this AI system by EU AI Act risk level:

Summary (first 500 chars): {metadata['readme_summary']}
Tags: {', '.join(metadata['tags']) or 'none'}
Domain: {metadata['domain']}
Libraries: {', '.join(metadata['libraries']) or 'none'}
Biometric data used: {metadata['biometric_data']}
Human-in-the-loop: {metadata['human_in_loop']}

Return the risk level and a short explanation.
"""
    print(prompt)
    openai.api_key = st.secrets["OPENAI_API_KEY"]
    try:
        resp = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a compliance expert in the EU AI Act."},
                {"role": "user",   "content": prompt}
            ]
        )
        answer = resp.choices[0].message.content
        st.markdown("### 🧠 AI Risk Assessment")
        st.success(answer)

    except Exception as e:
        st.error(f"API Error: {e}")
