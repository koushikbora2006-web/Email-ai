import re
import math
from collections import Counter
from database import get_db

class RAGService:
    def __init__(self):
        pass

    def chunk_text(self, text, chunk_size=400, overlap=50):
        """Splits large text into overlapping chunks for indexing."""
        words = text.split()
        if not words:
            return []

        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += (chunk_size - overlap)
        return chunks

    def add_document(self, user_email, filename, file_type, text_content):
        """Save document and split chunks into database."""
        chunks = self.chunk_text(text_content)
        chunk_count = len(chunks) if chunks else 1

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO rag_documents (user_email, filename, file_type, content, chunk_count) VALUES (?, ?, ?, ?, ?)',
            (user_email, filename, file_type, text_content, chunk_count)
        )
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "id": doc_id,
            "filename": filename,
            "file_type": file_type,
            "chunk_count": chunk_count,
            "length": len(text_content)
        }

    def retrieve_context(self, user_email, query, top_k=3):
        """Search uploaded knowledge base documents for relevant context matching query."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, filename, content FROM rag_documents WHERE user_email = ?', (user_email,))
        docs = cursor.fetchall()
        conn.close()

        if not docs:
            return ""

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return ""

        all_chunks = []
        for doc in docs:
            chunks = self.chunk_text(doc['content'])
            for chunk in chunks:
                all_chunks.append({
                    "filename": doc['filename'],
                    "text": chunk
                })

        # Score chunks using term frequency overlap / TF-IDF similarity
        scored_chunks = []
        for item in all_chunks:
            chunk_tokens = self._tokenize(item['text'])
            score = self._compute_similarity(query_tokens, chunk_tokens)
            if score > 0:
                scored_chunks.append((score, item))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_matches = [item['text'] for score, item in scored_chunks[:top_k]]

        if top_matches:
            return "\n\n".join(top_matches)
        
        # Fallback to taking snippet from most recent document if no exact keyword match
        return docs[-1]['content'][:500]

    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def _compute_similarity(self, tokens1, tokens2):
        c1 = Counter(tokens1)
        c2 = Counter(tokens2)
        intersection = set(c1.keys()) & set(c2.keys())
        numerator = sum(c1[w] * c2[w] for w in intersection)
        
        sum1 = sum(c1[w] ** 2 for w in c1.keys())
        sum2 = sum(c2[w] ** 2 for w in c2.keys())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0
        return float(numerator) / denominator
