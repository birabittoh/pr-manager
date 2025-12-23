from os import name
from pathlib import Path
from datetime import datetime

from modules.database import FileWorkflow

month_names = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
]

date_format = "%Y%m%d"
to_be_removed = " ',.!?;:-_()\""
separator = " — "
fw_separator = "_"
pdf_suffix = ".pdf"
temp_suffix = ".temp" + pdf_suffix
thumbnail_suffix = ".jpg"

def split_filename(filename: Path) -> tuple[str, str]:
    """Split filename into publication name and date string
       e.g. corriere-della-sera_20240615.temp.pdf -> (corriere-della-sera, 20240615)
    """
    base = filename.stem.replace(".temp", "")
    parts = base.split(fw_separator)
    if len(parts) < 2:
        return base, ""
    publication_name = fw_separator.join(parts[:-1])
    date_str = parts[-1]
    return publication_name, date_str

def _get_info_from_filename(filename: Path) -> tuple[str,str]:
    """Extract title from filename by removing extensions and replacing underscores with spaces
       e.g. corriere-della-sera_20240615.temp.pdf -> Corriere Della Sera - 15 giugno 2024
    """
    
    name_part, date_part = split_filename(filename)
    name = name_part.replace('-', ' ').title()

    try:
        date_obj = datetime.strptime(date_part, date_format)
        formatted_date = f"{date_obj.day} {month_names[date_obj.month - 1]} {date_obj.year}"
    except ValueError:
        formatted_date = date_part

    return name, formatted_date

def _get_title(file_path: Path, display_name: str) -> str:
    """Generate title for the file based on display name or filename"""
    name, formatted_date = _get_info_from_filename(file_path)

    if display_name:
        name = display_name
    if formatted_date:
        formatted_date = separator + formatted_date

    return name + formatted_date

def _get_hashtag(file_title: str) -> str:
    """Generate hashtags based on file title
       L'Uncinetto di Giò — 14 dicembre 2025 -> #LUncinettoDiGiò"""
    name = file_title.split(separator)[0].strip().title()
    return "#" + "".join([c for c in name if c not in to_be_removed])

def get_caption(file_path: Path, display_name: str) -> str:
    """Generate caption for Telegram upload"""
    title = _get_title(file_path, display_name)
    hashtag = _get_hashtag(title)
    return f"{title}\n\n{hashtag}"

def get_fw_id(fw_key: str) -> str:
    return fw_key[:4]

def get_fw_date(fw_key: str) -> str:
    return fw_key[4:12]

def get_fw_ver(fw_key: str) -> int:
    return int(fw_key[12:20])

def guess_fw_key(issue_id: str, date_str: str) -> str:
    return issue_id + date_str + "00000000001001"

def get_fw_key(fw: FileWorkflow) -> str:
    date = get_fw_date(str(fw.key))
    return get_key(str(fw.publication_name), date)

def get_key(publication_name: str, date_str: str) -> str:
    return publication_name + fw_separator + date_str + pdf_suffix
