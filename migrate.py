import sqlite3

DB_PATH = "database.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        print("Rinomino colonna date -> key...")
        cur.execute("""
            ALTER TABLE fileworkflow
            RENAME COLUMN date TO key
        """)
    except sqlite3.OperationalError as e:
        # La colonna potrebbe essere già stata rinominata
        print(f"Avviso: {e}")

    print("Carico mapping publication.name -> id (4 caratteri)...")
    cur.execute("""
        SELECT name, id
        FROM publication
    """)
    publication_ids = {
        row["name"]: str(row["id"]).zfill(4)
        for row in cur.fetchall()
    }

    print("Aggiorno i valori di key...")
    cur.execute("""
        SELECT rowid, publication_name, key
        FROM fileworkflow
    """)

    rows = cur.fetchall()

    for row in rows:
        rowid = row["rowid"]
        publication_name = row["publication_name"]
        old_key = str(row["key"])

        pub_id = publication_ids.get(publication_name)
        if not pub_id:
            raise RuntimeError(
                f"Nessuna publication trovata per name='{publication_name}'"
            )

        if publication_name == "retro-gamer-1":
            suffix = "00000052001001"
        else:
            suffix = "00000000001001"

        new_key = f"{pub_id}{old_key}{suffix}"

        cur.execute("""
            UPDATE fileworkflow
            SET key = ?
            WHERE rowid = ?
        """, (new_key, rowid))

    print("Ricreo indice UNIQUE (publication_name, key)...")
    cur.execute("""
        DROP INDEX IF EXISTS fileworkflow_publication_name_date
    """)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        fileworkflow_publication_name_key
        ON fileworkflow (publication_name, key)
    """)

    conn.commit()
    conn.close()
    print("Migrazione completata con successo.")

if __name__ == "__main__":
    migrate()
