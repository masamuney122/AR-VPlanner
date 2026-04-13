"""
FAISS vektör deposu yönetimi
Bilgi tabanı dosyalarını yükler ve semantik arama yapar
"""
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from models.data_models import Evidence
from utils.config import config


class VectorStore:
    """FAISS tabanlı vektör deposu — bilgi tabanı RAG için"""

    def __init__(self):
        model_name = config.get(
            'models.embedding_model',
            'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
        )
        self.dimension = config.get('vector_store.dimension', 384)
        self.model: Optional[SentenceTransformer] = None
        self.index: Optional[faiss.IndexFlatL2] = None
        self.documents: List[str] = []
        self.metadata: List[Dict] = []
        self._model_name = model_name

    def _ensure_model(self):
        if self.model is None:
            print(f"📚 Embedding modeli yükleniyor: {self._model_name}")
            self.model = SentenceTransformer(self._model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            print(f"✅ Embedding modeli hazır (dim={self.dimension})")

    def load_knowledge_base(self, kb_dir: str):
        """
        data/knowledge_base/ altındaki tüm .txt dosyalarını oku,
        paragraflara böl ve FAISS'e indexle.
        """
        if not os.path.isdir(kb_dir):
            print(f"⚠ Bilgi tabanı klasörü bulunamadı: {kb_dir}")
            return

        documents: List[str] = []
        metadata: List[Dict] = []

        for filename in sorted(os.listdir(kb_dir)):
            if not filename.endswith('.txt'):
                continue

            city = os.path.splitext(filename)[0]
            filepath = os.path.join(kb_dir, filename)

            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]

            for para in paragraphs:
                if len(para) < 20:
                    continue
                documents.append(para)
                metadata.append({'city': city, 'source': filename})

        if not documents:
            print("⚠ Bilgi tabanında doküman bulunamadı")
            return

        self.build_index(documents, metadata)
        print(f"📚 Bilgi tabanı yüklendi: {len(documents)} paragraf, {len(set(m['city'] for m in metadata))} şehir")

    def build_index(self, documents: List[str], metadata: List[Dict] = None):
        """Dokümanları vektörleştir ve FAISS indeksini oluştur."""
        if not documents:
            return

        self._ensure_model()

        embeddings = self.model.encode(documents, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')

        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)

        self.documents = documents
        self.metadata = metadata if metadata else [{}] * len(documents)

    def search(self, query: str, top_k: int = 5, city_filter: str = None) -> List[Evidence]:
        """
        Semantik arama yap.

        Args:
            query: Arama sorgusu
            top_k: Döndürülecek sonuç sayısı
            city_filter: Opsiyonel şehir filtresi (sadece o şehrin paragrafları)
        """
        if self.index is None or len(self.documents) == 0:
            return []

        self._ensure_model()

        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')

        fetch_k = top_k * 3 if city_filter else top_k
        distances, indices = self.index.search(query_embedding, min(fetch_k, len(self.documents)))

        results: List[Evidence] = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(self.documents):
                continue

            meta = self.metadata[idx]

            if city_filter and meta.get('city', '').lower() != city_filter.lower():
                continue

            score = float(1.0 / (1.0 + distances[0][i]))
            results.append(Evidence(
                content=self.documents[idx],
                source=meta.get('source', 'knowledge_base'),
                relevance_score=score,
                metadata=meta
            ))

            if len(results) >= top_k:
                break

        return results

    def add_documents(self, documents: List[str], metadata: List[Dict] = None):
        """Mevcut indekse yeni dokümanlar ekle."""
        if not documents:
            return

        self._ensure_model()

        embeddings = self.model.encode(documents, show_progress_bar=False)
        embeddings = np.array(embeddings).astype('float32')

        if self.index is None:
            self.index = faiss.IndexFlatL2(self.dimension)

        self.index.add(embeddings)
        self.documents.extend(documents)

        if metadata:
            self.metadata.extend(metadata)
        else:
            self.metadata.extend([{}] * len(documents))

    @property
    def is_ready(self) -> bool:
        return self.index is not None and len(self.documents) > 0


vector_store = VectorStore()
