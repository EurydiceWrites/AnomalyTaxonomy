"""
pipeline_ingest.py — Steps 0 and 1 of the generalized extraction pipeline.

Step 0: Extract text from a source file (PDF or plain text).
         - For digital PDFs: pdfplumber extracts the text layer directly (fast, no API cost).
         - For scanned/image PDFs: PyMuPDF renders each page as an image, then Gemini Flash
           reads the image and transcribes the text (1 API call per scanned page).
         - For .txt files: reads the file directly, no page processing needed.

Step 1: Send the assembled text to Gemini Flash for a lightweight metadata scan.
         One API call, no motif dictionary, no Volume 1 cache.

Usage:
    PDF (digital or scanned):
        python pipeline_ingest.py "Sources/Pipeline/Hopkins.pdf" 50 88

    Plain text file:
        python pipeline_ingest.py "Sources/Pipeline/gilgamesh.txt"

Output files saved to staging/:
    staging/extracted_text_{filename}_{start}-{end}.txt
    staging/metadata_{filename}_{start}-{end}.json
"""

import os
import sys
import re
import json
import argparse
from typing import Optional
from pydantic import BaseModel, Field
from typing import Literal

import pdfplumber
import fitz   # PyMuPDF — for rendering image-based PDF pages
from google import genai
from google.genai import types
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Pydantic model for the metadata scan output
# ---------------------------------------------------------------------------

class SourceAttribution(BaseModel):
    """Bibliographic identity of the source document,
    extracted from front matter."""

    author_name: Optional[str] = None
    title: str
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    place_of_publication: Optional[str] = None
    edition: Optional[str] = None
    translator: Optional[str] = None
    editor: Optional[str] = None
    author_role: Optional[Literal[
        "investigator",
        "translator",
        "editor",
        "author"
    ]] = None
    scan_complete: bool = False
    missing_fields: list[str] = []


class OcrPageResult(BaseModel):
    text: str = Field(description="All text from the page exactly as it appears, preserving paragraph structure and line breaks.")
    first_source_page: Optional[int] = Field(description="The first (lowest) printed page number visible on this scan — typically found in a running header or footer like '| 95' or '95 |'. If the scan shows two facing pages, return the lower number. Return null if no printed page numbers are visible.")


class ScannedMetadata(BaseModel):
    pseudonym: Optional[str] = Field(description="Name or pseudonym of the subject/protagonist. None if not identifiable.")
    age: Optional[str] = Field(description="Age of the subject at time of encounter, if stated.")
    gender: Optional[Literal["male", "female", "nonbinary", "unknown"]] = Field(description="Gender of the subject, if stated. Always lowercase.")
    date_of_encounter: Optional[str] = Field(description="Date or time period of the encounter, if stated.")
    location: Optional[str] = Field(description="Geographic location, if stated.")
    principal_investigator: Optional[str] = Field(description="Name of the investigator or researcher, if applicable.")
    memory_retrieval_method: Literal["conscious", "hypnosis", "altered", "mixed", "unknown", "not_applicable"] = Field(description="How the account was recalled. 'hypnosis' if retrieved under hypnotic regression. 'conscious' if naturally recalled. 'altered' if dream/trance/vision. 'mixed' if combination. 'not_applicable' if the source is not a recalled experience (e.g., authored literature, mythology, historical chronicle). 'unknown' if the source appears to be a recalled experience but the retrieval method is not stated.")
    number_of_witnesses: Optional[int] = Field(description="Number of witnesses, if stated.")
    entity_types: list[str] = Field(default=[], description="Types of entities described (e.g., 'Grey', 'humanoid', 'divine being', 'monster'). Return as a list — encounters can involve multiple entity types.")
    narrative_structure: Literal["investigation", "interview_dialogue", "first_person_testimony", "literary_narration", "compiled_catalogue", "not_applicable"] = Field(description="The narrative voice/structure of the text. 'investigation' = investigator narrates experiencer's account (e.g., Hopkins, Fowler). 'interview_dialogue' = interviewer and experiencer voices on the page (e.g., Clarke, Mack). 'first_person_testimony' = experiencer narrates their own experience (e.g., Ezekiel, Enoch). 'literary_narration' = characters acting within a narrative (e.g., Gilgamesh, Mahabharata). 'compiled_catalogue' = brief compiled case summaries from secondary sources (e.g., Vallee). 'not_applicable' = edge cases.")
    source_page_start: Optional[int] = Field(description="The first printed page number found in the body of the text (e.g., page numbers physically printed on the original document pages), NOT the PDF file page numbers.")
    source_page_end: Optional[int] = Field(description="The last printed page number found in the body of the text (e.g., page numbers physically printed on the original document pages), NOT the PDF file page numbers.")
    narrative_summary: str = Field(description="A brief 1-paragraph summary of the narrative content.")
    source_type: Literal["investigation", "ethnographic", "historical", "literary", "testimony", "unknown"] = Field(description="The type of source document. 'investigation' for clinical/field investigation reports. 'ethnographic' for cultural/anthropological accounts. 'historical' for historical records. 'literary' for epic/mythological/poetic texts. 'testimony' for first-person accounts without investigator. 'unknown' if unclear.")


