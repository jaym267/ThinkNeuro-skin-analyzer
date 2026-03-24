import os
import base64
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

st.set_page_config(
    page_title="SkinScan AI",
    page_icon="🔬",
    layout="centered"
)

st.markdown("""
    <style>
    .main-header {
        font-size: 3.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #6C63FF, #48C9B0, #76D7C4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .result-box {
        background: transparent;
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
    }
    .stButton > button {
        background: linear-gradient(90deg, #6C63FF, #48C9B0);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 10px 30px;
        font-size: 1rem;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #48C9B0, #76D7C4);
        transform: scale(1.02);
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-header" style="font-size:3.5rem; text-decoration:none;">🔬 Skin Infection Analyzer AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Upload a photo of your skin and get an instant AI-powered analysis</p>', unsafe_allow_html=True)

st.warning("""
⚠️ MEDICAL DISCLAIMER: This website is for informational purposes only 
and does NOT provide medical diagnoses. Always consult a licensed 
dermatologist or healthcare professional for any skin concerns.
""")

st.markdown("---")

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    uploaded_file = st.file_uploader(
        "📸 Drop your skin image here",
        type=["jpg", "jpeg", "png", "webp"]
    )

if uploaded_file is not None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(uploaded_file, caption="Your uploaded image", use_column_width=True)

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        analyze_button = st.button("🔍 Analyze Image", type="primary")

    if analyze_button:
        with st.spinner("🔬 Analyzing your image... please wait"):

            image_bytes = uploaded_file.read()
            image_data = base64.b64encode(image_bytes).decode("utf-8")
            media_type = uploaded_file.type

            try:
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": """You are a medical image analysis assistant 
                                    specializing in dermatology and parasitology.
                                    Analyze the uploaded skin image and provide:

                                    1. DESCRIPTION: What you visually observe on the skin
                                    2. POSSIBLE CONDITIONS: Potential skin or parasitic 
                                       infections matching the symptoms, with likelihood 
                                       (high / medium / low)
                                    3. RISK FACTORS: Severity indicators and warning signs
                                    4. RECOMMENDED ACTION: Whether the person should seek 
                                       urgent care, routine care, or monitor at home

                                    End every response with:
                                    ⚠️ This is NOT a medical diagnosis. Please consult a 
                                    licensed dermatologist or healthcare professional."""
                                }
                            ]
                        }
                    ],
                    max_tokens=1024
                )

                result = response.choices[0].message.content

                st.markdown("---")
                st.subheader("📋 Analysis Results")
                st.markdown(f'<div class="result-box">{result}</div>', unsafe_allow_html=True)

                st.session_state["last_result"] = result

                st.markdown("---")
                if "urgent" in result.lower():
                    st.error("🚨 Urgent Care Recommended — Please see a doctor immediately")
                elif "routine" in result.lower():
                    st.warning("⚠️ Routine Care Suggested — Book an appointment soon")
                else:
                    st.success("✅ Monitor at Home — Keep an eye on it and see a doctor if it worsens")

                st.download_button(
                    label="📥 Download Results",
                    data=result,
                    file_name="skin_analysis_results.txt",
                    mime="text/plain"
                )

            except Exception as e:
                st.error("Something went wrong with the analysis. Please try again with a clearer image.")

if "last_result" in st.session_state:
    st.markdown("---")
    st.subheader("💬 Have a follow-up question?")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    user_question = st.text_input("Ask anything about the results...")

    if st.button("📨 Send Question") and user_question:
        st.session_state["messages"].append({
            "role": "user",
            "content": user_question
        })

        followup = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful medical assistant. Answer questions about skin conditions based on the previous analysis. Always recommend consulting a doctor."
                },
                {
                    "role": "assistant",
                    "content": st.session_state["last_result"]
                }
            ] + st.session_state["messages"],
            max_tokens=512
        )

        reply = followup.choices[0].message.content
        st.session_state["messages"].append({
            "role": "assistant",
            "content": reply
        })

        st.markdown(f'<div class="result-box">{reply}</div>', unsafe_allow_html=True)

    if st.button("🔄 Analyze Another Image"):
        for key in ["last_result", "messages"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

st.markdown("---")
st.markdown('<p style="text-align:center; color:#999; font-size:0.8rem;">SkinScan AI — For informational purposes only. Not a substitute for professional medical advice.</p>', unsafe_allow_html=True)
