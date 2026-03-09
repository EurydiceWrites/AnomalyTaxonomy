import pdfplumber
import os

pdf_path = os.path.join("Sources", "John E. Mack, MD - Abduction - Human Encounters with Aliens.pdf")

print(f"Reading Mack PDF: {pdf_path}")

try:
    with pdfplumber.open(pdf_path) as pdf:
        # Let's extract pages 68-91 which contains the full "Sheila" case
        # You can adjust these page numbers depending on the PDF's structure
        text = ""
        for i in range(68, 92):
            try:
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except IndexError:
                # In case the PDF has fewer pages than expected
                break
        
        # Save it to a text file
        output_file = "mack_sample_text.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)
            
        print(f"Extraction successful! Sample narrative saved to {output_file}.")
        print("Here's a preview:\n")
        print(text[:1000] + "\n...[Truncated]")
except Exception as e:
    print(f"Error reading PDF: {e}")