# ---------------------------------------------------------------------------
# Front-matter scan: extract bibliographic source attribution
# ---------------------------------------------------------------------------

FRONT_MATTER_SYSTEM_PROMPT = (
    "You are examining the front matter of a published book or document. "
    "Extract bibliographic source attribution only. Do not extract narrative content.\n\n"
    "From the text provided, extract any of the following you can identify:\n"
    "- Author name(s)\n"
    "- Title of the work\n"
    "- Publication year\n"
    "- Publisher\n"
    "- Place of publication\n"
    "- Edition or printing (if not first)\n"
    "- Translator (if applicable)\n"
    "- Editor (if applicable)\n"
    "- Author's role: one of 'investigator', 'translator', 'editor', or 'author'\n"
    "  - Use 'investigator' when the author personally collected the data "
    "described in the book (e.g., conducted interviews, performed hypnosis, "
    "did fieldwork)\n"
    "  - Use 'translator' when the credited person translated the work\n"
    "  - Use 'editor' when the credited person compiled or edited others' work\n"
    "  - Use 'author' for all other cases\n\n"
    "Return your response as a JSON object matching the SourceAttribution schema. "
    "If you cannot determine a field, set it to null."
)


def _check_satisfaction(attr: SourceAttribution) -> bool:
    """
    Satisfaction condition: title is present AND at least one of
    (author_name, translator, editor) is present.
    """
    has_title = bool(attr.title and attr.title.strip())
    has_person = bool(
        (attr.author_name and attr.author_name.strip())
        or (attr.translator and attr.translator.strip())
        or (attr.editor and attr.editor.strip())
    )
    return has_title and has_person


def _get_missing_fields(attr: SourceAttribution) -> list:
    """List which required fields the scan could not populate."""
    missing = []
    if not attr.title or not attr.title.strip():
        missing.append("title")
    has_person = bool(
        (attr.author_name and attr.author_name.strip())
        or (attr.translator and attr.translator.strip())
        or (attr.editor and attr.editor.strip())
    )
    if not has_person:
        missing.append("author_name (or translator/editor)")
    return missing


def scan_front_matter(pdf_path, target_start_page):
    """
    Scan front-matter pages (before the user's target range) to extract
    bibliographic source attribution.

    Reads one page at a time from page 1 up to (but not including)
    target_start_page. After each page, sends accumulated text to Gemini Flash
    to extract whatever bibliographic info it can find.

    Stops early when the satisfaction condition is met (title + at least one
    person identified). If it reaches the target start page without satisfying,
    prompts the user for the missing fields.

    Parameters:
        pdf_path:          Path to the PDF
        target_start_page: The user's start page (1-indexed). We scan pages
                           before this.

    Returns:
        SourceAttribution object (always — either AI-complete or user-assisted)
    """
    print(f"\n[Front Matter] Scanning pages 1-{target_start_page - 1} "
          f"for source attribution...")

    accumulated_text = ""
    latest_attr = None

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        # Don't scan beyond what exists or past the target
        scan_end = min(target_start_page - 1, total_pages)

        if scan_end < 1:
            print("    [!] No front-matter pages to scan (target starts at page 1).")
            print("    [*] Proceeding with empty attribution — fill in at Step 2.")
            return SourceAttribution(
                title="Unknown",
                scan_complete=False,
                missing_fields=["title", "author_name (or translator/editor)"],
            )

        load_dotenv()
        gemini_client = genai.Client()

        for page_num in range(1, scan_end + 1):
            page_idx = page_num - 1
            page = pdf.pages[page_idx]
            raw_text = page.extract_text() or ""

            # If page is image-based, use Gemini OCR
            if len(raw_text.strip()) < 50:
                print(f"    [OCR] Front-matter page {page_num}...", end=" ", flush=True)
                raw_text, _ = ocr_page_with_gemini(gemini_client, pdf_path, page_idx)
                print("done.")

            if not raw_text.strip():
                continue

            accumulated_text += f"\n--- Page {page_num} ---\n{raw_text.strip()}\n"

            # Ask Gemini to extract attribution from what we have so far
            try:
                response = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=accumulated_text,
                    config=types.GenerateContentConfig(
                        system_instruction=FRONT_MATTER_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=SourceAttribution,
                        temperature=0.1,
                    ),
                )
                latest_attr = response.parsed
            except Exception as e:
                print(f"    [!] Gemini error on page {page_num}: {e}")
                continue

            # Check if we have enough
            if latest_attr and _check_satisfaction(latest_attr):
                latest_attr.scan_complete = True
                latest_attr.missing_fields = []
                _normalize_attribution(latest_attr)
                print(f"    [*] Source attribution satisfied after page {page_num}.")
                _print_attribution(latest_attr)
                return latest_attr

            print(f"    Page {page_num} scanned — not yet satisfied, continuing...")

    # Reached target start without satisfying
    if latest_attr:
        latest_attr.scan_complete = False
        latest_attr.missing_fields = _get_missing_fields(latest_attr)
    return _prompt_user_for_attribution(latest_attr)


