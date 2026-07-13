"""
PDF Text Extraction Service.

Stage: Input Pre-processing (text-only PDFs).

Uses ``pdfplumber`` to extract raw text page-by-page from a PDF file.
Scanned / image-based PDFs that yield no extractable text are explicitly
rejected with a clear error — OCR is intentionally NOT attempted.
"""

from typing import Optional

import pdfplumber

from app.utils.logger import get_logger

logger = get_logger("pdf_service")


class PDFService:
    """Service to extract plain text from text-based PDF files using pdfplumber."""

    def extract_text(self, pdf_path: str) -> str:
        """
        Extract all readable text from a text-based PDF file.

        Iterates through every page and accumulates text content. If the
        resulting combined text is empty (e.g. scanned/image PDF), a
        ``ValueError`` is raised immediately — no OCR is attempted.

        Args:
            pdf_path: Absolute filesystem path to the PDF file to extract.

        Returns:
            A single string containing all extracted text from the document,
            with pages separated by a double newline.

        Raises:
            ValueError: If the PDF contains no extractable text (likely a
                scanned or image-only document).
            IOError: If the file cannot be opened or read.
        """
        logger.info(f"Starting PDF text extraction from: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"PDF opened successfully. Total pages: {total_pages}")

                page_texts: list[str] = []

                for page_num, page in enumerate(pdf.pages, start=1):
                    try:
                        page_text: Optional[str] = page.extract_text()
                        if page_text and page_text.strip():
                            page_texts.append(page_text.strip())
                            logger.info(
                                f"Page {page_num}/{total_pages}: extracted "
                                f"{len(page_text.strip())} characters."
                            )
                        else:
                            logger.info(
                                f"Page {page_num}/{total_pages}: no text found "
                                f"(possibly an image page)."
                            )
                    except Exception as page_exc:
                        logger.warning(
                            f"Page {page_num}/{total_pages}: extraction error "
                            f"(skipped): {page_exc}",
                            exc_info=True,
                        )

        except Exception as exc:
            logger.error(
                f"Failed to open or process PDF at '{pdf_path}': {exc}",
                exc_info=True,
            )
            raise IOError(
                f"Could not open or read the PDF file. "
                f"Please ensure it is a valid, non-encrypted PDF. Detail: {exc}"
            ) from exc

        combined_text = "\n\n".join(page_texts).strip()

        if not combined_text:
            logger.error(
                f"PDF '{pdf_path}' yielded no extractable text across "
                f"all {total_pages} page(s). This is likely a scanned or "
                f"image-only PDF."
            )
            raise ValueError(
                "No text could be extracted from this PDF. "
                "The document appears to be a scanned or image-based PDF. "
                "Please upload a text-based PDF (one where you can select and copy text). "
                "OCR is not supported."
            )

        logger.info(
            f"PDF text extraction complete. "
            f"Total characters extracted: {len(combined_text)} from {len(page_texts)} page(s)."
        )
        return combined_text
