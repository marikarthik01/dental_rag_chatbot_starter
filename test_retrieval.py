
import chromadb

DB_DIR = "chroma_db"
COLLECTION_NAME = "dental_clinic_knowledge"

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_collection(name=COLLECTION_NAME)

print(f"Total knowledge chunks: {collection.count()}")

questions = [
    "What are the clinic opening hours?",
    "How much is the consultation fee?",
    "Can this chatbot book an appointment?",
]

for question in questions:
    print("\n" + "=" * 60)
    print(f"QUESTION: {question}")

    results = collection.query(
        query_texts=[question],
        n_results=2,
    )

    for i, document in enumerate(results["documents"][0], start=1):
        print(f"\nMATCH {i}:")
        print(document)