def _normalize_attribution(attr: SourceAttribution):
    """
    Apply title-case to author_name and title so OCR all-caps output
    (e.g. "BUDD HOPKINS") becomes "Budd Hopkins" in the database.
    Called after AI extraction and after any user manual input.
    """
    if attr.title:
        attr.title = attr.title.title()
    if attr.author_name:
        attr.author_name = attr.author_name.title()
    if attr.translator:
        attr.translator = attr.translator.title()
    if attr.editor:
        attr.editor = attr.editor.title()


def _print_attribution(attr: SourceAttribution):
    """Print the extracted attribution in a readable format."""
    print()
    print("=== SOURCE ATTRIBUTION ===")
    if attr.title:
        print(f"  Title:       {attr.title}")
    if attr.author_name:
        print(f"  Author:      {attr.author_name}")
    if attr.author_role:
        print(f"  Role:        {attr.author_role}")
    if attr.translator:
        print(f"  Translator:  {attr.translator}")
    if attr.editor:
        print(f"  Editor:      {attr.editor}")
    if attr.publication_year:
        print(f"  Year:        {attr.publication_year}")
    if attr.publisher:
        print(f"  Publisher:   {attr.publisher}")
    if attr.place_of_publication:
        print(f"  Place:       {attr.place_of_publication}")
    if attr.edition:
        print(f"  Edition:     {attr.edition}")
    print(f"  Complete:    {attr.scan_complete}")
    print("=== END ATTRIBUTION ===")


def _prompt_user_for_attribution(attr):
    """
    When front-matter scan can't satisfy the condition, show what was found
    and ask the user for the missing required fields.
    """
    print()
    print("SOURCE ATTRIBUTION: INCOMPLETE")

    if attr is None:
        # Nothing found at all — need everything
        print("  Found:    (nothing)")
        print("  Missing:  title, author_name (or translator/editor)")
        print()
        print("The pipeline could not construct a complete source citation from the")
        print("front matter. Please provide the missing details to continue.")
        print()
        title = input("  Title: ").strip()
        author = input("  Author (or translator/editor): ").strip()
        attr = SourceAttribution(
            title=title or "Unknown",
            author_name=author or None,
            scan_complete=bool(title and author),
            missing_fields=_get_missing_fields(
                SourceAttribution(title=title or "Unknown", author_name=author or None)
            ),
        )
    else:
        # Show what was found and what's missing
        found = []
        if attr.title:
            found.append(f"title = {attr.title}")
        if attr.author_name:
            found.append(f"author = {attr.author_name}")
        if attr.translator:
            found.append(f"translator = {attr.translator}")
        if attr.editor:
            found.append(f"editor = {attr.editor}")
        if attr.publication_year:
            found.append(f"year = {attr.publication_year}")
        if attr.publisher:
            found.append(f"publisher = {attr.publisher}")

        print(f"  Found:    {', '.join(found) if found else '(nothing)'}")
        print(f"  Missing:  {', '.join(attr.missing_fields)}")
        print()
        print("The pipeline could not construct a complete source citation from the")
        print("front matter. Please provide the missing details to continue.")
        print()

        # Only prompt for what's actually missing
        if not attr.title or not attr.title.strip():
            title = input("  Title: ").strip()
            if title:
                attr.title = title

        has_person = bool(
            (attr.author_name and attr.author_name.strip())
            or (attr.translator and attr.translator.strip())
            or (attr.editor and attr.editor.strip())
        )
        if not has_person:
            author = input("  Author (or translator/editor): ").strip()
            if author:
                attr.author_name = author

        # Re-check satisfaction after user input
        attr.scan_complete = _check_satisfaction(attr)
        attr.missing_fields = _get_missing_fields(attr)

    _normalize_attribution(attr)
    _print_attribution(attr)
    return attr


# ---------------------------------------------------------------------------
# Step 0A: Page number detection helpers (for digital PDFs)
# ---------------------------------------------------------------------------

