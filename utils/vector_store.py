"""
FAISS vektör deposu yönetimi
"""
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
from models.data_models import Evidence


class VectorStore:
    """FAISS tabanlı vektör deposu"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", dimension: int = 384):
        self.model = SentenceTransformer(model_name)
        self.dimension = dimension
        self.index = None
        self.documents = []
        self.metadata = []
    
    def build_index(self, documents: List[str], metadata: List[Dict] = None):
        """
        Vektör indeksini oluştur
        
        Args:
            documents: İndekslenecek dokümanlar
            metadata: Her doküman için metadata
        """
        if not documents:
            return
        
        # Dokümanları vektörlere dönüştür
        embeddings = self.model.encode(documents, show_progress_bar=True)
        embeddings = np.array(embeddings).astype('float32')
        
        # FAISS indeksini oluştur
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)
        
        # Dokümanları ve metadata'yı sakla
        self.documents = documents
        self.metadata = metadata if metadata else [{}] * len(documents)
    
    def search(self, query: str, top_k: int = 5) -> List[Evidence]:
        """
        Benzer dokümanları ara
        
        Args:
            query: Arama sorgusu
            top_k: Döndürülecek sonuç sayısı
        
        Returns:
            Kanıt listesi
        """
        if self.index is None or len(self.documents) == 0:
            return []
        
        # Sorguyu vektöre dönüştür
        query_embedding = self.model.encode([query])
        query_embedding = np.array(query_embedding).astype('float32')
        
        # Arama yap
        distances, indices = self.index.search(query_embedding, top_k)
        
        # Sonuçları Evidence objelerine dönüştür
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.documents):
                evidence = Evidence(
                    content=self.documents[idx],
                    source=self.metadata[idx].get('source', 'unknown'),
                    relevance_score=float(1.0 / (1.0 + distances[0][i])),  # Distance'ı score'a çevir
                    metadata=self.metadata[idx]
                )
                results.append(evidence)
        
        return results
    
    def add_documents(self, documents: List[str], metadata: List[Dict] = None):
        """Yeni dokümanlar ekle"""
        if not documents:
            return
        
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












