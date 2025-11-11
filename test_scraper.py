"""
Complete Test Script with Robust PDF Extraction
This file is designed to test the PDF text extraction logic on a single file,
using PyMuPDF with a fallback to pdfminer.six.
"""

import os
import asyncio
import logging
from io import BytesIO
import aiohttp
import fitz # PyMuPDF
from pdfminer.high_level import extract_text_to_fp
import chardet
from typing import Optional

# Set up logging for a clean test output
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class EletoDocumentScraperTest:
    """A simplified class to test PDF extraction logic."""
    
    def __init__(self):
        self.session = None

    async def init_session(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={
                    'User-Agent': 'Mozilla/5.0'
                }
            )

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def download_file(self, url: str) -> Optional[bytes]:
        """Download file content into memory."""
        await self.init_session()
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    logger.info(f"📄 Downloaded file: {url}")
                    return await response.read()
                else:
                    logger.warning(f"❌ Failed to download {url}: {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"❌ Download timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"❌ Download error {url}: {e}")
            return None

    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """Extract text from PDF using PyMuPDF and a fallback to pdfminer.six."""
        text = ""
        try:
            # Attempt 1: Try PyMuPDF
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            for page in doc:
                text += page.get_text()
            doc.close()

            # Simple sanity check to see if extraction was successful
            if len(text) > 100:
                logger.info("✅ PyMuPDF extraction successful.")
                return text

        except Exception as e:
            logger.warning(f"PyMuPDF failed, trying fallback: {e}")
            
        try:
            # Attempt 2: Fallback to pdfminer.six
            output = BytesIO()
            extract_text_to_fp(BytesIO(pdf_content), output)
            text = output.getvalue().decode('utf-8')
            logger.info("✅ Fallback extraction with pdfminer.six succeeded.")
            return text
        except Exception as e:
            logger.error(f"❌ Fallback PDF extraction error: {e}")
            return ""

async def run_test():
    """Main test function to execute the single-file extraction."""
    scraper = EletoDocumentScraperTest()
    test_url = "http://www.eleto.gr/download/TermsOnFora/TermsOnFora.pdf"
    
    logger.info(f"🚀 Starting text extraction test on: {test_url}")
    file_content = await scraper.download_file(test_url)
    
    if file_content:
        extracted_text = scraper.extract_text_from_pdf(file_content)
        
        print("\n" + "="*20 + " EXTRACTED TEXT PREVIEW " + "="*20)
        # Print the first 1000 characters for a quick check
        print(extracted_text[:12000] + "...")
        print("="*66)
        
        # A simple log to show the test is complete
        if extracted_text:
            logger.info("✅ Test complete: The extraction logic appears to be working.")
        else:
            logger.warning("❌ Test incomplete: No text was extracted.")
    
    await scraper.close_session()

if __name__ == "__main__":
    asyncio.run(run_test())