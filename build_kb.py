from pathlib import Path
import hashlib
import chromadb

DATA_FILE = Path("data/clinic_knowledge.md")
DB_DIR = "chroma_db"
COLLECTION_NAME = "dental_clinic_knowledge"

def split_markdown(text: str):
    # Beginner-friendly chunking: each Markdown heading begins a new chunk.
    chunks, current = [], []
    for line in text.splitlines():
        if line.startswith("#") and current:
            chunk = "\n".join(current).strip()
            if chunk:
                chunks.append(chunk)
            current = [line]
        else:
            current.append(line)
    final_chunk = "\n".join(current).strip()
    if final_chunk:
        chunks.append(final_chunk)
    return [c for c in chunks if len(c) > 20]

def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Missing knowledge file: {DATA_FILE}")

    text = DATA_FILE.read_text(encoding="utf-8")
    chunks = split_markdown(text)
    if not chunks:
        raise ValueError("No useful text chunks found in clinic_knowledge.md")

    db = chromadb.PersistentClient(path=DB_DIR)
    try:
        db.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = db.create_collection(name=COLLECTION_NAME)

    ids, metadatas = [], []
    for i, chunk in enumerate(chunks):
        digest = hashlib.sha1(chunk.encode("utf-8")).hexdigest()[:10]
        ids.append(f"clinic-{i}-{digest}")
        metadatas.append({"source": DATA_FILE.name, "chunk_number": i})

    collection.add(ids=ids, documents=chunks, metadatas=metadatas)
    print(f"Knowledge base rebuilt successfully: {len(chunks)} chunks.")
    print(f"Database location: {DB_DIR}")

if __name__ == "__main__":
    main()
