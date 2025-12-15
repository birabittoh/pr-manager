from peewee import *
from datetime import datetime
from modules import config

db_path = str(config.DATABASE_PATH)
db = SqliteDatabase(db_path)

class BaseModel(Model):
    class Meta:
        database = db

class Publication(BaseModel):
    name = CharField(unique=True)
    issue_id = CharField()
    max_scale = IntegerField()
    language = CharField()
    enabled = BooleanField(default=True)
    last_finished = CharField(null=True)
    created_at = DateTimeField(default=datetime.now)

class FileWorkflow(BaseModel):
    publication_name = CharField()
    date = CharField()
    downloaded = BooleanField(default=False)
    ocr_processed = BooleanField(default=False)
    uploaded = BooleanField(default=False)
    channel_id = IntegerField(null=True)
    message_id = IntegerField(null=True)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)
    
    class Meta:
        indexes = (
            (('publication_name', 'date'), True),
        )

def init_db():
    db.connect()
    db.create_tables([Publication, FileWorkflow])
    
    # Load publications from input.json
    import json
    from pathlib import Path
    
    input_file = Path(__file__).parent.parent / "input.json"
    if input_file.exists():
        with open(input_file, 'r') as f:
            publications = json.load(f)
            for pub in publications:
                Publication.get_or_create(
                    name=pub['name'],
                    defaults={
                        'issue_id': pub['issue_id'],
                        'max_scale': pub['max_scale'],
                        'language': pub['language']
                    }
                )
    db.close()
