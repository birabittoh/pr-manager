from pathlib import Path
from datetime import datetime
import img2pdf

month_names = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
]

separator = " — "

def get_title_from_filename(filename: Path) -> str:
    """Extract title from filename by removing extensions and replacing underscores with spaces
       e.g. corriere-della-sera_20240615.temp.pdf -> Corriere Della Sera - 15 giugno 2024
    """
    
    base = filename.stem.replace(".temp", "")

    parts = base.split("_")
    if len(parts) < 2:
        return base.title()

    name_part = "_".join(parts[:-1])
    date_part = parts[-1]
    try:
        date_obj = datetime.strptime(date_part, "%Y%m%d")
        formatted_date = f"{date_obj.day} {month_names[date_obj.month - 1]} {date_obj.year}"
    except ValueError:
        formatted_date = date_part

    return name_part.replace('-', ' ').title() + separator + formatted_date

def get_hashtag(file_title: str) -> str:
    """Generate hashtags based on file title
       L'Uncinetto di Giò — 14 dicembre 2025 -> #LUncinettoDiGiò"""
    name = file_title.split(separator)[0].strip().title().replace("'", "").replace(" ", "")
    return "#" + name


def save_images_as_pdf(images: list[bytes], output_path: Path) -> None:
    """Save a list of images as a single PDF file"""
    pdf_bytes = img2pdf.convert(images)
    
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
