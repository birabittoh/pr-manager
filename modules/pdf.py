from pathlib import Path
from PIL import Image
from datetime import datetime
from io import BytesIO

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


def save_images_as_pdf(images_io: list[BytesIO], output_path: Path) -> None:
    """Save a list of images as a single PDF file, with metadata, without recompression and saving quality and resolution for each image"""
    pil_images = []
    for img_io in images_io:
        img_io.seek(0)
        img = Image.open(img_io)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        pil_images.append(img)

    if not pil_images:
        raise ValueError("No images to save as PDF")

    first_image, *rest_images = pil_images

    pdf_info = {
        "Title": get_title_from_filename(output_path),
        "CreationDate": datetime.now().strftime("D:%Y%m%d%H%M%S"),
    }

    first_image.save(
        output_path,
        save_all=True,
        append_images=rest_images,
        format="PDF",
        #resolution=300.0,
        #quality=95,
        pdfinfo=pdf_info
    )
