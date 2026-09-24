import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from flask import current_app

def configure_tesseract():
    """
    Configure pytesseract path dynamically from config.
    """
    tesseract_path = current_app.config.get('TESSERACT_PATH', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        current_app.logger.warning(f"Tesseract path not found at: {tesseract_path}. OCR may fail.")

def extract_text_from_file(file_path):
    """
    Extracts text from a PDF or image file.
    First tries direct PDF text extraction. If empty/scanned, or if it is an image,
    it falls back to Tesseract OCR.
    """
    configure_tesseract()
    
    _, ext = os.path.splitext(file_path.lower())
    extracted_text = ""
    
    try:
        if ext == '.pdf':
            # Try PyMuPDF text extraction first
            doc = fitz.open(file_path)
            text_list = []
            for page in doc:
                text_list.append(page.get_text())
            doc.close()
            
            extracted_text = "\n".join(text_list).strip()
            
            # If digital extraction returned minimal text, it might be scanned. Use OCR.
            if len(extracted_text) < 50:
                current_app.logger.info("PDF appears to be scanned. Running OCR on pages...")
                ocr_texts = []
                doc = fitz.open(file_path)
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    # Render page to image pixmap
                    pix = page.get_pixmap(dpi=150)
                    img_data = pix.tobytes("png")
                    
                    # Read image with PIL and run Tesseract
                    from io import BytesIO
                    img = Image.open(BytesIO(img_data))
                    page_text = pytesseract.image_to_string(img)
                    ocr_texts.append(page_text)
                doc.close()
                extracted_text = "\n".join(ocr_texts).strip()
                
        elif ext in ['.png', '.jpg', '.jpeg']:
            # Run Tesseract on image file
            img = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(img).strip()
            
    except Exception as e:
        current_app.logger.error(f"Error in OCR text extraction: {str(e)}")
        # Return empty string instead of crashing, enabling safe fallback
        extracted_text = ""
        
    return extracted_text
