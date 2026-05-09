# File: app/config.py

import os
from datetime import timedelta

class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    
    # Database
    DB_USERNAME = os.environ.get('DB_USERNAME', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'eswatini_classifieds')
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        DATABASE_URL = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Eswatini Classifieds <noreply@eswatiniclassifieds.com>')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Site
    SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5000')
    SITE_NAME = os.environ.get('SITE_NAME', 'Eswatini Classifieds')
    SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'localhost')
    
    # Admin
    ADMIN_EMAILS = os.environ.get('ADMIN_EMAILS', 'admin@example.com').split(',')
    
    # Business
    DEFAULT_CITY = os.environ.get('DEFAULT_CITY', 'Mbabane')
    CURRENCY_CODE = os.environ.get('CURRENCY_CODE', 'SZL')
    CURRENCY_SYMBOL = os.environ.get('CURRENCY_SYMBOL', 'SZL')
    
    # Payment
    BANK_NAME = os.environ.get('BANK_NAME', 'FNB Eswatini')
    BANK_ACCOUNT_NAME = os.environ.get('BANK_ACCOUNT_NAME', 'Eswatini Classifieds')
    BANK_ACCOUNT_NUMBER = os.environ.get('BANK_ACCOUNT_NUMBER', '62345678901')
    BANK_BRANCH_CODE = os.environ.get('BANK_BRANCH_CODE', '280164')
    
    # Feature Flags
    FEATURE_MOMO_PAYMENTS = os.environ.get('FEATURE_MOMO_PAYMENTS', 'false').lower() == 'true'
    FEATURE_EMAIL_NOTIFICATIONS = os.environ.get('FEATURE_EMAIL_NOTIFICATIONS', 'true').lower() == 'true'
    FEATURE_IMAGE_UPLOADS = os.environ.get('FEATURE_IMAGE_UPLOADS', 'true').lower() == 'true'
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = os.environ.get('RATE_LIMIT_REQUESTS', '200 per day')
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FLASK_ENV = 'development'


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FLASK_ENV = 'production'
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    DATABASE_URL = 'sqlite:///:memory:'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}