def detect_page_number(page_text):
    """
    Try to detect the printed page number from the first or last line of a page.

    Looks for lines that are just a number, or where the first or last token
    is a number (like a header/footer: "93" or "THE BOOK | 93").

    Returns the detected integer, or None if not found.
    """
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return None

    # Check first and last line only (headers/footers)
    for line in [lines[0], lines[-1]]:
        # Case 1: the entire line is just a number
        if re.fullmatch(r'\d+', line):
            return int(line)
        tokens = line.split()
        # Case 2: first token is a number (e.g. "93 | THE EPIC OF GILGAMESH")
        if re.fullmatch(r'\d+', tokens[0]):
            return int(tokens[0])
        # Case 3: last token is a number (e.g. "THE EPIC OF GILGAMESH | 93")
        if re.fullmatch(r'\d+', tokens[-1]):
            return int(tokens[-1])

    return None


def strip_page_number_line(page_text, page_number):
    """
    Remove the line containing the detected page number from the page text
    (first or last line only), so the LLM doesn't see a stray number.
    """
    if page_number is None:
        return page_text

    lines = page_text.splitlines()
    non_blank = [(i, line) for i, line in enumerate(lines) if line.strip()]
    if not non_blank:
        return page_text

    page_num_str = str(page_number)
    for idx, line in [non_blank[0], non_blank[-1]]:
        stripped = line.strip()
        tokens = stripped.split()
        if (stripped == page_num_str or
                (tokens and tokens[0] == page_num_str) or
                (tokens and tokens[-1] == page_num_str)):
            lines[idx] = ""
            break

    return "\n".join(lines)


