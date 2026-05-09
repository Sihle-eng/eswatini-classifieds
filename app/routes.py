from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.models import User, BusinessProfile, ClientProfile, Posting, Transaction, SavedAd, Report, PostingImage, AdView
from datetime import datetime, timedelta
from app.email_utils import (
    send_welcome_email,
    send_terms_agreement,
    send_ad_posted_confirmation,
    send_contact_inquiry,
    send_payment_confirmation
)
from app.services.momo_service import MTNMoMoService
from app.services.dodo_service import DodoPaymentsService

import os
import uuid

main = Blueprint('main', __name__)

# ============================================
# HELPER FUNCTIONS FOR FILE UPLOAD
# ============================================
def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return filename"""
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None
def save_multiple_images(files, posting_id, primary_index=0):
    """Save multiple images and associate with posting"""
    saved_count = 0
    for i, file in enumerate(files):
        if file and file.filename != '' and saved_count < 10:  # Max 10 images
            filename = save_uploaded_file(file)
            if filename:
                from app.models import PostingImage
                image = PostingImage(
                    posting_id=posting_id,
                    filename=filename,
                    is_primary=(i == primary_index)  # First image is primary
                )
                db.session.add(image)
                saved_count += 1
    db.session.commit()
    return saved_count

# ============================================
# PUBLIC ROUTES (No Login Required)
# ============================================
@main.route('/')
def home():
    # Get filter parameters from URL
    category = request.args.get('category', '')
    city = request.args.get('city', '')
    
    # Base query - only active and non-expired ads
    from datetime import datetime
    query = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at > datetime.utcnow()
    )
    
    # Apply filters if provided
    if category:
        query = query.filter(Posting.category == category)
    if city:
        query = query.filter(Posting.location_city == city)
    
    # Get recent ads (latest 12)
    recent_ads = query.order_by(Posting.created_at.desc()).limit(12).all()
    
    #Get total active ads count
    active_count = Posting.query.filter(
         Posting.is_active == True,
         Posting.expires_at > datetime.utcnow()
    ).count()
    
    # Get featured ads (featured plan, active, not expired)
    featured_ads = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at > datetime.utcnow(),
        Posting.payment_plan == 'featured'
    ).order_by(Posting.created_at.desc()).limit(3).all()
    
    # Get counts for each category (for the category cards)
    category_counts = {}
    categories = ['employment', 'motors', 'property', 'services', 'general']
    for cat in categories:
        count = Posting.query.filter(
            Posting.is_active == True,
            Posting.expires_at > datetime.utcnow(),
            Posting.category == cat
        ).count()
        category_counts[cat] = count
    
    return render_template('index.html', 
                         recent_ads=recent_ads,
                         featured_ads=featured_ads,
                         category_counts=category_counts,
                         current_category=category,
                         current_city=city,
                         total_ads=active_count,
                         total_users=User.query.count())
@main.route('/test')
def test():
    return "Hello Eswatini! Server is working."

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        user_type = request.form.get('user_type')
        
        # ============================================
        # CHECK TERMS AGREEMENT
        # ============================================
        if not request.form.get('agree_terms'):
            flash('You must agree to the Terms & Conditions to create an account.', 'error')
            return redirect(url_for('main.register'))
        
        # Password validation
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('main.register'))
        
        if not any(c.isupper() for c in password):
            flash('Password must contain at least one uppercase letter.', 'error')
            return redirect(url_for('main.register'))
        
        if not any(c.isdigit() for c in password):
            flash('Password must contain at least one number.', 'error')
            return redirect(url_for('main.register'))
        
        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('main.register'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please login.', 'error')
            return redirect(url_for('main.register'))
        
        # Create new user
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
            email=email,
            password_hash=hashed_password,
            user_type=user_type,
            is_verified=False
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # ============================================
        # GENERATE AGREEMENT DETAILS
        # ============================================
        import uuid
        from datetime import datetime
        
        agreement_id = f"AGR-{uuid.uuid4().hex[:8].upper()}"
        ip_address = request.remote_addr
        date_signed = datetime.utcnow().strftime('%d %B %Y')
        
        # Create profile based on user type
        if user_type == 'business':
            business_profile = BusinessProfile(
                user_id=new_user.id,
                company_name=email.split('@')[0],
                city='Mbabane'
            )
            db.session.add(business_profile)
            db.session.commit()
            
            name = business_profile.company_name
            
            # ============================================
            # SEND EMAILS USING UTILITY FUNCTIONS
            # ============================================
            try:
                from app.email_utils import send_welcome_email, send_terms_agreement
                
                # Send welcome email
                send_welcome_email(email, user_type, name)
                
                # Send terms agreement with HTML template
                send_terms_agreement(email, user_type, name, agreement_id, ip_address)
                
                flash('📧 Welcome email and Terms & Conditions sent to your inbox!', 'info')
            except Exception as e:
                print(f"Email error (non-blocking): {e}")
            
            flash('Business account created! Please complete your profile.', 'success')
            
        else:
            client_profile = ClientProfile(
                user_id=new_user.id,
                full_name=email.split('@')[0],
                preferred_city='Mbabane'
            )
            db.session.add(client_profile)
            db.session.commit()
            
            name = client_profile.full_name
            
            # ============================================
            # SEND EMAILS USING UTILITY FUNCTIONS
            # ============================================
            try:
                from app.email_utils import send_welcome_email, send_terms_agreement
                
                # Send welcome email
                send_welcome_email(email, user_type, name)
                
                # Send terms agreement with HTML template
                send_terms_agreement(email, user_type, name, agreement_id, ip_address)
                
                flash('📧 Welcome email and Safety Guidelines sent to your inbox!', 'info')
            except Exception as e:
                print(f"Email error (non-blocking): {e}")
            
            flash('Client account created! Welcome to Eswatini Classifieds.', 'success')
        
        # Log the user in
        login_user(new_user)
        
        # Redirect to appropriate dashboard        
        admin_emails = ['admin@example.com', 'techcharities@example.com', 'eswatiniclassifieds@gmail.com']
        if email in admin_emails:
            return redirect(url_for('main.admin_dashboard'))
        elif user_type == 'business':
            return redirect(url_for('main.business_dashboard'))
        else:
            return redirect(url_for('main.client_dashboard'))

    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        
        # Check if user exists and password is correct
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('main.login'))
        
        # Log the user in
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.email}!', 'success')
        
        # Redirect to appropriate dashboard
        admin_emails = ['admin@example.com', 'techcharities@example.com', 'eswatiniclassifieds@gmail.com']
        if user.email in admin_emails:
            return redirect(url_for('main.admin_dashboard'))
        elif user.user_type == 'business':
            return redirect(url_for('main.business_dashboard'))
        else:
            return redirect(url_for('main.client_dashboard'))
    
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.home'))

# ============================================
# BUSINESS ROUTES (Login Required)
# ============================================

@main.route('/business/dashboard')
@login_required
def business_dashboard():
    if current_user.user_type != 'business':
        flash('Access denied. Business account required.', 'error')
        return redirect(url_for('main.home'))
    
    business = BusinessProfile.query.filter_by(user_id=current_user.id).first()
    
    active_count = 0
    total_views = 0
    
    if business:
        # Count active ads
        active_count = Posting.query.filter_by(business_id=business.id, is_active=True).count()
        
        # Sum all views across all ads by this business
        total_views = db.session.query(db.func.sum(Posting.views_count)).filter(
            Posting.business_id == business.id
        ).scalar() or 0
    
    return render_template('business/dashboard.html', 
                         active_count=active_count, 
                         total_views=total_views)

@main.route('/business/post-ad', methods=['GET', 'POST'])
@login_required
def post_ad():
    if current_user.user_type != 'business':
        flash('Access denied. Business account required.', 'error')
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        category = request.form.get('category')
        location_city = request.form.get('location_city')
        salary_price = request.form.get('salary_price')
        description = request.form.get('description')
        payment_plan = request.form.get('payment_plan')
        payment_method = request.form.get('payment_method')
        
        # Calculate expiration date based on plan
        from datetime import datetime, timedelta
        
        if payment_plan == '7days':
            days_to_add = 7
            amount = 50.00
        elif payment_plan == '30days':
            days_to_add = 30
            amount = 150.00
        elif payment_plan == 'featured':
            days_to_add = 14
            amount = 300.00
        else:
            days_to_add = 7
            amount = 50.00
        
        expires_at = datetime.utcnow() + timedelta(days=days_to_add)
        
        # GET BUSINESS PROFILE FIRST
        business = BusinessProfile.query.filter_by(user_id=current_user.id).first()
        
        if not business:
            flash('Please complete your business profile first.', 'error')
            return redirect(url_for('main.business_dashboard'))
        
        # CREATE THE POSTING
        new_posting = Posting(
            business_id=business.id,
            title=title,
            description=description,
            category=category,
            salary_price=salary_price,
            location_city=location_city,
            is_active=False,
            expires_at=expires_at,
            payment_plan=payment_plan
        )
        
        db.session.add(new_posting)
        db.session.flush()
        
        # HANDLE MULTIPLE IMAGE UPLOADS
        if 'images' in request.files:
            files = request.files.getlist('images')
            valid_files = [f for f in files if f.filename != '']
            
            if len(valid_files) > 10:
                flash('⚠️ Maximum 10 images allowed.', 'warning')
            
            if valid_files:
                saved_count = save_multiple_images(valid_files[:10], new_posting.id)
                
                if saved_count > 0:
                    primary_image = PostingImage.query.filter_by(
                        posting_id=new_posting.id, 
                        is_primary=True
                    ).first()
                    if primary_image:
                        new_posting.image_filename = primary_image.filename
                    
                    flash(f'📸 {saved_count} image(s) uploaded!', 'success')
        
        db.session.commit()
        
        # CREATE TRANSACTION
        transaction = Transaction(
            posting_id=new_posting.id,
            payer_user_id=current_user.id,
            amount=amount,
            currency='SZL',
            payment_method=payment_method,
            payment_status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # ============================================
        # HANDLE PAYMENT (Mock Admin Only)
        # ============================================
        if payment_method == 'mock':
            admin_emails = ['admin@example.com', 'techcharities@example.com, eswatiniclassifieds@gmail.com']
            if current_user.email not in admin_emails:
                flash('Mock payment is for admins only.', 'error')
                return redirect(url_for('main.business_dashboard'))
            
            transaction.payment_status = 'success'
            transaction.paid_at = datetime.utcnow()
            new_posting.is_active = True
            db.session.commit()
            
            try:
                send_ad_posted_confirmation(
                    current_user.email, title, new_posting.id,
                    expires_at, amount, payment_method
                )
            except Exception as e:
                print(f"Email error: {e}")
            
            flash(f'✅ Ad posted successfully! Expires {expires_at.strftime("%d %b %Y")}.', 'success')
            return redirect(url_for('main.business_dashboard'))
        
        elif payment_method == 'paypal':
            flash('💳 Redirecting to secure payment page...', 'info')
            return redirect(url_for('main.payment_instructions', posting_id=new_posting.id))
    
    # GET request - show the form
    return render_template('business/post_ad.html')

# ============================================
# CLIENT ROUTES (Login Required)
# ============================================

@main.route('/client/dashboard')
@login_required
def client_dashboard():
    if current_user.user_type != 'client':
        flash('Access denied. Client account required.', 'error')
        return redirect(url_for('main.home'))
    
    saved_count = SavedAd.query.filter_by(client_user_id=current_user.id).count()
    
    return render_template('client/dashboard.html', saved_count=saved_count)
@main.route('/client/browse')
@login_required
def browse_ads():
    # Get filter parameters
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    city = request.args.get('city', '')
    
    from datetime import datetime
    
    # Base query - active and non-expired
    query = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at > datetime.utcnow()
    )
    
    # Apply search filter
    if search:
        query = query.filter(
            (Posting.title.ilike(f'%{search}%')) | 
            (Posting.description.ilike(f'%{search}%'))
        )
    
    # Apply category filter
    if category:
        query = query.filter(Posting.category == category)
    
    # Apply city filter
    if city:
        query = query.filter(Posting.location_city == city)
    
    # Get all matching ads
    ads = query.order_by(Posting.created_at.desc()).all()
    
    # Get category counts for sidebar
    category_counts = {}
    categories = ['employment', 'motors', 'property', 'services', 'general']
    for cat in categories:
        count = Posting.query.filter(
            Posting.is_active == True,
            Posting.expires_at > datetime.utcnow(),
            Posting.category == cat
        ).count()
        category_counts[cat] = count
    
    return render_template('client/browse.html', 
                         ads=ads,
                         category_counts=category_counts,
                         search=search,
                         current_category=category,
                         current_city=city)

@main.route('/business/payment/<int:posting_id>')
@login_required
def payment_instructions(posting_id):
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    posting = Posting.query.get_or_404(posting_id)
    transaction = Transaction.query.filter_by(posting_id=posting_id).first()
    
    # Ensure the posting belongs to the current user
    if posting.business.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    return render_template('business/payment.html', posting=posting, transaction=transaction)

@main.route('/business/my-ads')
@login_required
def my_ads():
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    from datetime import datetime
    
    business = BusinessProfile.query.filter_by(user_id=current_user.id).first()
    
    if business:
        postings = Posting.query.filter_by(business_id=business.id).order_by(Posting.created_at.desc()).all()
    else:
        postings = []
    
    return render_template('business/my_ads.html', postings=postings, now=datetime.utcnow())

@main.route('/business/renew-ad/<int:posting_id>', methods=['GET', 'POST'])
@login_required
def renew_ad(posting_id):
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    posting = Posting.query.get_or_404(posting_id)
    
    # Ensure the posting belongs to the current user
    if posting.business.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        payment_plan = request.form.get('payment_plan')
        payment_method = request.form.get('payment_method')
        
        # Calculate new expiration date
        from datetime import datetime, timedelta
        
        if payment_plan == '7days':
            days_to_add = 7
            amount = 50.00
        elif payment_plan == '30days':
            days_to_add = 30
            amount = 150.00
        elif payment_plan == 'featured':
            days_to_add = 14
            amount = 300.00
        else:
            days_to_add = 7
            amount = 50.00
        
        # Update expiration
        if posting.expires_at < datetime.utcnow():
            posting.expires_at = datetime.utcnow() + timedelta(days=days_to_add)
        else:
            posting.expires_at = posting.expires_at + timedelta(days=days_to_add)
        
        posting.payment_plan = payment_plan
        posting.is_active = False
        
        # Create transaction
        transaction = Transaction(
            posting_id=posting.id,
            payer_user_id=current_user.id,
            amount=amount,
            currency='SZL',
            payment_method=payment_method,
            payment_status='pending'
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        # ============================================
        # HANDLE PAYMENT
        # ============================================
        if payment_method == 'mock':
            # Only admin can use mock
            admin_emails = ['admin@example.com', 'techcharities@example.com']
            if current_user.email not in admin_emails:
                flash('Mock payment is for admins only.', 'error')
                return redirect(url_for('main.business_dashboard'))
            
            transaction.payment_status = 'success'
            transaction.paid_at = datetime.utcnow()
            posting.is_active = True
            db.session.commit()
            flash(f'✅ Ad renewed! New expiration: {posting.expires_at.strftime("%d %b %Y")}.', 'success')
            return redirect(url_for('main.my_ads'))
        
        elif payment_method == 'paypal':
            # Redirect to PayPal payment page
            flash('🅿️ Redirecting to PayPal to complete payment...', 'info')
            return redirect(url_for('main.pay_with_paypal', posting_id=posting_id))
    
    return render_template('business/renew_ad.html', posting=posting)

@main.route('/ad/<int:posting_id>')
def view_ad(posting_id):
    from datetime import datetime
    
    posting = Posting.query.get_or_404(posting_id)

    # ============================================
    # CHECK IF USER IS AUTHENTICATED
    # ============================================
    if not current_user.is_authenticated:
        # Show limited preview for non-logged-in users
        return render_template('view_ad_preview.html',
                             posting=posting,
                             posting_id=posting_id)
    
    # ============================================
    # UNIQUE VIEW TRACKING
    # ============================================
    viewer_ip = request.remote_addr
    today = datetime.utcnow().date()
    
    # Check if this IP already viewed this ad today
    existing_view = AdView.query.filter_by(
        posting_id=posting_id,
        viewer_ip=viewer_ip
    ).filter(
        db.func.date(AdView.viewed_at) == today
    ).first()
    
    if not existing_view:
        # New unique view - create tracking record
        new_view = AdView(
            posting_id=posting_id,
            viewer_ip=viewer_ip,
            viewer_user_id=current_user.id if current_user.is_authenticated else None
        )
        db.session.add(new_view)
        
        # ONLY increment view count on unique views
        posting.views_count = (posting.views_count or 0) + 1
        db.session.commit()
    
    # Get business details
    business = BusinessProfile.query.get(posting.business_id)
    
    # Check if ad is expired
    is_expired = posting.expires_at < datetime.utcnow()
    
    # Get similar ads
    similar_ads = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at > datetime.utcnow(),
        Posting.category == posting.category,
        Posting.location_city == posting.location_city,
        Posting.id != posting.id
    ).limit(3).all()
    
    # Check if ad is saved by current user
    is_saved = False
    if current_user.is_authenticated and current_user.user_type == 'client':
        saved = SavedAd.query.filter_by(
            client_user_id=current_user.id,
            posting_id=posting_id
        ).first()
        is_saved = saved is not None
    
    return render_template('view_ad.html', 
                         posting=posting,
                         business=business,
                         is_expired=is_expired,
                         similar_ads=similar_ads,
                         is_saved=is_saved)



# ============================================
# SAVED ADS ROUTES
# ============================================

@main.route('/client/save-ad/<int:posting_id>')
@login_required
def save_ad(posting_id):
    if current_user.user_type != 'client':
        flash('Only clients can save ads.', 'error')
        return redirect(url_for('main.home'))
    
    # Check if already saved
    existing = SavedAd.query.filter_by(
        client_user_id=current_user.id, 
        posting_id=posting_id
    ).first()
    
    if not existing:
        saved = SavedAd(
            client_user_id=current_user.id,
            posting_id=posting_id
        )
        db.session.add(saved)
        db.session.commit()
        flash('Ad saved to your favorites!', 'success')
    else:
        flash('Ad already in your favorites.', 'info')
    
    return redirect(request.referrer or url_for('main.home'))

@main.route('/client/unsave-ad/<int:posting_id>')
@login_required
def unsave_ad(posting_id):
    if current_user.user_type != 'client':
        flash('Only clients can manage saved ads.', 'error')
        return redirect(url_for('main.home'))
    
    SavedAd.query.filter_by(
        client_user_id=current_user.id,
        posting_id=posting_id
    ).delete()
    db.session.commit()
    
    flash('Ad removed from favorites.', 'info')
    return redirect(request.referrer or url_for('main.home'))

@main.route('/client/saved-ads')
@login_required
def saved_ads():
    if current_user.user_type != 'client':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    from datetime import datetime
    
    # Get all saved ads for this client
    saved = db.session.query(Posting).join(
        SavedAd, SavedAd.posting_id == Posting.id
    ).filter(
        SavedAd.client_user_id == current_user.id
    ).order_by(SavedAd.saved_at.desc()).all()
    
    return render_template('client/saved_ads.html', saved_ads=saved, now=datetime.utcnow())

@main.route('/business/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_business_profile():
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    profile = BusinessProfile.query.filter_by(user_id=current_user.id).first()
    
    if request.method == 'POST':
        if not profile:
            profile = BusinessProfile(user_id=current_user.id)
            db.session.add(profile)
        
        profile.company_name = request.form.get('company_name')
        profile.registration_number = request.form.get('registration_number')
        profile.phone_number = request.form.get('phone_number')
        profile.city = request.form.get('city')
        profile.address = request.form.get('address')
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.business_dashboard'))
    
    return render_template('business/edit_profile.html', profile=profile)

# ============================================
# ADMIN ROUTES
# ============================================

def admin_required(f):
    """Decorator to require admin access"""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        admin_emails = ['admin@example.com', 'techcharities@example.com', 'eswatiniclassifieds@gmail.com']
        if current_user.email not in admin_emails:
            flash('Admin access required.', 'error')
            return redirect(url_for('main.home'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/admin')
@admin_required
def admin_dashboard():
    # Get pending transactions
    pending_transactions = Transaction.query.filter_by(payment_status='pending').order_by(Transaction.created_at.desc()).all()
    
    # Get pending reports
    pending_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(10).all()
    
    # Get stats
    total_users = User.query.count()
    total_ads = Posting.query.count()
    active_ads = Posting.query.filter_by(is_active=True).count()
    total_revenue = db.session.query(db.func.sum(Transaction.amount)).filter(Transaction.payment_status == 'success').scalar() or 0
    total_reports = Report.query.count()
    
    return render_template('admin/dashboard.html',
                         pending_transactions=pending_transactions,
                         pending_reports=pending_reports,
                         total_users=total_users,
                         total_ads=total_ads,
                         active_ads=active_ads,
                         total_revenue=total_revenue,
                         total_reports=total_reports)

@main.route('/admin/verify-payment/<int:transaction_id>')
@admin_required
def verify_payment(transaction_id):
    from datetime import datetime
    
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.payment_status = 'success'
    transaction.paid_at = datetime.utcnow()
    
    # Activate the posting
    if transaction.posting_id:
        posting = Posting.query.get(transaction.posting_id)
        if posting:
            posting.is_active = True
    
    db.session.commit()
    flash(f'Payment #{transaction_id} verified and ad activated!', 'success')
    return redirect(url_for('main.admin_dashboard'))

@main.route('/admin/reject-payment/<int:transaction_id>')
@admin_required
def reject_payment(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.payment_status = 'failed'
    db.session.commit()
    flash(f'Payment #{transaction_id} rejected.', 'info')
    return redirect(url_for('main.admin_dashboard'))

@main.route('/ad/<int:posting_id>/contact', methods=['POST'])
def contact_seller(posting_id):
    posting = Posting.query.get_or_404(posting_id)
    business = BusinessProfile.query.get(posting.business_id)
    business_user = User.query.get(business.user_id)
    
    # Get form data
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    message = request.form.get('message')
    
    # Send email using our new email utility
    try:
        
        send_contact_inquiry(
            seller_email=business_user.email,
            seller_name=business.company_name,
            buyer_name=name,
            buyer_email=email,
            buyer_phone=phone,
            message=message,
            ad_title=posting.title,
            ad_id=posting_id
        )
        
        flash('✅ Your message has been sent to the seller!', 'success')
    except Exception as e:
        print(f"Email error: {e}")
        flash('⚠️ Could not send message. Please try again later.', 'error')
    
    return redirect(url_for('main.view_ad', posting_id=posting_id))

@main.route('/ad/<int:posting_id>/report', methods=['POST'])
def report_ad(posting_id):
    posting = Posting.query.get_or_404(posting_id)
    
    reason = request.form.get('reason')
    details = request.form.get('details')
    
    # Create report
    report = Report(
        posting_id=posting_id,
        reporter_user_id=current_user.id if current_user.is_authenticated else None,
        reason=reason,
        details=details,
        status='pending'
    )
    
    db.session.add(report)
    db.session.commit()
    
    flash('Thank you for your report. Our team will review it shortly.', 'success')
    return redirect(url_for('main.view_ad', posting_id=posting_id))

@main.route('/admin/reports')
@admin_required
def admin_reports():
    status = request.args.get('status', 'pending')
    reports = Report.query.filter_by(status=status).order_by(Report.created_at.desc()).all()
    
    return render_template('admin/reports.html', reports=reports, current_status=status)

@main.route('/admin/report/<int:report_id>/review', methods=['POST'])
@admin_required
def review_report(report_id):
    report = Report.query.get_or_404(report_id)
    action = request.form.get('action')
    
    if action == 'dismiss':
        report.status = 'reviewed'
        db.session.commit()
        flash('Report dismissed.', 'info')
    
    elif action == 'remove_ad':
        # Deactivate the reported ad
        posting = Posting.query.get(report.posting_id)
        if posting:
            posting.is_active = False
        report.status = 'resolved'
        db.session.commit()
        flash('Ad has been deactivated.', 'success')
    
    elif action == 'warn_user':
        # In a real app, send warning email to ad owner
        report.status = 'resolved'
        db.session.commit()
        flash('Warning sent to ad owner.', 'success')
    
    return redirect(url_for('main.admin_reports'))

@main.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)

@main.route('/admin/user/<int:user_id>/toggle-status')
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    status = 'verified' if user.is_verified else 'unverified'
    flash(f'User {user.email} is now {status}.', 'success')
    return redirect(url_for('main.admin_users'))

@main.route('/privacy')
def privacy():
    return render_template('privacy.html')

# ============================================
# MTN MOMO CALLBACK WEBHOOK
# ============================================
@main.route('/api/momo/callback', methods=['POST'])
def momo_callback():
    """Webhook for MTN MoMo payment notifications"""
    data = request.get_json()
    
    if data:
        reference_id = data.get('externalId')
        status = data.get('status')
        
        print(f"📱 MoMo Callback Received: {reference_id} - {status}")
        
        # Find transaction by reference
        transaction = Transaction.query.filter_by(momo_reference=reference_id).first()
        
        if transaction:
            if status == 'SUCCESSFUL':
                transaction.payment_status = 'success'
                transaction.paid_at = datetime.utcnow()
                
                # Activate the posting
                posting = Posting.query.get(transaction.posting_id)
                if posting:
                    posting.is_active = True
                    print(f"✅ Ad #{posting.id} activated via MoMo callback")
                
                db.session.commit()
            elif status == 'FAILED':
                transaction.payment_status = 'failed'
                db.session.commit()
                print(f"❌ Payment failed for transaction #{transaction.id}")
    
    return '', 200

@main.route('/business/pay-with-momo/<int:posting_id>', methods=['POST'])
@login_required
def pay_with_momo(posting_id):
    """Initiate MTN MoMo payment for an ad"""
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    posting = Posting.query.get_or_404(posting_id)
    
    # Ensure the posting belongs to the current user
    if posting.business.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    phone_number = request.form.get('phone_number')
    if not phone_number:
        flash('Please enter your MTN mobile number.', 'error')
        return redirect(url_for('main.payment_instructions', posting_id=posting_id))
    
    # Clean phone number
    phone_number = phone_number.replace(' ', '').replace('-', '')
    if not phone_number.startswith('268'):
        phone_number = '268' + phone_number.lstrip('0')
    
    # Determine amount
    if posting.payment_plan == '7days':
        amount = 50.00
    elif posting.payment_plan == '30days':
        amount = 150.00
    elif posting.payment_plan == 'featured':
        amount = 300.00
    else:
        amount = 50.00
    
    # Create transaction record
    import uuid
    reference_id = str(uuid.uuid4())
    transaction = Transaction(
        posting_id=posting_id,
        payer_user_id=current_user.id,
        amount=amount,
        currency='SZL',
        payment_method='mtn_momo',
        payment_status='pending',
        momo_reference=reference_id
    )
    db.session.add(transaction)
    db.session.commit()
    
    # Call MTN MoMo API
    momo = MTNMoMoService()
    success, message, ref = momo.request_to_pay(
        amount=amount,
        phone_number=phone_number,
        reference_id=reference_id,
        message=f"Eswatini Classifieds - Ad #{posting_id}"
    )
    
    if success:
        flash(f'📱 {message}', 'info')
    else:
        flash(f'❌ Payment failed: {message}', 'error')
    
    return redirect(url_for('main.my_ads'))

@main.route('/business/momo-payment/<int:posting_id>')
@login_required
def momo_payment(posting_id):
    posting = Posting.query.get_or_404(posting_id)
    transaction = Transaction.query.filter_by(posting_id=posting_id).first()
    return render_template('business/momo_payment.html', posting=posting, transaction=transaction)

# ============================================
# DODO PAYMENTS ROUTES
# ============================================

@main.route('/business/pay-with-dodo/<int:posting_id>')
@login_required
def pay_with_dodo(posting_id):
    """Redirect to Dodo Payments checkout"""
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    dodo = DodoPaymentsService()
    if not dodo.enabled:
        flash('Dodo Payments is currently unavailable.', 'error')
        return redirect(url_for('main.payment_instructions', posting_id=posting_id))
    
    posting = Posting.query.get_or_404(posting_id)
    
    # Ensure the posting belongs to the current user
    if posting.business.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    # Determine amount based on payment plan
    if posting.payment_plan == '7days':
        amount = 50.00
    elif posting.payment_plan == '30days':
        amount = 150.00
    elif posting.payment_plan == 'featured':
        amount = 300.00
    else:
        amount = 50.00
    
    # Create transaction record
    transaction = Transaction.query.filter_by(
        posting_id=posting_id,
        payment_status='pending'
    ).first()
    
    if not transaction:
        transaction = Transaction(
            posting_id=posting_id,
            payer_user_id=current_user.id,
            amount=amount,
            currency='SZL',
            payment_method='dodo',
            payment_status='pending'
        )
        db.session.add(transaction)
        db.session.commit()
    
    # Create checkout session
    success_url = url_for('main.dodo_success', posting_id=posting_id, _external=True)
    cancel_url = url_for('main.dodo_cancel', posting_id=posting_id, _external=True)
    
    result = dodo.create_checkout_session(
        amount=amount,
        currency='SZL',
        description=f"Eswatini Classifieds - Ad #{posting_id} ({posting.payment_plan})",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            'posting_id': posting_id,
            'user_id': current_user.id,
            'transaction_id': transaction.id
        }
    )
    
    if result['success']:
        # Update transaction with Dodo session ID
        transaction.momo_reference = result.get('session_id')  # Reusing momo_reference field
        db.session.commit()
        return redirect(result['checkout_url'])
    else:
        flash(f'Payment failed: {result["error"]}', 'error')
        return redirect(url_for('main.payment_instructions', posting_id=posting_id))


@main.route('/business/dodo-success/<int:posting_id>')
@login_required
def dodo_success(posting_id):
    """Handle successful Dodo payment return"""
    flash('✅ Payment initiated! Your ad will activate once payment is confirmed.', 'info')
    return redirect(url_for('main.my_ads'))


@main.route('/business/dodo-cancel/<int:posting_id>')
@login_required
def dodo_cancel(posting_id):
    """Handle cancelled Dodo payment"""
    flash('❌ Payment was cancelled.', 'warning')
    return redirect(url_for('main.payment_instructions', posting_id=posting_id))


@main.route('/api/webhook/dodo', methods=['POST'])
def dodo_webhook():
    """Handle Dodo Payments webhook notifications"""
    dodo = DodoPaymentsService()
    
    # Get signature from headers
    signature = request.headers.get('Dodo-Signature', '')
    
    # Verify webhook signature
    if not dodo.verify_webhook_signature(request.data, signature):
        print("❌ Invalid webhook signature")
        return '', 401
    
    data = request.get_json()
    
    if not data:
        return '', 400
    
    event_type = data.get('type')
    payment_data = data.get('data', {})
    
    print(f"📦 Dodo Webhook Received: {event_type}")
    
    if event_type == 'payment.succeeded':
        # Get metadata
        metadata = payment_data.get('metadata', {})
        posting_id = metadata.get('posting_id')
        transaction_id = metadata.get('transaction_id')
        
        # Find and update transaction
        if transaction_id:
            transaction = Transaction.query.get(transaction_id)
        else:
            transaction = Transaction.query.filter_by(
                posting_id=posting_id,
                payment_method='dodo',
                payment_status='pending'
            ).first()
        
        if transaction:
            transaction.payment_status = 'success'
            transaction.paid_at = datetime.utcnow()
            
            # Activate the posting
            posting = Posting.query.get(transaction.posting_id)
            if posting:
                posting.is_active = True
                print(f"✅ Ad #{posting.id} activated via Dodo webhook")
            
            db.session.commit()
            
            # Send confirmation email
            try:
                user = User.query.get(transaction.payer_user_id)
                if user and posting:
                    send_payment_confirmation(
                        user_email=user.email,
                        ad_title=posting.title,
                        amount=float(transaction.amount),
                        payment_method='dodo',
                        transaction_id=transaction.id
                    )
            except Exception as e:
                print(f"Email error: {e}")
    
    elif event_type == 'payment.failed':
        metadata = payment_data.get('metadata', {})
        transaction_id = metadata.get('transaction_id')
        
        if transaction_id:
            transaction = Transaction.query.get(transaction_id)
            if transaction:
                transaction.payment_status = 'failed'
                db.session.commit()
                print(f"❌ Payment failed for transaction #{transaction_id}")
    
    return '', 200

@main.route('/business/pay-with-paypal/<int:posting_id>')
@login_required
def pay_with_paypal(posting_id):
    """Redirect to PayPal.me for payment - converts SZL to USD"""
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    posting = Posting.query.get_or_404(posting_id)
    
    if posting.business.user_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    # Determine amount in SZL
    if posting.payment_plan == '7days':
        amount_szl = 50
    elif posting.payment_plan == '30days':
        amount_szl = 150
    elif posting.payment_plan == 'featured':
        amount_szl = 300
    else:
        amount_szl = 50
    
    # Convert SZL to USD (approximate exchange rate)
    # 1 USD ≈ 18 SZL
    amount_usd = round(amount_szl / 18.0, 2)
    
    # Create transaction record in SZL
    transaction = Transaction(
        posting_id=posting_id,
        payer_user_id=current_user.id,
        amount=amount_szl,  # Store original SZL amount
        currency='SZL',
        payment_method='paypal',
        payment_status='pending'
    )
    db.session.add(transaction)
    db.session.commit()
    
    flash(f'🅿️ Redirecting to PayPal. Amount: ${amount_usd} USD (≈ SZL {amount_szl})', 'info')
    return redirect(f"https://paypal.me/eswatiniclassifieds/{amount_usd}")


@main.route('/business/payment-history')
@login_required
def payment_history():
    if current_user.user_type != 'business':
        flash('Access denied. Business account required.', 'error')
        return redirect(url_for('main.home'))
    
    # Get all transactions for this business user
    transactions = Transaction.query.filter_by(
        payer_user_id=current_user.id
    ).order_by(Transaction.created_at.desc()).all()
    
    # Calculate total spent
    total_spent = sum(float(t.amount) for t in transactions if t.payment_status == 'success')
    
    return render_template('business/payment_history.html', 
                         transactions=transactions,
                         total_spent=total_spent)