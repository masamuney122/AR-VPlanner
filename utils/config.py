"""
Konfigürasyon yönetimi
"""
import yaml
import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını proje kök dizininden yükle
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / '.env'
print(f"[Config] .env yolu: {_env_path} (mevcut: {_env_path.exists()})")
_loaded = load_dotenv(dotenv_path=str(_env_path), override=True)
print(f"[Config] load_dotenv sonuç: {_loaded}")
_gkey = os.getenv('GOOGLE_API_KEY', '')
print(f"[Config] GOOGLE_API_KEY env: {'VAR (' + _gkey[:8] + '...)' if _gkey else 'YOK'}")


class Config:
    """Konfigürasyon sınıfı"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = str(_project_root / 'config.yaml')
        self.config_path = config_path
        self._load_config()
        self._load_env_vars()
    
    def _load_config(self):
        """YAML konfigürasyon dosyasını yükle"""
        config_file = Path(self.config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}
    
    def _load_env_vars(self):
        """Ortam değişkenlerini yükle"""
        # Google API key
        if 'api' in self.config:
            google_key = os.getenv('GOOGLE_API_KEY', '')
            if google_key:
                self.config['api']['google_api_key'] = google_key
    
    def get(self, key: str, default=None):
        """Konfigürasyon değerini al"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value if value is not None else default


# Global konfigürasyon instance
config = Config()




