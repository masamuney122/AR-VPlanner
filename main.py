"""
Ana uygulama dosyası
Seyahat ve Etkinlik Öneri Planlayıcısı
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env'yi en başta yükle (tüm importlardan önce)
_env_path = Path(__file__).resolve().parent / '.env'
print(f"[Startup] .env yolu: {_env_path}")
print(f"[Startup] .env mevcut: {_env_path.exists()}")
if _env_path.exists():
    load_dotenv(dotenv_path=str(_env_path), override=True)
    _key = os.getenv('GOOGLE_API_KEY', '')
    print(f"[Startup] GOOGLE_API_KEY: {'YÜKLENDI (' + _key[:10] + '...)' if _key else 'BOŞ!'}")
else:
    print("[Startup] .env dosyası bulunamadı!")

from web.app import app
from utils.config import config
from utils.vector_store import vector_store

if __name__ == '__main__':
    host = config.get('web.host', '0.0.0.0')
    port = config.get('web.port', 5000)
    debug = config.get('web.debug', True)
    
    print("=" * 60)
    print("Seyahat ve Etkinlik Öneri Planlayıcısı")
    print("Ajan Tabanlı, Erişim Destekli ve Doğrulanabilir Sistem")
    print("=" * 60)
    
    kb_dir = config.get('knowledge_base.directory', 'data/knowledge_base')
    kb_path = os.path.join(os.path.dirname(__file__), kb_dir)
    if os.path.isdir(kb_path):
        print(f"\n📚 Bilgi tabanı yükleniyor: {kb_path}")
        vector_store.load_knowledge_base(kb_path)
    else:
        print(f"\n⚠ Bilgi tabanı klasörü bulunamadı: {kb_path}")
        print("  RAG devre dışı — data/knowledge_base/ klasörüne .txt dosyaları ekleyin")
    
    print(f"\nWeb arayüzü: http://{host}:{port}")
    print(f"Debug modu: {debug}")
    print("\nUygulama başlatılıyor...\n")
    
    app.run(host=host, port=port, debug=debug)






