from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
from flask_migrate import Migrate
from sqlalchemy.pool import NullPool   
import os
import sys

# Load environment variables
load_dotenv()

# Create instances
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Load configuration
    from app.config import config
    app.config.from_object(config[config_name])
   
    # Explicitly set Brevo API key from environment into config
    app.config['BREVO_API_KEY'] = os.environ.get('BREVO_API_KEY')
    app.config['CRON_SECRET'] = os.environ.get('CRON_SECRET', 'eswatini2025daily')
    
    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # ====================================================
    # FIX: Use NullPool to avoid persistent connections
    # Each database operation gets a fresh connection,
    # which is closed immediately after use.
    # This completely prevents "max clients reached" errors.
    # ====================================================
    sslmode = 'require' if os.environ.get('RENDER') else 'disable'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'poolclass': NullPool,
        'connect_args': {'sslmode': sslmode}   
    }
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)

    # ====================================================
    # Teardown: ensure session is removed after each request
    # (Still useful with NullPool to clear local state)
    # ====================================================
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    @app.context_processor
    def inject_contractor_status():
        from app.models import Contractor
        is_contractor = False
        if current_user.is_authenticated:
            contractor = Contractor.query.filter_by(email=current_user.email, active=True).first()
            is_contractor = contractor is not None
        return dict(is_contractor=is_contractor)
    
    # Login manager settings
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # User loader
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables (temporarily disabled – tables already exist)
    with app.app_context():
        db.create_all()
    
    # Template filters
    @app.template_filter('get_user')
    def get_user_filter(user_id):
        from app.models import User
        return User.query.get(user_id)

    @app.template_filter('get_posting')
    def get_posting_filter(posting_id):
        from app.models import Posting
        return Posting.query.get(posting_id)
    
    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)
    
    # Add config to template context
    @app.context_processor
    def inject_config():
        return {
            'SITE_NAME': app.config['SITE_NAME'],
            'CURRENCY_SYMBOL': app.config['CURRENCY_SYMBOL'],
            'FEATURE_IMAGE_UPLOADS': app.config['FEATURE_IMAGE_UPLOADS'],
        }
    
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )
    
    return app