def validate_page_numbers(pages):
    """
    Check whether detected source page numbers are reliable across 3+ pages.

    Works for both single-page scans (source increments by 1 per PDF page)
    and two-page spreads (source increments by 2 per PDF page).

    Gaps are fine — pages where detection returned None are simply skipped.

    Returns:
        (reliable: bool, step: int or None, intercept: int or None)
        - step is how many source pages each PDF page covers (1 or 2)
        - intercept lets you compute: source_page = step * pdf_page + intercept
    """
    from collections import Counter

    detected = sorted(
        [(p["pdf_page"], p["source_page"]) for p in pages if p["source_page"] is not None]
    )

    if len(detected) < 3:
        return False, None, None

    # For each consecutive pair of detected pages, figure out how many source
    # pages advance per PDF page. 1 = normal scan, 2 = two-page spread.
    steps = []
    for i in range(1, len(detected)):
        pdf_delta = detected[i][0] - detected[i-1][0]
        src_delta = detected[i][1] - detected[i-1][1]
        if pdf_delta > 0:
            step = round(src_delta / pdf_delta)
            if step in (1, 2):   # only trust realistic values
                steps.append(step)

    if len(steps) < 2:
        return False, None, None

    most_common_step, count = Counter(steps).most_common(1)[0]
    if count < 2:
        return False, None, None

    # Compute the intercept (b in: source = step * pdf + b) for each detected
    # page, then take the median for robustness against outliers.
    intercepts = [src - most_common_step * pdf for pdf, src in detected]
    intercept = sorted(intercepts)[len(intercepts) // 2]

    return True, most_common_step, intercept


# ---------------------------------------------------------------------------
# Step 0B: OCR via Gemini Flash (for image-based PDF pages)
# ---------------------------------------------------------------------------

def ocr_page_with_gemini(client, pdf_path, page_idx):
    """
    Render one PDF page as an image using PyMuPDF and send it to Gemini Flash
    for text transcription. Used when pdfplumber finds no text layer.

    Parameters:
        client:    Gemini API client
        pdf_path:  Path to the PDF file
        page_idx:  0-indexed page number

    Returns:
        (text, source_page) where text is the extracted string and source_page
        is the first printed page number found on the scan (or None if not found).
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_idx]

        # Render at 2x zoom for better OCR quality
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                ("Transcribe all text from this image exactly as it appears. "
                 "Also identify the first printed page number visible (in a running "
                 "header or footer). If this is a two-page spread, return the lower "
                 "page number. Return null for first_source_page if none is visible."),
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
                response_schema=OcrPageResult,
            ),
        )
        result: OcrPageResult = response.parsed
        return result.text or "", result.first_source_page

    except Exception as e:
        print(f"    [!] OCR failed for page index {page_idx}: {e}")
        return "", None


# ---------------------------------------------------------------------------
# Step 0: PDF text extraction (digital + scanned)
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path, start_page, end_page):
    """
    Extract text from a PDF page range.

    For each page:
      - Tries pdfplumber first (fast, free, works for digital PDFs).
      - If the page returns little or no text (< 50 chars), assumes it is a
        scanned image page and falls back to Gemini Flash OCR via PyMuPDF.
        This costs one Gemini Flash API call per image page.

    Parameters:
        pdf_path:   Path to the PDF file
        start_page: First page (1-indexed, matching PDF viewer)
        end_page:   Last page (1-indexed, inclusive)

    Returns:
        (pages, full_text) where pages is a list of dicts and full_text is the
        assembled string with [--- PAGE MARKER ---] headers.
    """
    print(f"\n[Step 0] Extracting text from PDF: {os.path.basename(pdf_path)}")
    print(f"         Pages {start_page} to {end_page}")

    load_dotenv()
    gemini_client = None   # only initialised if OCR is needed

    pages = []
    ocr_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if end_page > total_pages:
            print(f"    [!] PDF has {total_pages} pages; clamping end page to {total_pages}.")
            end_page = total_pages

        for pdf_page_num in range(start_page, end_page + 1):
            page_idx = pdf_page_num - 1
            page = pdf.pages[page_idx]
            raw_text = page.extract_text() or ""

            if len(raw_text.strip()) < 50:
                # Image-based page — fall back to Gemini OCR.
                # The OCR call also returns the first printed page number it sees,
                # so we don't need detect_page_number() for scanned pages.
                if gemini_client is None:
                    print("    [*] Image-based pages detected. Initialising Gemini Flash OCR...")
                    gemini_client = genai.Client()
                print(f"    [OCR] Page {pdf_page_num}...", end=" ", flush=True)
                raw_text, source_page = ocr_page_with_gemini(gemini_client, pdf_path, page_idx)
                print("done.")
                ocr_count += 1
                cleaned_text = raw_text.strip()
            else:
                # Digital page — detect page number from text position (header/footer)
                source_page = detect_page_number(raw_text)
                cleaned_text = strip_page_number_line(raw_text, source_page)

            pages.append({
                "pdf_page": pdf_page_num,
                "source_page": source_page,
                "text": cleaned_text.strip(),
            })

    # Validate page number consistency.
    # step=1 means one book page per PDF page (normal).
    # step=2 means two book pages per PDF page (two-page spread scans).
    # Fill in any pages where detection returned None using the fitted formula.
    reliable, step, intercept = validate_page_numbers(pages)
    if reliable:
        for p in pages:
            if p["source_page"] is None:
                p["source_page"] = step * p["pdf_page"] + intercept
        first = pages[0]["source_page"]
        last = pages[-1]["source_page"]
        scan_type = "two-page spread" if step == 2 else "single-page"
        print(f"    [*] Printed page numbers detected: {first}-{last} "
              f"({scan_type}, reliable)")
    else:
        if any(p["source_page"] for p in pages):
            print("    [!] Page numbers detected but inconsistent — clearing. "
                  "Source pages will need manual entry.")
        for p in pages:
            p["source_page"] = None

    total_chars = sum(len(p["text"]) for p in pages)
    print(f"    [*] Extracted {len(pages)} pages, {total_chars:,} characters"
          + (f" ({ocr_count} via OCR)" if ocr_count else "") + ".")

    full_text = _assemble_pages(pages)
    return pages, full_text


# ---------------------------------------------------------------------------
# Step 0 (text file variant)
# ---------------------------------------------------------------------------

def extract_txt_text(txt_path):
    """
    Read a plain text file and assemble it for the pipeline.
    No page number processing — the whole file is treated as one block.

    Returns:
        (pages, full_text) in the same format as extract_pdf_text(), with a
        single entry representing the whole file.
    """
    print(f"\n[Step 0] Reading text file: {os.path.basename(txt_path)}")

    with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    print(f"    [*] Read {len(content):,} characters.")

    pages = [{
        "pdf_page": None,
        "source_page": None,
        "text": content,
    }]

    marker = f"[--- TEXT FILE: {os.path.basename(txt_path)} ---]"
    full_text = f"{marker}\n{content}"

    return pages, full_text


# ---------------------------------------------------------------------------
# Shared assembly helper
# ---------------------------------------------------------------------------

def _assemble_pages(pages):
    """Build the full text string with page markers from a list of page dicts."""
    lines = []
    for p in pages:
        if p["pdf_page"] is None:
            # Should not happen for PDF pages, but guard anyway
            lines.append(p["text"])
        elif p["source_page"] is not None:
            lines.append(f"[--- PDF PAGE {p['pdf_page']} / SOURCE PAGE {p['source_page']} ---]")
        else:
            lines.append(f"[--- PDF PAGE {p['pdf_page']} ---]")
        lines.append(p["text"])
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 1: Metadata scan via Gemini Flash
# ---------------------------------------------------------------------------

def scan_metadata(full_text, source_path, start_page, end_page, attribution=None):
    """
    Send the extracted text to Gemini Flash for a lightweight metadata scan.

    Single API call — no chunking, no motif dictionary, no Volume 1 cache.

    If a SourceAttribution is provided and author_role == "investigator",
    auto-populates principal_investigator from author_name when the scan
    returns null for that field.

    Returns:
        ScannedMetadata object
    """
    print(f"\n[Step 1] Running metadata scan via Gemini Flash...")

    load_dotenv()
    client = genai.Client()

    system_instruction = (
        "You are a metadata extraction assistant. Read the provided text and extract "
        "whatever metadata you can find. Every field is optional except narrative_summary "
        "and source_type. Do not invent information — if a field is not present in the "
        "text, return null. Return valid JSON matching the schema. "
        "The text contains page markers in the format [--- PDF PAGE X ---] or "
        "[--- PDF PAGE X / SOURCE PAGE Y ---]. When extracting source_page_start and "
        "source_page_end, report the SOURCE PAGE numbers (the numbers physically printed "
        "on the original document), not the PDF PAGE numbers. If only PDF page numbers "
        "are available, report those but note the distinction. "
        "The provided text may include introductory, prefatory, or scholarly material "
        "alongside the primary narrative. Use all available pages to extract metadata — "
        "introductions often contain dates, authorship, and historical context that the "
        "narrative itself does not. Do not discard prefatory content."
    )

    # If we have an author from front-matter who isn't yet classified as
    # "investigator", ask the scan to check the narrative for evidence
    if (attribution
            and attribution.author_name
            and attribution.author_role in ("author", None)):
        system_instruction += (
            f" The source attribution identifies '{attribution.author_name}' as the "
            "author. Examine the narrative text for evidence that this person personally "
            "conducted the investigation described — for example, first-person accounts "
            "of interviewing witnesses, arranging hypnosis sessions, visiting sites, or "
            "collecting evidence. If such evidence is found, set principal_investigator "
            f"to '{attribution.author_name}'."
        )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=full_text,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=ScannedMetadata,
            temperature=0.1,
        ),
    )

    metadata: ScannedMetadata = response.parsed
    print("    [*] Scan complete.")

    # Auto-populate principal_investigator from SourceAttribution.
    # Case 1: Front-matter already tagged as "investigator" but scan missed it.
    # Case 2: Scan found investigative voice and set principal_investigator —
    #          upgrade the attribution's author_role to "investigator".
    if attribution and attribution.author_name:
        if (attribution.author_role == "investigator"
                and not metadata.principal_investigator):
            # Case 1: already known investigator, scan missed it
            metadata.principal_investigator = attribution.author_name
            print(f"    [*] Auto-populated investigator from source attribution: "
                  f"{attribution.author_name}")
        elif (attribution.author_role in ("author", None)
                and metadata.principal_investigator
                and attribution.author_name.lower() in metadata.principal_investigator.lower()):
            # Case 2: scan detected the author IS the investigator — upgrade role
            attribution.author_role = "investigator"
            print(f"    [*] Author role upgraded to 'investigator': "
                  f"{attribution.author_name}")

    # Formatted summary for Shawna to review
    filename = os.path.basename(source_path)
    page_info = f"pages {start_page}-{end_page}" if start_page is not None else "full file"

    print()
    print("=== METADATA SCAN RESULTS ===")
    print(f"Source:     {filename} ({page_info})")
    print(f"Subject:    {metadata.pseudonym or 'None'}")
    print(f"Type:       {metadata.source_type}")
    print(f"Location:   {metadata.location or 'None'}")
    print(f"Date:       {metadata.date_of_encounter or 'None'}")
    print(f"Retrieval:  {metadata.memory_retrieval_method}")
    print(f"Summary:    {metadata.narrative_summary}")
    print("---")
    print(f"Investigator:  {metadata.principal_investigator or 'None'}")
    print(f"Witnesses:     {metadata.number_of_witnesses if metadata.number_of_witnesses is not None else 'None'}")
    print(f"Entity Types:  {', '.join(metadata.entity_types) if metadata.entity_types else 'None'}")
    print(f"Structure:     {metadata.narrative_structure}")
    src_range = (f"{metadata.source_page_start}-{metadata.source_page_end}"
                 if metadata.source_page_start is not None else "None")
    print(f"Source Pages:  {src_range}")
    print("=== END SCAN ===")

    return metadata


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _slugify(text):
    """Convert text to a safe lowercase slug for filenames."""
    if not text:
        return "unknown"
    slug = re.sub(r'[^\w\s\-]', '', text.lower())
    slug = re.sub(r'[\s\-]+', '_', slug).strip('_')
    return slug or "unknown"


def _build_pipeline_json(metadata, attribution, text_output_path,
                         start_page, end_page, pages):
    """
    Build the consolidated pipeline JSON containing all metadata from Steps 0 and 1.
    This is the single file that flows through the rest of the pipeline.
    """
    # Determine source page range from detected pages (if any)
    source_start = metadata.source_page_start
    source_end = metadata.source_page_end

    pipeline = {
        "step_0": {
            "source_text_path": text_output_path,
            "pdf_page_start": start_page,
            "pdf_page_end": end_page,
            "source_page_start": source_start,
            "source_page_end": source_end,
        },
        "step_1_scanned_metadata": {
            "source_type": metadata.source_type,
            "memory_retrieval_method": metadata.memory_retrieval_method,
            "narrative_structure": metadata.narrative_structure,
            "principal_investigator": metadata.principal_investigator,
            "experiencer_name": metadata.pseudonym,
            "gender": metadata.gender,
            "age_at_time": metadata.age,
            "location": metadata.location,
            "date_of_experience": metadata.date_of_encounter,
            "entity_types": metadata.entity_types,
            "narrative_summary": metadata.narrative_summary,
        },
        "step_1_source_attribution": {
            "author_name": attribution.author_name if attribution else None,
            "title": attribution.title if attribution else None,
            "publication_year": attribution.publication_year if attribution else None,
            "publisher": attribution.publisher if attribution else None,
            "place_of_publication": attribution.place_of_publication if attribution else None,
            "edition": attribution.edition if attribution else None,
            "translator": attribution.translator if attribution else None,
            "editor": attribution.editor if attribution else None,
            "author_role": attribution.author_role if attribution else None,
        },
        "step_3_extraction": None,
    }

    return pipeline


def _make_pipeline_json_path(metadata, attribution, source_text_path=None):
    """
    Build the JSON filename: staging/{experiencer_name}_{source_title}_metadata.json
    Falls back to the source text filename when both experiencer and title are unknown,
    to prevent filename collisions.
    """
    experiencer = _slugify(metadata.pseudonym) if metadata.pseudonym else "unknown"
    title = _slugify(attribution.title) if attribution and attribution.title else "unknown"
    # If both are unknown, use the source text filename to avoid collisions
    if experiencer == "unknown" and title == "unknown" and source_text_path:
        source_stem = os.path.splitext(os.path.basename(source_text_path))[0]
        source_stem = source_stem.replace("extracted_text_", "")
        filename = f"unknown_{_slugify(source_stem)}_metadata.json"
    else:
        filename = f"{experiencer}_{title}_metadata.json"
    return os.path.join("staging", filename)


def _display_and_confirm(pipeline_json, json_path):
    """
    Display the pipeline JSON in the terminal and wait for user confirmation.
    """
    print()
    print("=" * 65)
    print("  PIPELINE METADATA — REVIEW BEFORE PROCEEDING")
    print("=" * 65)

    # Step 0 summary
    s0 = pipeline_json["step_0"]
    print(f"\n  Source text:  {s0['source_text_path']}")
    print(f"  PDF pages:   {s0['pdf_page_start']}-{s0['pdf_page_end']}")
    src = (f"{s0['source_page_start']}-{s0['source_page_end']}"
           if s0['source_page_start'] is not None else "None")
    print(f"  Source pages: {src}")

    # Step 1 metadata
    s1 = pipeline_json["step_1_scanned_metadata"]
    print(f"\n  Experiencer:  {s1['experiencer_name'] or 'None'}")
    print(f"  Gender:       {s1['gender'] or 'None'}")
    print(f"  Age:          {s1['age_at_time'] or 'None'}")
    print(f"  Type:         {s1['source_type']}")
    print(f"  Structure:    {s1['narrative_structure']}")
    print(f"  Retrieval:    {s1['memory_retrieval_method']}")
    print(f"  Investigator: {s1['principal_investigator'] or 'None'}")
    print(f"  Location:     {s1['location'] or 'None'}")
    print(f"  Date:         {s1['date_of_experience'] or 'None'}")
    print(f"  Entities:     {', '.join(s1['entity_types']) if s1['entity_types'] else 'None'}")
    print(f"  Summary:      {s1['narrative_summary'][:100]}...")

    # Attribution
    sa = pipeline_json["step_1_source_attribution"]
    print(f"\n  Author:       {sa['author_name'] or 'None'}")
    print(f"  Title:        {sa['title'] or 'None'}")
    print(f"  Role:         {sa['author_role'] or 'None'}")
    if sa['publication_year']:
        print(f"  Year:         {sa['publication_year']}")

    print()
    print("=" * 65)

    # Confirmation loop
    while True:
        choice = input("\nMetadata looks correct? [y/n/edit]: ").strip().lower()

        if choice == "y":
            print("[*] Metadata confirmed. Ready for Step 3 (extraction).")
            return pipeline_json

        elif choice == "n":
            print("[*] Exiting. No extraction will be run.")
            sys.exit(0)

        elif choice == "edit":
            print(f"\n[*] Edit the JSON file at:\n    {json_path}")
            print("[*] Make your changes, save the file, then press Enter to continue.")
            input("    Press Enter when done... ")

            # Re-read the edited JSON
            with open(json_path, "r", encoding="utf-8") as f:
                pipeline_json.update(json.load(f))

            # Re-save (in case the user edited with formatting issues)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(pipeline_json, f, indent=2, ensure_ascii=False)

            print("[*] JSON re-loaded. Displaying updated metadata...")
            # Re-display
            return _display_and_confirm(pipeline_json, json_path)

        else:
            print("  Please enter 'y', 'n', or 'edit'.")


def make_output_stem(source_path, start_page, end_page):
    """Build a safe filename stem, e.g. 'Hopkins_50-88'."""
    basename = os.path.basename(source_path)
    name_no_ext = os.path.splitext(basename)[0]
    safe_name = re.sub(r'[^\w\-]', '_', name_no_ext)
    if start_page is not None:
        return f"{safe_name}_{start_page}-{end_page}"
    return safe_name


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Steps 0 + 1: Extract source text and scan metadata.",
        epilog=(
            "Examples:\n"
            "  PDF:  python pipeline_ingest.py Sources/Hopkins.pdf 50 88\n"
            "  Text: python pipeline_ingest.py --text Sources/gilgamesh.txt"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pdf_path", nargs="?", default=None,
                        help="Path to a PDF file.")
    parser.add_argument("start_page", type=int, nargs="?", default=None,
                        help="First PDF page to extract (1-indexed).")
    parser.add_argument("end_page", type=int, nargs="?", default=None,
                        help="Last PDF page to extract (1-indexed, inclusive).")
    parser.add_argument("--text", metavar="FILE",
                        help="Path to a plain text file. Use instead of pdf_path + page args.")
    parser.add_argument("--model", default="claude-opus-4-6",
                        choices=["gemini-2.5-pro", "gemini-3.1-pro-preview", "claude-opus-4-6"],
                        help="Which LLM to use for Step 3 extraction (default: claude-opus-4-6)")
    parser.add_argument("--include-vol1", action="store_true",
                        help="Load Bullard Volume 1 context (off by default — dictionary-only mode)")
    args = parser.parse_args()

    # Determine mode
    if args.text:
        # Text mode
        source_path = args.text
        is_pdf = False
    elif args.pdf_path:
        # PDF mode
        source_path = args.pdf_path
        is_pdf = True
    else:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(source_path):
        print(f"Error: File '{source_path}' not found.")
        sys.exit(1)

    if is_pdf and (args.start_page is None or args.end_page is None):
        print("Error: PDF input requires start_page and end_page arguments.")
        print("  Usage: python pipeline_ingest.py file.pdf 1 50")
        sys.exit(1)

    os.makedirs("staging", exist_ok=True)

    # Front-matter scan (PDF only — text files don't have front matter)
    attribution = None
    if is_pdf:
        attribution = scan_front_matter(source_path, args.start_page)

    # Step 0: Extract text
    if is_pdf:
        pages, full_text = extract_pdf_text(source_path, args.start_page, args.end_page)
    else:
        pages, full_text = extract_txt_text(source_path)

    # Save extracted text
    stem = make_output_stem(source_path, args.start_page, args.end_page)
    text_output_path = os.path.join("staging", f"extracted_text_{stem}.txt")
    with open(text_output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    print(f"\n[*] Extracted text saved to: {text_output_path}")

    # Step 1: Metadata scan
    metadata = scan_metadata(full_text, source_path, args.start_page, args.end_page,
                             attribution=attribution)

    # Build the consolidated pipeline JSON
    pipeline_json = _build_pipeline_json(
        metadata, attribution, text_output_path,
        args.start_page, args.end_page, pages,
    )

    # Save the JSON using the naming convention:
    # staging/{experiencer_name}_{source_title}_metadata.json
    json_path = _make_pipeline_json_path(metadata, attribution, text_output_path)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pipeline_json, f, indent=2, ensure_ascii=False)
    print(f"\n[*] Pipeline JSON saved to: {json_path}")

    # Display the JSON and wait for confirmation
    _display_and_confirm(pipeline_json, json_path)

    # Step 3: Extraction via LLM bridge
    print(f"\n[*] Starting Step 3: Extraction via extract_narrative() (model: {args.model})...")
    from llm_bridge import extract_narrative, classify_voice_tags

    final_profile, all_events, ai_events_json, chunks = extract_narrative(
        pipeline_json_path=json_path,
        profile_name="baseline_test",
        model=args.model,
        include_vol1=args.include_vol1,
    )

    print(f"\n[*] Pass 1 extraction complete: {len(all_events)} events")

    # Pass 2: Voice classification
    ai_events_json = classify_voice_tags(ai_events_json, chunks, model=args.model)

    print(f"[*] Results merged into: {json_path}")


if __name__ == "__main__":
    main()
