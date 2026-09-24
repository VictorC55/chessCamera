import pymupdf

pdf_path = "50images.pdf"
output_prefix = "photo"

doc = pymupdf.open(pdf_path)

saved_count = 0
# start at index 1 (Page 2), step by 2 to skip logo pages
for page_num in range(len(doc)):
    page = doc[page_num]
    pix = page.get_pixmap(dpi=300)
    
    saved_count += 1
    filename = f"pictures/50test/{output_prefix}_{saved_count:02d}.jpg"
    pix.save(filename)
    print(f"Saved photo {saved_count} (from PDF page {page_num + 1})")

doc.close()
print(f"Finished! Extracted {saved_count} clean photos.")