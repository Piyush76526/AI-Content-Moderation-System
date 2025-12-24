import streamlit as st
import io
import zipfile
import uuid
from PIL import Image
import boto3
from PyPDF2 import PdfReader

AWS_REGION = "us-east-1"
S3_BUCKET = "YOUR_BUCKET_NAME"
AWS_ACCOUNT_ID = ""

try:
    rekognition = boto3.client("rekognition", region_name=AWS_REGION)
    AWS_REKOG_AVAIL = True
except:
    AWS_REKOG_AVAIL = False

try:
    textract = boto3.client("textract", region_name=AWS_REGION)
    AWS_TEXTRACT_AVAIL = True
except:
    AWS_TEXTRACT_AVAIL = False

try:
    macie_client = boto3.client("macie2", region_name=AWS_REGION)
    sts = boto3.client("sts")
    AWS_ACCOUNT_ID = sts.get_caller_identity()["Account"]
    s3 = boto3.client("s3", region_name=AWS_REGION)
    AWS_MACIE_AVAIL = True
except:
    AWS_MACIE_AVAIL = False

harmful_words = ["fuck", "idiot", "bitch", "asshole", "hate", "kill"]
scam_keywords = ["otp", "lottery", "bank blocked", "click link", "hack", "fraud"]
fake_news = ["pm of india died", "prime minister died", "war started", "government collapsed"]

def analyze_text(t):
    low = t.lower()
    for w in harmful_words:
        if w in low:
            return "❌ Harmful Text", f"Detected: {w}"
    for w in scam_keywords:
        if w in low:
            return "🚨 Scam Message", f"Detected: {w}"
    for w in fake_news:
        if w in low:
            return "⚠️ Fake News Suspicion", "Unverified claim"
    return "✅ Safe Text", "-"

def scan_image(img_bytes):
    if not AWS_REKOG_AVAIL:
        return "❌ Rekognition OFF – AWS not configured", None
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data = buf.getvalue()
    res = rekognition.detect_moderation_labels(Image={"Bytes": data}, MinConfidence=70)
    labels = res.get("ModerationLabels", [])
    if labels:
        return "❌ Harmful IMAGE", labels
    return "✅ Safe IMAGE", None

def extract_ocr(img_bytes):
    if not AWS_TEXTRACT_AVAIL:
        return None
    res = textract.detect_document_text(Document={"Bytes": img_bytes})
    text = ""
    for b in res["Blocks"]:
        if b["BlockType"] == "LINE":
            text += b["Text"] + "\n"
    return text

def scan_pdf(data):
    try:
        reader = PdfReader(io.BytesIO(data))
        full_text = ""
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                full_text += txt + "\n"
        if full_text.strip():
            return analyze_text(full_text)
        if AWS_TEXTRACT_AVAIL:
            ocr_text = extract_ocr(data)
            if ocr_text:
                return analyze_text(ocr_text)
        return None, "⚪ PDF has no readable text"
    except:
        return None, "⚠️ Unable to read PDF"

def upload_s3(filename, data):
    key = f"uploads/{uuid.uuid4()}-{filename}"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    return key

def macie_scan():
    job = macie_client.create_classification_job(
        jobType="ONE_TIME",
        s3JobDefinition={"bucketDefinitions":[{"accountId": AWS_ACCOUNT_ID, "buckets":[S3_BUCKET]}]},
        name=f"macie-job-{uuid.uuid4()}"
    )
    return job["jobId"]

def macie_result():
    out = macie_client.list_findings()
    if not out.get("findingIds"):
        return None
    detailed = macie_client.get_findings(findingIds=out["findingIds"])
    return detailed

st.set_page_config(page_title="AI Scanner", layout="wide")
st.title("🛡️ Unified AI Content Moderation + AWS Scanner")

typed = st.text_area("✍️ Write text to analyze")
if typed.strip():
    r, reason = analyze_text(typed)
    (st.success if "Safe" in r else st.error)(r)
    st.info(reason)

st.markdown("---")
st.subheader("📂 Upload Any File")

file = st.file_uploader("Upload file")

def scan_zip(zfile):
    st.warning("ZIP Detected – scanning inside…")
    z = zipfile.ZipFile(zfile, "r")
    names = z.namelist()
    st.json(names)
    for n in names:
        st.write(f"Scanning → {n}")
        data = z.read(n)
        low = n.lower()
        if low.endswith((".jpg", ".jpeg", ".png", ".webp")):
            r, labels = scan_image(data)
            (st.success if "Safe" in r else st.error)(r)
            if labels: st.json(labels)
        elif low.endswith(".pdf"):
            r, reason = scan_pdf(data)
            if r:
                (st.success if "Safe" in r else st.error)(r)
                st.info(reason)
        elif low.endswith((".txt", ".py", ".js", ".html")):
            text = data.decode("utf-8", errors="ignore")
            r, reason = analyze_text(text)
            (st.success if "Safe" in r else st.error)(r)
            st.info(reason)
        else:
            st.info("⚪ Skip – unsupported format")
    st.success("ZIP Scan Completed")

if file:
    name = file.name.lower()
    data = file.read()

    if name.endswith(".zip"):
        scan_zip(file)
        st.stop()

    if name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        img = Image.open(io.BytesIO(data))
        st.image(img, caption="Uploaded Image")
        r, labels = scan_image(data)
        (st.success if "Safe" in r else st.error)(r)
        if labels: st.json(labels)
        ocr_text = extract_ocr(data)
        if ocr_text:
            r, reason = analyze_text(ocr_text)
            st.info("🧠 OCR Text Found")
            (st.success if "Safe" in r else st.error)(r)
            st.info(reason)
        st.stop()

    if name.endswith(".pdf"):
        r, reason = scan_pdf(data)
        if r:
            (st.success if "Safe" in r else st.error)(r)
            st.info(reason)
        else:
            st.warning(reason)
        st.stop()

    try:
        text = data.decode("utf-8", errors="ignore")
        r, reason = analyze_text(text)
        st.code(text)
        (st.success if "Safe" in r else st.error)(r)
        st.info(reason)
    except:
        st.warning("⚠️ Unsupported file type – cannot read")

    st.markdown("### 🔐 Scan Sensitive Information with AWS Macie")
    if AWS_MACIE_AVAIL:
        if st.button("Upload & Scan using Macie"):
            key = upload_s3(file.name, data)
            st.success(f"📤 Uploaded to S3 as → {key}")
            job = macie_scan()
            st.info(f"🧠 Macie Scan Started (Job ID: {job})")
            st.write("⏳ after 30–60s → click Get Result")
        if st.button("Get Macie Result"):
            res = macie_result()
            if not res:
                st.warning("⏳ No findings yet")
            else:
                st.success("🎯 AWS Macie Result")
                st.json(res)
    else:
        st.error("❌ Macie not enabled – enable in AWS Console")

st.markdown("---")
st.caption("AI Moderation → Text NLP + Rekognition + Textract OCR + AWS Macie")
