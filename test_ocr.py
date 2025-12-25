from PIL import Image
import pytesseract
import os

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

file = "test.png"

if not os.path.exists(file):
    print("❌ File not found:", file)
    exit()

img = Image.open(file)
text = pytesseract.image_to_string(img)
print("🧠 OCR OUTPUT:")
print(text)
