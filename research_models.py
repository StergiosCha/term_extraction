from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

import os

# Separate database for research protocol. Use external DB if provided in environment.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./research.db")

# Fix Heroku/Render legacy postgres:// URLs for SQLAlchemy 1.4+
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Sqlite requires check_same_thread; Postgres doesn't
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ResearchProject(Base):
    __tablename__ = "research_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    domain = Column(String)  # e.g., "Celiac Disease", "COVID-19"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    corpus_files = relationship("CorpusFile", back_populates="project")
    terms = relationship("TermCandidate", back_populates="project")

class CorpusFile(Base):
    __tablename__ = "corpus_files"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("research_projects.id"))
    filename = Column(String)
    content = Column(Text)
    cleaned_content = Column(Text)
    language = Column(String(10))  # "en" or "el"
    source_type = Column(String)  # "upload", "bootcat", "manual"
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("ResearchProject", back_populates="corpus_files")

class TermCandidate(Base):
    __tablename__ = "term_candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("research_projects.id"))
    term = Column(String(500), index=True)
    language = Column(String(10))
    model_used = Column(String)
    prompt_id = Column(String)
    frequency = Column(Integer, default=1)
    is_validated = Column(Boolean, default=False)
    extracted_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("ResearchProject", back_populates="terms")
    definitions = relationship("DefinitionExperiment", back_populates="term")

class DefinitionExperiment(Base):
    __tablename__ = "definition_experiments"
    
    id = Column(Integer, primary_key=True, index=True)
    term_id = Column(Integer, ForeignKey("term_candidates.id"))
    model_id = Column(String)
    prompt_type = Column(String)  # "zero-shot", "few-shot", "rag-enhanced", etc.
    prompt_content = Column(Text)
    definition_text = Column(Text)
    is_rag = Column(Boolean, default=False)
    rag_sources = Column(JSON)  # Store source chunks used
    
    # Validation flags
    manual_valid = Column(Boolean, nullable=True)
    manual_comment = Column(Text)
    auto_valid = Column(Boolean, nullable=True)
    auto_score = Column(Float)  # From symbolic parser
    
    generated_at = Column(DateTime, default=datetime.utcnow)
    
    term = relationship("TermCandidate", back_populates="definitions")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_research_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
