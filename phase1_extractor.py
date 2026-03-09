# phase1_extractor.py
import pdfplumber

pdf_path = "Sources\Bullard, Thomas - UFO Abductions, The Measure of a Mystery - Volume 2.pdf"

print(f"Opening {pdf_path} using the range() function...")
print("-" * 40)

with pdfplumber.open(pdf_path) as pdf:
    
    # We use range() to generate the numbers 14, 15, and 16
    for i in range(3, 20):
        
        # We print the number so you, the human in the loop, can track progress
        print(f"Extracting PDF Page Index: {i}")
        
        # We use the number 'i' to grab the actual page object from the list
        current_page = pdf.pages[i]
        
        # Now we extract the text from that page object
        extracted_text = current_page.extract_text()
        
        print(extracted_text)
        print("--- END OF PAGE ---")

print("-" * 40)
print("Range extraction complete!")