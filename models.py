from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Date, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date
import json

# Database setup
DATABASE_URL = "sqlite:///./terminology.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    tier = Column(String, default="free")
    features = Column(JSON, default=lambda: {})
    rate_limit = Column(Integer, default=20)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    daily_document_corrections = Column(Integer, default=0)
    daily_elaborate_corrections = Column(Integer, default=0)
    daily_words_used = Column(Integer, default=0)
    last_word_usage_date = Column(Date)
    last_correction_date = Column(Date)
    current_requests = Column(Integer, default=0)
    last_request_at = Column(DateTime, default=datetime.utcnow)
    
    def get_daily_word_limit(self):
        limits = {"free": 1000, "premium": 25000, "enterprise": 100000}
        return limits.get(self.tier, 1000)
    
    def get_remaining_daily_words(self):
        return max(0, self.get_daily_word_limit() - (self.daily_words_used or 0))
    
    def has_reached_daily_word_limit(self, word_count):
        return (self.daily_words_used or 0) + word_count > self.get_daily_word_limit()
    
    def use_words(self, word_count):
        today = date.today()
        if self.last_word_usage_date != today:
            self.daily_words_used = 0
        self.daily_words_used = (self.daily_words_used or 0) + word_count
        self.last_word_usage_date = today

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    session_token = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    stripe_subscription_id = Column(String)
    status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# NEW TABLES FOR FEATURES 1-9

class TranslationHistory(Base):
    __tablename__ = 'translation_history'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    source_text = Column(Text, nullable=False)
    translated_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    style = Column(String(50))
    llm_provider = Column(String(50))
    confidence_score = Column(Float)
    sources_used = Column(Integer, default=0)
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
class FavoriteTranslation(Base):
    __tablename__ = 'favorite_translations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    translation_id = Column(Integer, ForeignKey('translation_history.id'))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class CustomGlossary(Base):
    __tablename__ = 'custom_glossary'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    source_term = Column(String(500), nullable=False)
    target_term = Column(String(500), nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    context = Column(Text)
    priority = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BatchTranslation(Base):
    __tablename__ = 'batch_translations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    filename = Column(String(500))
    source_language = Column(String(10))
    target_language = Column(String(10))
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    status = Column(String(50), default='pending')
    output_file_path = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

def create_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_daily_limits(db, user, correction_type):
    pass

def get_remaining_corrections(user):
    return {"document": 5, "elaborate": 1}

def update_user_tier_features(user, tier):
    pass

def migrate_privacy_columns():
    pass