from pathlib import Path
from datetime import datetime
import img2pdf

def get_title_from_filename(filename: Path) -> str:
    """Extract title from filename by removing extensions and replacing underscores with spaces
       e.g. corriere-della-sera-1_20240615.temp.pdf -> Corriere Della Sera - 15/06/2024
    """
    
    base = filename.stem.replace(".temp", "")

    parts = base.split("_")
    if len(parts) < 2:
        return base.title()

    name_part = "_".join(parts[:-1])
    date_part = parts[-1]
    try:
        date_obj = datetime.strptime(date_part, "%Y%m%d")
        formatted_date = date_obj.strftime("%d/%m/%Y")
    except ValueError:
        formatted_date = date_part

    # if name part ends with "-\d+", remove that part
    if '-' in name_part:
        split_result = name_part.rsplit('-', 1)
        possible_number = split_result[-1]
        if possible_number.isdigit():
            name_part = split_result[0]

    title = f"{name_part.replace('-', ' ').title()} - {formatted_date}"
    return title


def save_images_as_pdf(images: list[bytes], output_path: Path) -> None:
    """Save a list of images as a single PDF file"""
    pdf_bytes = img2pdf.convert(images)
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
