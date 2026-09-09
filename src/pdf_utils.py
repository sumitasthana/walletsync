"""PDF download and text extraction utilities."""

import re
from io import BytesIO
from typing import Optional

import fitz  # PyMuPDF
import requests


def download_and_extract_pdf_text(url: str) -> Optional[str]:
    """
    Download PDF from URL and extract all text.
    
    Args:
        url: The PDF URL to download
        
    Returns:
        Extracted text from PDF, or None if failed
    """
    try:
        # Download PDF with standard User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Read PDF from bytes
        pdf_stream = BytesIO(response.content)
        
        # Extract text using PyMuPDF
        pdf_document = fitz.open(stream=pdf_stream, filetype="pdf")
        
        all_text = []
        page_count = pdf_document.page_count
        
        for page_num in range(page_count):
            page = pdf_document[page_num]
            text = page.get_text()
            all_text.append(text)
        
        # Combine all pages before closing
        full_text = "\n".join(all_text)
        
        # Close document after extraction
        pdf_document.close()
        
        # Clean text - remove excessive whitespace
        # Replace multiple newlines with double newline
        cleaned_text = re.sub(r'\n{3,}', '\n\n', full_text)
        # Replace multiple spaces with single space
        cleaned_text = re.sub(r' {2,}', ' ', cleaned_text)
        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in cleaned_text.split('\n')]
        cleaned_text = '\n'.join(lines)
        
        return cleaned_text
        
    except Exception as e:
        raise Exception(f"Failed to download/extract PDF from {url}: {e}")
