import streamlit as st
import re
import io
from PIL import Image

USE_AWS_REKOGNITION = True
rekognition = None
AWS_AVAILABLE = False

if USE_AWS_REKOGNITION:
    try:
        import boto3
        rekognition = boto3.client("rekognition", region_name="us-east-1")
        AWS_AVAILABLE = True
    except Exception:
        AWS_AVAILABLE = False

def scan_image_aws(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    clean_bytes = buffer.getvalue()

    response = rekognition.detect_moderation_labels(
        Image={"Bytes": clean_bytes},
        MinConfidence=70
    )

    labels = response.get("ModerationLabels", [])
    if labels:
        return "❌ HARMFUL IMAGE CONTENT", labels
    return "✅ SAFE IMAGE CONTENT", None

harmful_words = ["fuck", "idiot", "bitch", "asshole", "hate", "kill"]
scam_keywords = ["otp", "lottery", "bank blocked", "click link", "hack", "fraud"]
fake_news_claims = [
    "pm of india died",
    "prime minister died",
    "government collapsed",
    "war started"
]


def analyze_text(text):
    t = text.lower()

    for w in harmful_words:
        if w in t:
            return "❌ HARMFUL TEXT", f"Abusive word detected: {w}"

    for w in scam_keywords:
        if w in t:
            return "🚨 SCAM / HACK ALERT", f"Suspicious keyword detected: {w}"

    for w in fake_news_claims:
        if w in t:
            return "⚠️ POSSIBLE FAKE NEWS", "High-risk unverified claim detected"

    return "✅ TEXT APPEARS SAFE", "No harmful patterns detected"

st.title("🛡️ AI Content Moderation System")

st.markdown("""
### 📝 Ways to Submit Content
1. **Type text manually** (messages, alerts, news)
2. **Upload text files (.txt)**
3. **Upload images** (unsafe content detection)
""")

st.subheader("✍️ Write Text Here")

typed_text = st.text_area(
    "Enter any message, alert, news, or content",
    height=160,
    placeholder="Example: Your bank account is blocked. Share OTP..."
)

if typed_text.strip():
    result, reason = analyze_text(typed_text)

    if "SAFE" in result:
        st.success(result)
    elif "FAKE" in result:
        st.warning(result)
    else:
        st.error(result)

    st.info(reason)

st.markdown("---")

st.subheader("📂 Upload File")

uploaded_file = st.file_uploader(
    "Upload a TXT file or Image",
    type=["txt", "jpg", "jpeg", "png", "webp"]
)

if uploaded_file:

    if uploaded_file.type == "text/plain":
        text = uploaded_file.read().decode("utf-8")
        st.subheader("📄 File Content")
        st.code(text)

        result, reason = analyze_text(text)

        if "SAFE" in result:
            st.success(result)
        elif "FAKE" in result:
            st.warning(result)
        else:
            st.error(result)

        st.info(reason)

    else:
        image_bytes = uploaded_file.read()
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, caption="Uploaded Image", use_column_width=True)

        if USE_AWS_REKOGNITION and AWS_AVAILABLE:
            result, labels = scan_image_aws(image_bytes)
            if "HARMFUL" in result:
                st.error(result)
                st.json(labels)
            else:
                st.success(result)
        else:
            st.warning("Image moderation will activate when AWS API is configured")

st.markdown("---")
st.caption("Text moderation: Rule-based NLP | Image moderation: AWS Rekognition (optional)")
