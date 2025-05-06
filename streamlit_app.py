import streamlit as st
import openai
import requests

st.set_page_config(page_title="EU AI Risk Classifier", layout="centered")

st.title("🔍 EU AI Act Risk Classifier")

github_url = st.text_input("Enter the GitHub repository URL:", "")

if github_url:
    st.write("🔁 Analyzing repo... (simulated)")

    # Mock extracted metadata – in a real version, you'd pull this from the repo
    metadata = {
        "readme_summary": "Predicts student performance using test data.",
        "tags": ["education", "scoring", "analytics"],
        "domain": "education",
        "biometric_data": False,
        "human_in_loop": True
    }

    # Generate prompt
    prompt = f"""Classify this AI system by EU AI Act risk level:
    
    Summary: {metadata['readme_summary']}
    Tags: {', '.join(metadata['tags'])}
    Domain: {metadata['domain']}
    Biometric data used: {metadata['biometric_data']}
    Human-in-the-loop: {metadata['human_in_loop']}

    Return the risk level and a short explanation.
    """

    openai.api_key = st.secrets["OPENAI_API_KEY"]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a compliance expert in the EU AI Act."},
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content
        st.markdown("### 🧠 AI Risk Assessment")
        st.success(reply)

    except Exception as e:
        st.error(f"Error: {e}")
