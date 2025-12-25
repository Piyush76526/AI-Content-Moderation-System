import streamlit as st
import io
import zipfile
import uuid
import os
from PIL import Image
import pytesseract
import boto3

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_ACCOUNT_ID = ""

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

try:
    rekognition = boto3.client(
        "rekognition",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )
    AWS_REKOG_AVAIL = True
except:
    AWS_REKOG_AVAIL = False

try:
    macie_client = boto3.client(
        "macie2",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )
    sts = boto3.client(
        "sts",
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )
    AWS_ACCOUNT_ID = sts.get_caller_identity()["Account"]
    s3 = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_KEY,
        aws_secret_access_key=AWS_SECRET
    )
    AWS_MACIE_AVAIL = True
except:
    AWS_MACIE_AVAIL = False

harmful_words = ["fuck", "idiot", "bitch", "asshole", "hate", "kill"]
scam_keywords = ["otp", "lottery", "bank blocked", "click link", "hack", "fraud"]
fake_news = ["pm of india died", "prime minister died", "war started", "government collapsed"]

def analyze_text(t):
    low = t.lower()
    for w in harmful_words:
        if w in low: return "❌ Harmful Text", f"Detected: {w}"
    for w in scam_keywords:
        if w in low: return "🚨 Scam Message", f"Detected: {w}"
    for w in fake_news:
        if w in low: return "⚠️ Fake News Suspicion", "Unverified claim"
    return "✅ Safe Text", "-"

def extract_ocr(data):
    try:
        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img)
        return text.strip()
    except:
        return None

def scan_image(data):
    if not AWS_REKOG_AVAIL:
        return "❌ Rekognition not configured", None
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b = buf.getvalue()
    res = rekognition.detect_moderation_labels(Image={"Bytes": b}, MinConfidence=70)
    labels = res.get("ModerationLabels", [])
    if labels:
        return "❌ Harmful IMAGE", labels
    return "✅ Safe IMAGE", None

def scan_pdf(data):
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        full_text = ""
        for p in reader.pages:
            t = p.extract_text()
            if t: full_text += t + "\n"
        if full_text.strip(): return analyze_text(full_text)
        ocr_text = extract_ocr(data)
        if ocr_text: return analyze_text(ocr_text)
        return None, "⚪ PDF no readable text"
    except:
        return None, "⚠️ PDF read error"

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
    if not out.get("findingIds"): return None
    return macie_client.get_findings(findingIds=out["findingIds"])

st.set_page_config(page_title="AI Content Scanner", layout="wide")
st.title("🛡️ AI Content Moderation Scanner")

typed = st.text_area("✍️ Analyze Text")
if typed.strip():
    r, reason = analyze_text(typed)
    (st.success if "Safe" in r else st.error)(r)
    st.info(reason)

st.markdown("---")
st.subheader("📂 Upload File to Scan")

file = st.file_uploader("Upload", type=None)

def scan_zip(zfile):
    st.warning("ZIP found — scanning contents…")
    z = zipfile.ZipFile(zfile, "r")
    files = z.namelist()
    st.json(files)
    for n in files:
        d = z.read(n)
        n2 = n.lower()
        if n2.endswith((".jpg", ".jpeg", ".png", ".webp")):
            r, labels = scan_image(d)
            (st.success if "Safe" in r else st.error)(r)
            if labels: st.json(labels)
        elif n2.endswith(".pdf"):
            r, reason = scan_pdf(d)
            if r: (st.success if "Safe" in r else st.error)(r); st.info(reason)
        elif n2.endswith((".txt", ".py", ".js", ".html")):
            tx = d.decode("utf-8", errors="ignore")
            r, reason = analyze_text(tx)
            (st.success if "Safe" in r else st.error)(r)
            st.info(reason)
        else:
            st.write("⏸ Skipped:", n)
    st.success("ZIP Scan Completed")

if file:
    name = file.name.lower()
    data = file.read()

    if name.endswith(".zip"):
        scan_zip(file)
        st.stop()

    if name.endswith((".jpg",".jpeg",".png",".webp")):
        img = Image.open(io.BytesIO(data))
        st.image(img, caption="Uploaded Image")
        r, labels = scan_image(data)
        (st.success if "Safe" in r else st.error)(r)
        if labels: st.json(labels)
        tx = extract_ocr(data)
        if tx:
            st.info("🧠 OCR Text:")
            st.code(tx)
            r, reason = analyze_text(tx)
            (st.success if "Safe" in r else st.error)(r)
            st.info(reason)
        st.stop()

    if name.endswith(".pdf"):
        r, reason = scan_pdf(data)
        if r: (st.success if "Safe" in r else st.error)(r); st.info(reason)
        else: st.warning(reason)
        st.stop()

    try:
        text = data.decode("utf-8", errors="ignore")
        r, reason = analyze_text(text)
        st.code(text)
        (st.success if "Safe" in r else st.error)(r)
        st.info(reason)
    except:
        st.warning("⚠️ File unreadable")

    st.markdown("### 🔐 Sensitive Data Scan — AWS Macie")
    if AWS_MACIE_AVAIL:
        if st.button("Upload & Scan"):
            key = upload_s3(file.name, data)
            st.success(f"Uploaded → {key}")
            j = macie_scan()
            st.info(f"Scan Running → Job {j}")
        if st.button("Get Result"):
            res = macie_result()
            if not res: st.warning("⏳ No findings")
            else: st.success("Result"); st.json(res)
    else:
        st.error("Macie disabled — enable in AWS Console")

st.caption("Powered by: pytesseract OCR + AWS Rekognition + Macie")
