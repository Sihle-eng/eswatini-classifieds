
from app import db
from datetime import datetime
from flask_login import UserMixin

class User(db.Model, UserMixin):
    """Base user table for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)  # We'll hash passwords
    user_type = db.Column(db.String(20), nullable=False)  # 'business' or 'client'
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    business_profile = db.relationship('BusinessProfile', backref='user', uselist=False)
    client_profile = db.relationship('ClientProfile', backref='user', uselist=False)
    
    def __repr__(self):
        return f'<User {self.email} ({self.user_type})>'

class BusinessProfile(db.Model):
    """Additional details for business accounts"""
    __tablename__ = 'business_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    company_name = db.Column(db.String(200), nullable=False)
    registration_number = db.Column(db.String(50))  # Eswatini Business Reg Number
    address = db.Column(db.String(300))
    city = db.Column(db.String(50))  # Mbabane, Manzini, etc.
    phone_number = db.Column(db.String(20))
    logo_url = db.Column(db.String(500))
    is_subscribed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    postings = db.relationship('Posting', backref='business', lazy=True)
    
    def __repr__(self):
        return f'<Business {self.company_name}>'

class ClientProfile(db.Model):
    """Additional details for job seeker/general user accounts"""
    __tablename__ = 'client_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    phone_number = db.Column(db.String(20))  # For MoMo payments
    preferred_city = db.Column(db.String(50))  # Tailored content
    skills_interests = db.Column(db.Text)  # JSON string or comma-separated
    resume_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Client {self.full_name}>'

class Posting(db.Model):
    """Job ads and general classifieds"""
    __tablename__ = 'postings'
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business_profiles.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 'employment', 'motors', 'property', 'services', 'general'
    salary_price = db.Column(db.String(100))
    location_city = db.Column(db.String(50))  # Eswatini city
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    payment_plan = db.Column(db.String(20))  # '7days', '30days', 'featured'
    views_count = db.Column(db.Integer, default=0)
    image_filename = db.Column(db.String(200), nullable=True)
    
    def __repr__(self):
        return f'<Posting {self.title}>'
class PostingImage(db.Model):
    """Multiple images for each posting"""
    __tablename__ = 'posting_images'
    
    id = db.Column(db.Integer, primary_key=True)
    posting_id = db.Column(db.Integer, db.ForeignKey('postings.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    is_primary = db.Column(db.Boolean, default=False)  # Main image shown in listings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    posting = db.relationship('Posting', backref=db.backref('images', lazy=True, cascade='all, delete-orphan'))
    
    def __repr__(self):
        return f'<PostingImage {self.filename}>'

class Transaction(db.Model):
    """Payment records for ads"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    posting_id = db.Column(db.Integer, db.ForeignKey('postings.id'))
    payer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='SZL')
    payment_method = db.Column(db.String(30))  # 'mtn_momo', 'bank_transfer', 'card'
    payment_status = db.Column(db.String(20), default='pending')  # 'pending', 'success', 'failed'
    momo_reference = db.Column(db.String(100))
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transaction {self.id} - {self.amount} {self.currency}>'

class SavedAd(db.Model):
    """Clients can save ads they're interested in"""
    __tablename__ = 'saved_ads'
    
    id = db.Column(db.Integer, primary_key=True)
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    posting_id = db.Column(db.Integer, db.ForeignKey('postings.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate saves
    __table_args__ = (db.UniqueConstraint('client_user_id', 'posting_id', name='unique_save'),)
    
    def __repr__(self):
        return f'<SavedAd User:{self.client_user_id} Post:{self.posting_id}>'

class Report(db.Model):
    """User reports for inappropriate ads"""
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    posting_id = db.Column(db.Integer, db.ForeignKey('postings.id'), nullable=False)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Can be anonymous
    reason = db.Column(db.String(50), nullable=False)
    details = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    posting = db.relationship('Posting', backref='reports')
    
    def __repr__(self):
        return f'<Report #{self.id} - Ad #{self.posting_id}>'

class AdView(db.Model):
    """Track unique ad views per IP per day"""
    __tablename__ = 'ad_views'
    
    id = db.Column(db.Integer, primary_key=True)
    posting_id = db.Column(db.Integer, db.ForeignKey('postings.id'), nullable=False)
    viewer_ip = db.Column(db.String(50), nullable=False)
    viewer_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AdView Ad:{self.posting_id} IP:{self.viewer_ip}>'

class DeletionLog(db.Model):
    """Track account deletions and reasons"""
    __tablename__ = 'deletion_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), nullable=False)
    user_name = db.Column(db.String(200))
    user_type = db.Column(db.String(20))
    reason = db.Column(db.String(50))
    feedback = db.Column(db.Text)
    deleted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DeletionLog {self.user_email}>'

class ClientPreference(db.Model):
    __tablename__ = 'client_preferences'
    id = db.Column(db.Integer, primary_key=True)
    client_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    receive_daily_updates = db.Column(db.Boolean, default=False)
    preferred_categories = db.Column(db.Text, default='')  # comma-separated: 'employment,motors'
    preferred_cities = db.Column(db.Text, default='')      # comma-separated
    last_digest_sent = db.Column(db.DateTime, nullable=True)

    client = db.relationship('User', backref='preferences', uselist=False)