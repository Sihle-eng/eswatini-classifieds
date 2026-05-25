from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import redis
from rq import Queue 

# Load environment variables
load_dotenv()

# Create instances
db = SQLAlchemy()
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
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    
    # Login manager settings
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # ============================================
    # REDIS + RQ SETUP (kept for potential future use)
    # ============================================
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
    app.config['REDIS_URL'] = redis_url
    # Create Redis connection (will be used by workers too)
    redis_conn = redis.from_url(redis_url)
    # Create a default queue
    app.config['RQ_QUEUE'] = Queue('default', connection=redis_conn)
    # Also store the redis connection on app for potential use
    app.config['REDIS_CONN'] = redis_conn
    
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'sslmode': 'require'
    }
}
    
    # Import and register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # User loader
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables
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
    
    return app