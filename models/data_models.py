"""
Veri modelleri - Proje genelinde kullanılan veri yapıları
Itinerary (rota) tabanlı seyahat planlama sistemi
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class UserPreferences:
    """Kullanıcı tercihleri"""
    interests: List[str]
    budget: float
    start_date: datetime
    end_date: datetime
    location: str  # Tek şehir
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    """Kanıt veri yapısı"""
    content: str
    source: str
    relevance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Place:
    """Google Places'tan gelen yer bilgisi"""
    name: str
    place_id: str
    address: str
    lat: float
    lng: float
    rating: float
    category: str
    price_level: int  # 0-4
    description: str
    duration_minutes: int  # Tahmini ziyaret süresi
    estimated_cost: float  # Tahmini maliyet (TL)
    photo_ref: str = ''
    opening_hours: List[str] = field(default_factory=list)
    types: List[str] = field(default_factory=list)
    user_ratings_total: int = 0


@dataclass
class TransportLeg:
    """İki nokta arası ulaşım bilgisi"""
    origin_name: str
    destination_name: str
    distance_text: str
    duration_text: str
    duration_minutes: int
    mode: str = 'driving'  # driving, walking, transit
    estimated_cost: float = 0.0


@dataclass
class DayPlan:
    """Tek bir günün planı"""
    day_number: int
    date: str
    places: List[Place]  # Sıralı ziyaret noktaları
    transport_legs: List[TransportLeg]  # Yerler arası ulaşım
    meals_cost: float  # Günlük yemek maliyeti
    transport_cost: float  # Günlük ulaşım maliyeti
    activities_cost: float  # Giriş ücretleri vs.
    day_total: float  # Günlük toplam


@dataclass
class Accommodation:
    """Konaklama bilgisi"""
    name: str
    place_id: str
    address: str
    lat: float
    lng: float
    rating: float
    price_per_night: float
    total_nights: int
    total_cost: float
    photo_ref: str = ''


@dataclass
class BudgetBreakdown:
    """Bütçe dağılımı"""
    accommodation: float
    activities: float
    food: float
    transport: float
    extras: float  # Tampon/ekstra masraflar
    total: float
    remaining: float  # Kalan bütçe
    user_budget: float


@dataclass
class Itinerary:
    """Tam rota/gezi planı"""
    city: str
    days: List[DayPlan]
    accommodation: Optional[Accommodation]
    budget: BudgetBreakdown
    total_days: int
    explanation: str = ''
    verified: bool = False
    verification_details: Dict[str, Any] = field(default_factory=dict)
    optimization_score: float = 0.0


# Eski uyumluluk için Activity ve TravelPlan (orchestrator tarafından kullanılıyor)
@dataclass
class Activity:
    """Etkinlik veri yapısı (eski uyumluluk)"""
    name: str
    description: str
    location: str
    duration: int  # dakika
    cost: float
    category: str
    evidence: List[Evidence] = field(default_factory=list)
    verification_score: Optional[float] = None


@dataclass
class TravelPlan:
    """Seyahat planı (eski uyumluluk)"""
    activities: List[Activity]
    total_cost: float
    total_duration: int
    optimization_score: float
    explanation: str
    verified: bool = False
    verification_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Ajan yanıt veri yapısı"""
    success: bool
    data: Any
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
