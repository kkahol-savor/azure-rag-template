"""
Harvard Pilgrim PDF Scraper

This script scrapes the Harvard Pilgrim website to extract and download PDFs
for Schedules of Benefits (SOB) and Summaries of Benefits and Coverage (SBC).
It identifies forms on the webpage that generate PDFs dynamically and downloads
them to a specified folder.

Usage:
    Run the script directly to download all available PDFs to the "harvard_pdfs" folder.

Dependencies:
    - requests
    - BeautifulSoup (from bs4)
    - os
    - urllib.parse

Author: [Your Name]
Date: April 15, 2025
"""

import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urlencode

BASE_URL = "https://www.harvardpilgrim.org/enroll/schedules-of-benefits-and-sbcs-maine-2025/"
PDF_DOWNLOAD_BASE = BASE_URL  # Form action is same as base URL

def extract_and_download_pdfs():
    """
    Extracts PDF links from the Harvard Pilgrim webpage and downloads them.

    This function parses the webpage to find forms that generate PDFs dynamically.
    It determines the type of document (SOB or SBC), constructs the download URL,
    and saves the PDFs to the "harvard_pdfs" folder.
    """
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(BASE_URL, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    os.makedirs("harvard_pdfs", exist_ok=True)

    for form in soup.find_all("form"):
        inputs = {inp["name"]: inp.get("value", "") for inp in form.find_all("input")}
        if not inputs:
            continue

        # Decide if it's SOB or SBC
        if "hphc_child_fetch_document_sob" in inputs:
            doc_type = "SOB"
        elif "hphc_child_fetch_document_sbc" in inputs:
            doc_type = "SBC"
        else:
            continue

        record_id = inputs.get("hphc_child_fetch_document_sob_record_id") or \
                    inputs.get("hphc_child_fetch_document_sbc_record_id")

        file_name = f"{doc_type}_{record_id}.pdf"
        pdf_url = f"{PDF_DOWNLOAD_BASE}?{urlencode(inputs)}"

        try:
            pdf_response = requests.get(pdf_url)
            if pdf_response.ok and pdf_response.headers["Content-Type"] == "application/pdf":
                with open(os.path.join("data", file_name), "wb") as f:
                    f.write(pdf_response.content)
                print(f"Downloaded: {file_name}")
            else:
                print(f"Skipped (non-PDF): {file_name}")
        except Exception as e:
            print(f"Error downloading {file_name}: {e}")

if __name__ == "__main__":
    extract_and_download_pdfs()