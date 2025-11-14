"""
SQLAlchemy ORM Models for PriceScout
Version: 1.0.0
Date: November 13, 2025

This module defines database models using SQLAlchemy ORM.
Supports both SQLite (local development) and PostgreSQL (production).

Usage:
    from app.db_models import Company, User, Showing, Price
    from app.db_session import get_session
    
    with get_session() as session:
        users = session.query(User).filter_by(role='admin').all()
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, 
    DateTime, Date, Text, ForeignKey, CheckConstraint, UniqueConstraint,
    Index, Numeric, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB, INET
from datetime import datetime
import json

Base = declarative_base()


# ============================================================================
# CORE TABLES: Multi-tenancy and User Management
# ============================================================================

class Company(Base):
    """Multi-tenant companies with isolated data access"""
    __tablename__ = 'companies'
    
    company_id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    settings = Column(Text, default='{}')  # JSON string for SQLite, JSONB for PostgreSQL
    
    # Relationships
    users = relationship("User", back_populates="company", foreign_keys="User.company_id")
    scrape_runs = relationship("ScrapeRun", back_populates="company", cascade="all, delete-orphan")
    showings = relationship("Showing", back_populates="company", cascade="all, delete-orphan")
    prices = relationship("Price", back_populates="company", cascade="all, delete-orphan")
    films = relationship("Film", back_populates="company", cascade="all, delete-orphan")
    operating_hours = relationship("OperatingHours", back_populates="company", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("length(company_name) > 0", name='company_name_not_empty'),
        Index('idx_companies_active', 'is_active'),
        Index('idx_companies_name', 'company_name'),
    )
    
    def __repr__(self):
        return f"<Company(id={self.company_id}, name='{self.company_name}')>"
    
    @property
    def settings_dict(self):
        """Parse settings JSON string to dict"""
        try:
            return json.loads(self.settings) if isinstance(self.settings, str) else self.settings
        except:
            return {}
    
    @settings_dict.setter
    def settings_dict(self, value):
        """Set settings from dict"""
        self.settings = json.dumps(value)


class User(Base):
    """Application users with RBAC (admin/manager/user roles)"""
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='user')
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='SET NULL'))
    default_company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='SET NULL'))
    home_location_type = Column(String(50))  # 'director', 'market', or 'theater'
    home_location_value = Column(String(255))
    allowed_modes = Column(Text, default='[]')  # JSON array of sidebar modes
    is_admin = Column(Boolean, default=False)
    must_change_password = Column(Boolean, default=False)
    reset_code = Column(String(10))
    reset_code_expiry = Column(BigInteger)
    reset_attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    default_company = relationship("Company", foreign_keys=[default_company_id])
    scrape_runs = relationship("ScrapeRun", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")
    
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'manager', 'user')", name='valid_role'),
        CheckConstraint(
            "home_location_type IS NULL OR home_location_type IN ('director', 'market', 'theater')",
            name='valid_home_location'
        ),
        Index('idx_users_username', 'username'),
        Index('idx_users_company', 'company_id'),
        Index('idx_users_role', 'role'),
        Index('idx_users_active', 'is_active'),
    )
    
    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}', role='{self.role}')>"
    
    @property
    def allowed_modes_list(self):
        """Parse allowed_modes JSON to list"""
        try:
            return json.loads(self.allowed_modes) if isinstance(self.allowed_modes, str) else self.allowed_modes
        except:
            return []
    
    @allowed_modes_list.setter
    def allowed_modes_list(self, value):
        """Set allowed_modes from list"""
        self.allowed_modes = json.dumps(value)


class AuditLog(Base):
    """Security audit trail for compliance and debugging"""
    __tablename__ = 'audit_log'
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'))
    username = Column(String(100))
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='SET NULL'))
    event_type = Column(String(100), nullable=False)  # 'login', 'logout', 'data_access', etc.
    event_category = Column(String(50), nullable=False)  # 'authentication', 'authorization', 'data', 'system'
    severity = Column(String(20), default='info')  # 'info', 'warning', 'error', 'critical'
    details = Column(Text)  # JSON string
    ip_address = Column(String(45))  # IPv6-compatible
    user_agent = Column(Text)
    session_id = Column(String(255))
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    __table_args__ = (
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_user', 'user_id'),
        Index('idx_audit_company', 'company_id'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_severity', 'severity'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.log_id}, type='{self.event_type}', user='{self.username}')>"


# ============================================================================
# PRICING DATA TABLES: Scraped theater and film information
# ============================================================================

class ScrapeRun(Base):
    """Data collection sessions tracking"""
    __tablename__ = 'scrape_runs'
    
    run_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    run_timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    mode = Column(String(100), nullable=False)  # 'market', 'operating_hours', 'compsnipe', etc.
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'))
    status = Column(String(50), default='completed')  # 'running', 'completed', 'failed'
    records_scraped = Column(Integer, default=0)
    error_message = Column(Text)
    
    # Relationships
    company = relationship("Company", back_populates="scrape_runs")
    user = relationship("User", back_populates="scrape_runs")
    prices = relationship("Price", back_populates="scrape_run")
    operating_hours = relationship("OperatingHours", back_populates="scrape_run")
    
    __table_args__ = (
        Index('idx_scrape_runs_company', 'company_id'),
        Index('idx_scrape_runs_timestamp', 'run_timestamp'),
        Index('idx_scrape_runs_mode', 'mode'),
    )
    
    def __repr__(self):
        return f"<ScrapeRun(id={self.run_id}, mode='{self.mode}', status='{self.status}')>"


class Showing(Base):
    """Theater screening schedules with pricing"""
    __tablename__ = 'showings'
    
    showing_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    play_date = Column(Date, nullable=False, index=True)
    theater_name = Column(String(255), nullable=False)
    film_title = Column(String(500), nullable=False)
    showtime = Column(String(20), nullable=False)
    format = Column(String(100))  # '2D', '3D', 'IMAX', 'Dolby', etc.
    daypart = Column(String(50))  # 'matinee', 'evening', 'late_night'
    is_plf = Column(Boolean, default=False)  # Premium Large Format
    ticket_url = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="showings")
    prices = relationship("Price", back_populates="showing", cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('company_id', 'play_date', 'theater_name', 'film_title', 'showtime', 'format',
                        name='unique_showing'),
        Index('idx_showings_company', 'company_id'),
        Index('idx_showings_theater_date', 'company_id', 'theater_name', 'play_date'),
        Index('idx_showings_film', 'company_id', 'film_title'),
        Index('idx_showings_date', 'play_date'),
    )
    
    def __repr__(self):
        return f"<Showing(id={self.showing_id}, theater='{self.theater_name}', film='{self.film_title}')>"


class Price(Base):
    """Ticket pricing data by type (Adult/Senior/Child/etc)"""
    __tablename__ = 'prices'
    
    price_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    run_id = Column(Integer, ForeignKey('scrape_runs.run_id', ondelete='SET NULL'))
    showing_id = Column(Integer, ForeignKey('showings.showing_id', ondelete='CASCADE'))
    ticket_type = Column(String(100), nullable=False)  # 'Adult', 'Senior', 'Child', etc.
    price = Column(Numeric(6, 2), nullable=False)
    capacity = Column(String(50))  # Optional theater capacity info
    play_date = Column(Date)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="prices")
    scrape_run = relationship("ScrapeRun", back_populates="prices")
    showing = relationship("Showing", back_populates="prices")
    
    __table_args__ = (
        CheckConstraint('price >= 0', name='price_positive'),
        Index('idx_prices_company', 'company_id'),
        Index('idx_prices_run', 'run_id'),
        Index('idx_prices_showing', 'showing_id'),
        Index('idx_prices_date', 'play_date'),
    )
    
    def __repr__(self):
        return f"<Price(id={self.price_id}, type='{self.ticket_type}', price={self.price})>"


class Film(Base):
    """Movie metadata from OMDB/IMDB enrichment"""
    __tablename__ = 'films'
    
    film_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    film_title = Column(String(500), nullable=False)
    imdb_id = Column(String(20), index=True)
    genre = Column(String(255))
    mpaa_rating = Column(String(20))
    director = Column(String(500))
    actors = Column(Text)
    plot = Column(Text)
    poster_url = Column(Text)
    metascore = Column(Integer)
    imdb_rating = Column(Numeric(3, 1))
    release_date = Column(String(50), index=True)
    domestic_gross = Column(BigInteger)
    runtime = Column(String(50))
    opening_weekend_domestic = Column(BigInteger)
    last_omdb_update = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="films")
    
    __table_args__ = (
        UniqueConstraint('company_id', 'film_title', name='unique_film_per_company'),
        Index('idx_films_company', 'company_id'),
        Index('idx_films_title', 'company_id', 'film_title'),
        Index('idx_films_imdb', 'imdb_id'),
        Index('idx_films_release_date', 'release_date'),
    )
    
    def __repr__(self):
        return f"<Film(id={self.film_id}, title='{self.film_title}', imdb='{self.imdb_id}')>"


class OperatingHours(Base):
    """Theater daily operating schedules"""
    __tablename__ = 'operating_hours'
    
    operating_hours_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    run_id = Column(Integer, ForeignKey('scrape_runs.run_id', ondelete='SET NULL'))
    market = Column(String(255))
    theater_name = Column(String(255), nullable=False)
    scrape_date = Column(Date, nullable=False)
    open_time = Column(String(20))
    close_time = Column(String(20))
    duration_hours = Column(Numeric(5, 2))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    company = relationship("Company", back_populates="operating_hours")
    scrape_run = relationship("ScrapeRun", back_populates="operating_hours")
    
    __table_args__ = (
        Index('idx_operating_hours_company', 'company_id'),
        Index('idx_operating_hours_theater_date', 'company_id', 'theater_name', 'scrape_date'),
        Index('idx_operating_hours_market', 'company_id', 'market'),
    )
    
    def __repr__(self):
        return f"<OperatingHours(id={self.operating_hours_id}, theater='{self.theater_name}')>"


# ============================================================================
# REFERENCE AND ERROR TRACKING TABLES
# ============================================================================

class UnmatchedFilm(Base):
    """Films that failed OMDB matching (needs review)"""
    __tablename__ = 'unmatched_films'
    
    unmatched_film_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    film_title = Column(String(500), nullable=False, index=True)
    first_seen = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    occurrence_count = Column(Integer, default=1)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'film_title', name='unique_unmatched_film'),
        Index('idx_unmatched_films_company', 'company_id'),
        Index('idx_unmatched_films_title', 'film_title'),
    )
    
    def __repr__(self):
        return f"<UnmatchedFilm(id={self.unmatched_film_id}, title='{self.film_title}', count={self.occurrence_count})>"


class IgnoredFilm(Base):
    """Films intentionally excluded from processing"""
    __tablename__ = 'ignored_films'
    
    ignored_film_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    film_title = Column(String(500), nullable=False)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.user_id', ondelete='SET NULL'))
    
    __table_args__ = (
        UniqueConstraint('company_id', 'film_title', name='unique_ignored_film'),
        Index('idx_ignored_films_company', 'company_id'),
    )
    
    def __repr__(self):
        return f"<IgnoredFilm(id={self.ignored_film_id}, title='{self.film_title}')>"


class UnmatchedTicketType(Base):
    """Unparseable ticket descriptions (needs review)"""
    __tablename__ = 'unmatched_ticket_types'
    
    unmatched_ticket_id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.company_id', ondelete='CASCADE'), nullable=False)
    original_description = Column(Text)
    unmatched_part = Column(String(255))
    first_seen = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    theater_name = Column(String(255))
    film_title = Column(String(500))
    showtime = Column(String(20))
    format = Column(String(100))
    play_date = Column(Date)
    occurrence_count = Column(Integer, default=1)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'unmatched_part', 'theater_name', 'film_title', 'play_date',
                        name='unique_unmatched_ticket'),
        Index('idx_unmatched_tickets_company', 'company_id'),
        Index('idx_unmatched_tickets_theater', 'company_id', 'theater_name'),
    )
    
    def __repr__(self):
        return f"<UnmatchedTicketType(id={self.unmatched_ticket_id}, part='{self.unmatched_part}')>"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_table_classes():
    """Return all ORM model classes for introspection"""
    return {
        'Company': Company,
        'User': User,
        'AuditLog': AuditLog,
        'ScrapeRun': ScrapeRun,
        'Showing': Showing,
        'Price': Price,
        'Film': Film,
        'OperatingHours': OperatingHours,
        'UnmatchedFilm': UnmatchedFilm,
        'IgnoredFilm': IgnoredFilm,
        'UnmatchedTicketType': UnmatchedTicketType,
    }


def create_all_tables(engine):
    """Create all tables in the database (for initial setup)"""
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """Drop all tables in the database (for testing/cleanup)"""
    Base.metadata.drop_all(engine)
