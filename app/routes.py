from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import db
from app.models import (
    BlogPost,
    ContactInquiry,
    ProductPackage,
    User,
    BusinessProfile,
    ClientProfile,
    Posting,
    Transaction,
    SavedAd,
    Report,
    PostingImage,
    AdView,
    DeletionLog,
    ClientPreference,
    Contractor,
    WeeklyReport,
    Milestone,
    Commission,
    CalendarEvent,
    Lead,
    ForumThread,
    ForumReply,
    Feedback,
    PostMedia,
)
from datetime import datetime, timedelta
from app.email_utils import (
    send_welcome_email,
    send_terms_agreement,
    send_ad_posted_confirmation,
    send_contact_inquiry,
    send_payment_confirmation,
    send_email
)
from app.services.momo_service import MTNMoMoService
from app.services.dodo_service import DodoPaymentsService
from app.tasks import send_welcome_email_job, send_terms_agreement_job
from sqlalchemy import case
from app.models import ClientPreference
from flask_mail import Message


import os
import uuid
import cloudinary.uploader

main = Blueprint('main', __name__)

# ============================================
# HELPER FUNCTIONS FOR FILE UPLOAD
# ============================================
def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Upload file to Cloudinary and return the public URL"""
    if file and allowed_file(file.filename):
        try:
            upload_result = cloudinary.uploader.upload(file)
            return upload_result['secure_url']
        except Exception as e:
            print(f"Cloudinary upload error: {e}")
            return None
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
        else:  # client
            client_profile = ClientProfile(
                user_id=new_user.id,
                full_name=email.split('@')[0],
                preferred_city='Mbabane'
            )
            db.session.add(client_profile)
            db.session.commit()
            name = client_profile.full_name
        
        # ============================================
        # SEND EMAILS SYNCHRONOUSLY (NO RQ)
        # ============================================
        from app.email_utils import send_welcome_email, send_terms_agreement
        try:
            send_welcome_email(email, user_type, name)
            send_terms_agreement(email, user_type, name, agreement_id, ip_address)
            flash('📧 Welcome email and Terms & Conditions sent!', 'info')
        except Exception as e:
            print(f"[ERROR] Failed to send registration emails: {e}")
            flash('Account created but welcome email could not be sent.', 'warning')
        
        # Log the user in
        login_user(new_user)


        contractor = Contractor.query.filter_by(email=email, active=True).first()
        if contractor:
            return redirect(url_for('main.contractor_dashboard'))
        
        # Redirect to appropriate dashboard        
        admin_emails = ['eswatiniclassifieds@gmail.com']
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

         # Check if user is a contractor and redirect to their dashboard
        contractor = Contractor.query.filter_by(email=user.email, active=True).first()
        if contractor:
            return redirect(url_for('main.contractor_dashboard'))
        
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
    
    PROMO_EMAIL = "sihlelelwewelcome@gmail.com"
    is_promo = (current_user.email == PROMO_EMAIL)
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        category = request.form.get('category')
        location_city = request.form.get('location_city')
        salary_price = request.form.get('salary_price')
        description = request.form.get('description')
        
        # For promo user, we ignore payment_plan and payment_method from form
        # or they won't exist. We'll set defaults.
        if is_promo:
            # Set a default plan (e.g., 7 days) and method 'promotional'
            payment_plan = '7days'
            payment_method = 'promotional'
            days_to_add = 7
            amount = 0.00
        else:
            payment_plan = request.form.get('payment_plan')
            payment_method = request.form.get('payment_method')
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
        
        from datetime import datetime, timedelta
        expires_at = datetime.utcnow() + timedelta(days=days_to_add)
        
        business = BusinessProfile.query.filter_by(user_id=current_user.id).first()
        if not business:
            flash('Please complete your business profile first.', 'error')
            return redirect(url_for('main.business_dashboard'))
        
        # CREATE POSTING
        new_posting = Posting(
            business_id=business.id,
            title=title,
            description=description,
            category=category,
            salary_price=salary_price,
            location_city=location_city,
            is_active=is_promo,   # True for promo, False for others
            expires_at=expires_at,
            payment_plan=payment_plan
        )
        db.session.add(new_posting)
        db.session.flush()
        
        # Handle images (same for both)
        if 'images' in request.files:
            files = request.files.getlist('images')
            valid_files = [f for f in files if f.filename != '']
            if valid_files:
                saved_count = save_multiple_images(valid_files[:10], new_posting.id)
                if saved_count > 0:
                    primary = PostingImage.query.filter_by(posting_id=new_posting.id, is_primary=True).first()
                    if primary:
                        new_posting.image_filename = primary.filename
                    flash(f'📷 {saved_count} image(s) uploaded.', 'success')
        
        db.session.commit()
        
        if is_promo:
            # Record dummy transaction
            dummy = Transaction(
                posting_id=new_posting.id,
                payer_user_id=current_user.id,
                amount=0.00,
                currency='SZL',
                payment_method='promotional',
                payment_status='success',
                paid_at=datetime.utcnow()
            )
            db.session.add(dummy)
            db.session.commit()
            flash(f'✓ Promotional ad posted. Expires {expires_at.strftime("%d %b %Y")}.', 'success')
            return redirect(url_for('main.my_ads'))
        else:
            # Normal flow: create transaction, handle payment
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
            
            if payment_method == 'mock':
                admin_emails = ['admin@example.com', 'techcharities@example.com', 'eswatiniclassifieds@gmail.com']
                if current_user.email not in admin_emails:
                    flash('Mock payment is for administrators only.', 'error')
                    return redirect(url_for('main.business_dashboard'))
                transaction.payment_status = 'success'
                transaction.paid_at = datetime.utcnow()
                new_posting.is_active = True
                db.session.commit()
                try:
                    send_ad_posted_confirmation(current_user.email, title, new_posting.id, expires_at, amount, payment_method)
                except Exception as e:
                    print(f"Email error: {e}")
                flash(f'✔ Ad posted successfully. Expires {expires_at.strftime("%d %b %Y")}.', 'success')
                return redirect(url_for('main.business_dashboard'))
            elif payment_method == 'paypal':
                flash('ℹ Redirecting to secure payment page...', 'info')
                return redirect(url_for('main.payment_instructions', posting_id=new_posting.id))
            # Add other payment methods (momo, dodo) as needed
    
    # GET request – show form
    return render_template('business/post_ad.html', is_promo=is_promo)

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

    prefs = ClientPreference.query.filter_by(client_user_id=current_user.id).first()
    
    return render_template('client/dashboard.html', saved_count=saved_count, client_prefs=prefs)

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
    rank = case(
         (Posting.payment_plan == 'featured', 1),
         (Posting.payment_plan == '30days', 2),
         (Posting.payment_plan == '7days', 3),
         else_=4
    )
    ads = query.order_by(rank, Posting.created_at.desc()).all()
    
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
        contact_inquiry = ContactInquiry(
            posting_id=posting_id,
            sender_name=name,
            sender_email=email,
            sender_phone=phone,
            message=message
        )
        db.session.add(contact_inquiry)
        db.session.commit()


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
# TEAM MANAGEMENT ROUTES (Admin & Contractor)
# ============================================

@main.route('/team')
@admin_required
def team_dashboard():
    contractors = Contractor.query.all()
    return render_template('admin/team_dashboard.html', contractors=contractors)

@main.route('/team/contractor/<int:contractor_id>')
@admin_required
def contractor_detail(contractor_id):
    contractor = Contractor.query.get_or_404(contractor_id)
    reports = WeeklyReport.query.filter_by(contractor_id=contractor_id).order_by(WeeklyReport.week_ending.desc()).all()
    milestones = Milestone.query.filter_by(contractor_id=contractor_id).all()
    commissions = Commission.query.filter_by(contractor_id=contractor_id).order_by(Commission.created_at.desc()).all()
    return render_template('admin/contractor_detail.html', contractor=contractor, reports=reports, milestones=milestones, commissions=commissions)

@main.route('/team/report', methods=['GET', 'POST'])
@login_required
def submit_report():
    # Find if current user is a contractor (by email)
    contractor = Contractor.query.filter_by(email=current_user.email).first()
    if not contractor:
        flash('You are not registered as a contractor.', 'error')
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        week_ending = request.form.get('week_ending')
        summary = request.form.get('summary')
        report = WeeklyReport(
            contractor_id=contractor.id,
            week_ending=datetime.strptime(week_ending, '%Y-%m-%d').date(),
            summary=summary,
            new_business_contacts=request.form.get('new_business_contacts', 0),
            ads_posted=request.form.get('ads_posted', 0),
            engagement_notes=request.form.get('engagement_notes', ''),
            new_clients_contacted=request.form.get('new_clients_contacted', 0),
            sales_made=request.form.get('sales_made', 0),
            revenue_generated=request.form.get('revenue_generated', 0.00),
            pipeline_notes=request.form.get('pipeline_notes', '')
        )
        db.session.add(report)
        db.session.commit()
        flash('Report submitted successfully!', 'success')
        return redirect(url_for('main.submit_report'))
    return render_template('contractor/submit_report.html', contractor=contractor)

@main.route('/team/reports')
@admin_required
def all_reports():
    reports = WeeklyReport.query.order_by(WeeklyReport.week_ending.desc()).all()
    return render_template('admin/all_reports.html', reports=reports)

@main.route('/team/calendar')
@login_required
def team_calendar():
    admin_emails = ['admin@example.com', 'techcharities@example.com', 'eswatiniclassifieds@gmail.com']
    contractor = Contractor.query.filter_by(email=current_user.email, active=True).first()
    can_add_event = (current_user.email in admin_emails) or (contractor and contractor.role == 'community_manager')
    # Only show team meetings
    events = CalendarEvent.query.filter_by(calendar_type='team').order_by(CalendarEvent.event_date.asc()).all()
    return render_template('admin/calendar.html', events=events, can_add_event=can_add_event)

@main.route('/team/calendar/add', methods=['POST'])
@login_required
def add_calendar_event():
    # Allow admin or community manager to add events
    admin_emails = ['eswatiniclassifieds@gmail.com']
    contractor = Contractor.query.filter_by(email=current_user.email, active=True).first()
    if current_user.email not in admin_emails and (not contractor or contractor.role != 'community_manager'):
        flash('You do not have permission to add events.', 'error')
        return redirect(url_for('main.team_calendar'))

    title = request.form.get('title')
    description = request.form.get('description')
    event_date = request.form.get('event_date')
    event_time = request.form.get('event_time')
    event = CalendarEvent(
        title=title,
        description=description,
        event_date=datetime.strptime(event_date, '%Y-%m-%d').date(),
        event_time=datetime.strptime(event_time, '%H:%M').time() if event_time else None,
        calendar_type='team',
        created_by=current_user.id
    )
    db.session.add(event)
    db.session.commit()
    flash('Event added to calendar.', 'success')
    return redirect(url_for('main.team_calendar'))

@main.route('/team/milestones')
@admin_required
def manage_milestones():
    milestones = Milestone.query.order_by(Milestone.status.asc()).all()
    contractors = Contractor.query.all()  # <-- add this line
    return render_template('admin/milestones.html', milestones=milestones, contractors=contractors)

@main.route('/team/milestone/create', methods=['POST'])
@admin_required
def create_milestone():
    contractor_id = request.form.get('contractor_id')
    name = request.form.get('name')
    description = request.form.get('description')
    amount = request.form.get('amount')

    if not contractor_id or not name or not amount:
        flash('Contractor, name and amount are required.', 'error')
        return redirect(url_for('main.manage_milestones'))

    milestone = Milestone(
        contractor_id=contractor_id,
        name=name,
        description=description,
        amount=float(amount),
        status='pending'
    )
    db.session.add(milestone)
    db.session.commit()
    flash(f'Milestone "{name}" assigned to contractor.', 'success')
    return redirect(url_for('main.manage_milestones'))

@main.route('/team/milestone/update/<int:milestone_id>', methods=['POST'])
@admin_required
def update_milestone(milestone_id):
    milestone = Milestone.query.get_or_404(milestone_id)
    new_status = request.form.get('status')
    if new_status == 'achieved':
        milestone.achieved_at = datetime.utcnow()
    elif new_status == 'paid':
        milestone.paid_at = datetime.utcnow()
    milestone.status = new_status
    db.session.commit()
    flash('Milestone updated.', 'success')
    return redirect(url_for('main.manage_milestones'))

@main.route('/team/commissions')
@admin_required
def manage_commissions():
    commissions = Commission.query.order_by(Commission.created_at.desc()).all()
    return render_template('admin/commissions.html', commissions=commissions)

@main.route('/team/commission/pay/<int:commission_id>', methods=['POST'])
@admin_required
def mark_commission_paid(commission_id):
    commission = Commission.query.get_or_404(commission_id)
    commission.status = 'paid'
    db.session.commit()
    flash('Commission marked as paid.', 'success')
    return redirect(url_for('main.manage_commissions'))

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


@main.route('/account/delete', methods=['POST'])
@login_required
def delete_account():
    """Permanently delete user account"""
    user_id = current_user.id
    user_type = current_user.user_type
    user_email = current_user.email
    user_name = current_user.email.split('@')[0]
    
    # Get deletion reason
    reason = request.form.get('reason', 'Not specified')
    feedback = request.form.get('feedback', '')  
  
   # Log the deletion BEFORE deleting
    deletion_log = DeletionLog(
        user_email=user_email,
        user_name=user_name,
        user_type=user_type,
        reason=reason,
        feedback=feedback
    )
    db.session.add(deletion_log)
    db.session.flush()  # Save log before deleting user
    
    if user_type == 'business':
        business = BusinessProfile.query.filter_by(user_id=user_id).first()
        if business:
            user_name = business.company_name
            postings = Posting.query.filter_by(business_id=business.id).all()
            
            for posting in postings:
                Transaction.query.filter_by(posting_id=posting.id).delete()
                Report.query.filter_by(posting_id=posting.id).delete()
                SavedAd.query.filter_by(posting_id=posting.id).delete()
                AdView.query.filter_by(posting_id=posting.id).delete()
                PostingImage.query.filter_by(posting_id=posting.id).delete()
            
            Posting.query.filter_by(business_id=business.id).delete()
            db.session.delete(business)
    else:
        client = ClientProfile.query.filter_by(user_id=user_id).first()
        if client:
            user_name = client.full_name or user_name
            db.session.delete(client)
    
    # Delete remaining data
    SavedAd.query.filter_by(client_user_id=user_id).delete()
    Transaction.query.filter_by(payer_user_id=user_id).delete()
    Report.query.filter_by(reporter_user_id=user_id).delete()
    AdView.query.filter_by(viewer_user_id=user_id).delete()
    User.query.filter_by(id=user_id).delete()
    db.session.commit()
    
    # Send deletion confirmation email
    try:
        send_email(
            to=user_email,
            subject='Account Deletion Confirmation - Eswatini Classifieds',
            template_name='account_deleted',
            user_name=user_name,
            user_email=user_email,
            reason=reason,
            feedback=feedback,
            deletion_date=datetime.utcnow().strftime('%d %B %Y at %H:%M')
        )
        print(f"[SUCCESS] Deletion email sent to {user_email}")
    except Exception as e:
        print(f"[ERROR] Could not send deletion email: {e}")
    
    logout_user()
    flash('Your account has been permanently deleted. A confirmation email has been sent to your inbox.', 'info')
    return redirect(url_for('main.home'))

@main.route('/account/delete')
@login_required
def delete_account_page():
    """Show account deletion confirmation page"""
    return render_template('delete_account.html')

@main.route('/admin/deletions')
@admin_required
def admin_deletions():
    """View account deletion log"""
    deletions = DeletionLog.query.order_by(DeletionLog.deleted_at.desc()).all()
    return render_template('admin/deletions.html', deletions=deletions)

@main.route('/business/payment-history')
@login_required
def payment_history():
    if current_user.user_type != 'business':
        flash('Access denied.', 'error')
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

@main.route('/create-preferences-table')
def create_prefs_table():
    db.create_all()  # This creates any missing tables
    return "Table created (if it didn't exist)"

@main.route('/client/update-preferences', methods=['POST'])
@login_required
def update_preferences():
    if current_user.user_type != 'client':
        flash('Access denied.', 'error')
        return redirect(url_for('main.home'))
    
    prefs = ClientPreference.query.filter_by(client_user_id=current_user.id).first()
    if not prefs:
        prefs = ClientPreference(client_user_id=current_user.id)
        db.session.add(prefs)
    
    prefs.receive_daily_updates = 'receive_daily_updates' in request.form
    prefs.preferred_categories = ','.join(request.form.getlist('categories'))
    prefs.preferred_cities = ','.join(request.form.getlist('cities'))
    
    db.session.commit()
    flash('Your daily digest preferences have been saved!', 'success')
    return redirect(url_for('main.client_dashboard'))


@main.route('/cron/daily-digest/<secret>')
def daily_digest_cron(secret):
    if secret != current_app.config.get('CRON_SECRET'):
        return 'Unauthorized', 401
    
    from datetime import datetime, timedelta
    
    # Get clients who want daily updates - USING JOIN INSTEAD OF .has()
    clients = db.session.query(User).join(
        ClientPreference, User.id == ClientPreference.client_user_id
    ).filter(
        User.user_type == 'client',
        ClientPreference.receive_daily_updates == True,
        db.or_(
            ClientPreference.last_digest_sent == None,
            ClientPreference.last_digest_sent < datetime.utcnow() - timedelta(days=1)
        )
    ).all()
    
    sent_count = 0
    for client in clients:
        prefs = client.preferences  # This still works (scalar)
        categories = prefs.preferred_categories.split(',') if prefs.preferred_categories else []
        cities = prefs.preferred_cities.split(',') if prefs.preferred_cities else []
        
        since_date = prefs.last_digest_sent if prefs.last_digest_sent else (datetime.utcnow() - timedelta(days=1))
        query = Posting.query.filter(
            Posting.is_active == True,
            Posting.expires_at > datetime.utcnow(),
            Posting.created_at > since_date
        )
        if categories:
            query = query.filter(Posting.category.in_(categories))
        if cities:
            query = query.filter(Posting.location_city.in_(cities))
        
        new_ads = query.limit(20).all()
        if new_ads:
            try:
                from app.email_utils import send_email
                subject = "Your Daily Digest - New Listings in Eswatini Classifieds"
                send_email(
                    to=client.email,
                    subject=subject,
                    template_name='daily_digest',
                    client_name=client.client_profile.full_name if client.client_profile else client.email.split('@')[0],
                    ads=new_ads,
                    date=datetime.utcnow().strftime('%B %d, %Y')
                )
                prefs.last_digest_sent = datetime.utcnow()
                db.session.commit()
                sent_count += 1
            except Exception as e:
                print(f"[ERROR] Digest failed for {client.email}: {e}")
    
    return f'Processed {len(clients)} clients, sent {sent_count} digests', 200

@main.route('/admin/bulk-email', methods=['GET', 'POST'])
@admin_required
def admin_bulk_email():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        body_template = request.form.get('body', '').strip()
        recipient_type = request.form.get('recipient_type', 'all')
        specific_email = request.form.get('specific_email', '').strip()

        if not subject or not body_template:
            flash('Subject and message body are required.', 'error')
            return redirect(url_for('main.admin_bulk_email'))

        # Build the list of recipients
        recipients = []
        if recipient_type == 'specific' and specific_email:
            user = User.query.filter_by(email=specific_email).first()
            if user:
                recipients.append(user)
            else:
                flash('User not found with that email.', 'error')
                return redirect(url_for('main.admin_bulk_email'))
        else:
            query = User.query
            if recipient_type == 'business':
                query = query.filter_by(user_type='business')
            elif recipient_type == 'client':
                query = query.filter_by(user_type='client')
            recipients = query.all()

        if not recipients:
            flash('No recipients found.', 'warning')
            return redirect(url_for('main.admin_bulk_email'))

        # Send emails one by one – now uses the safe send_email() and the HTML template
        sent_count = 0
        for user in recipients:
            if user.user_type == 'business':
                biz = BusinessProfile.query.filter_by(user_id=user.id).first()
                name = biz.company_name if biz else user.email.split('@')[0]
                user_type_label = 'Business'
            else:
                client = ClientProfile.query.filter_by(user_id=user.id).first()
                name = client.full_name if (client and client.full_name) else user.email.split('@')[0]
                user_type_label = 'Client'

            # Replace placeholders in the admin's message
            personalized_subject = subject.replace('{name}', name).replace('{email}', user.email).replace('{user_type}', user_type_label)
            personalized_body = body_template.replace('{name}', name).replace('{email}', user.email).replace('{user_type}', user_type_label)

            try:
                send_email(
                    to=user.email,
                    subject=personalized_subject,
                    template_name='bulk_message',   # the new HTML template
                    user_name=name,
                    user_type=user_type_label,
                    body=personalized_body,
                    site_url=current_app.config.get('SITE_URL', 'https://eswatiniclassifieds.com'),
                    current_year=datetime.utcnow().year
                )
                sent_count += 1
            except Exception as e:
                print(f"[BULK ERROR] {user.email}: {e}")

        flash(f'Bulk email sent to {sent_count} out of {len(recipients)} recipients.', 'success')
        return redirect(url_for('main.admin_dashboard'))

    # GET request – show the form
    return render_template('admin/bulk_email.html')

@main.route('/ping')
def ping():
    return "OK", 200

@main.route('/contractor/dashboard')
@login_required
def contractor_dashboard():
    contractor = Contractor.query.filter_by(email=current_user.email).first()
    if not contractor:
        flash('You are not authorized.', 'error')
        return redirect(url_for('main.home'))
    milestones = Milestone.query.filter_by(contractor_id=contractor.id).all()
    commissions = Commission.query.filter_by(contractor_id=contractor.id).all()
    reports = WeeklyReport.query.filter_by(contractor_id=contractor.id).order_by(WeeklyReport.week_ending.desc()).all()
    return render_template('contractor/dashboard.html',
                           contractor=contractor,
                           milestones=milestones,
                           commissions=commissions,
                           reports=reports)


# ============================================
# CONTRACTOR TOOLS
# ============================================

def contractor_required(role=None):
    """Decorator to ensure user is an active contractor, optionally of a specific role."""
    from functools import wraps
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            contractor = Contractor.query.filter_by(email=current_user.email, active=True).first()
            if not contractor:
                flash('Access denied.', 'error')
                return redirect(url_for('main.home'))
            if role and contractor.role != role:
                flash('This tool is not available for your role.', 'error')
                return redirect(url_for('main.contractor_dashboard'))
            return f(contractor, *args, **kwargs)
        return decorated_function
    return decorator


# ---- Sales Rep Tools ----

@main.route('/contractor/crm', methods=['GET', 'POST'])
@contractor_required(role='sales_rep')
def contractor_crm(contractor):
    if request.method == 'POST':
        lead = Lead(
            contractor_id=contractor.id,
            name=request.form.get('name'),
            business_name=request.form.get('business_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            notes=request.form.get('notes'),
            status=request.form.get('status', 'new')
        )
        db.session.add(lead)
        db.session.commit()
        flash('Lead added successfully.', 'success')
        return redirect(url_for('main.contractor_crm'))
    leads = Lead.query.filter_by(contractor_id=contractor.id).order_by(Lead.created_at.desc()).all()
    return render_template('contractor/crm.html', leads=leads)

@main.route('/contractor/lead-capture', methods=['GET', 'POST'])
@contractor_required(role='sales_rep')
def contractor_lead_capture(contractor):
    if request.method == 'POST':
        lead = Lead(
            contractor_id=contractor.id,
            name=request.form.get('name'),
            business_name=request.form.get('business_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            notes='Captured via lead form.',
            status='new'
        )
        db.session.add(lead)
        db.session.commit()
        flash('Lead captured!', 'success')
        return redirect(url_for('main.contractor_lead_capture'))
    return render_template('contractor/lead_capture.html')

@main.route('/contractor/sales-analytics')
@contractor_required(role='sales_rep')
def contractor_sales_analytics(contractor):
    total_commissions = db.session.query(db.func.sum(Commission.amount)).filter_by(contractor_id=contractor.id, status='paid').scalar() or 0
    pending_commissions = db.session.query(db.func.sum(Commission.amount)).filter_by(contractor_id=contractor.id, status='pending').scalar() or 0
    leads_count = Lead.query.filter_by(contractor_id=contractor.id).count()
    return render_template('contractor/sales_analytics.html', total_commissions=total_commissions, pending_commissions=pending_commissions, leads_count=leads_count)

# ---- Community Manager Tools ----

@main.route('/contractor/member-directory')
@contractor_required(role='community_manager')
def contractor_member_directory(contractor):
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('contractor/member_directory.html', users=users)

@main.route('/contractor/feedback')
@contractor_required(role='community_manager')
def contractor_feedback(contractor):
    feedback_list = Feedback.query.order_by(Feedback.submitted_at.desc()).all()
    return render_template('contractor/feedback.html', feedback_list=feedback_list)

# ---- Community Manager: Discussion Forum ----
@main.route('/contractor/forum', methods=['GET', 'POST'])
@contractor_required(role='community_manager')
def contractor_forum(contractor):
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            thread = ForumThread(title=title, content=content, author_id=current_user.id)
            db.session.add(thread)
            db.session.commit()
            flash('Thread created!', 'success')
            return redirect(url_for('main.contractor_forum'))
    threads = ForumThread.query.order_by(ForumThread.created_at.desc()).all()
    return render_template('contractor/forum.html', threads=threads)

@main.route('/contractor/forum/thread/<int:thread_id>', methods=['GET', 'POST'])
@contractor_required(role='community_manager')
def contractor_forum_thread(contractor, thread_id):
    thread = ForumThread.query.get_or_404(thread_id)
    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            reply = ForumReply(thread_id=thread.id, content=content, author_id=current_user.id)
            db.session.add(reply)
            db.session.commit()
            flash('Reply posted.', 'success')
            return redirect(url_for('main.contractor_forum_thread', thread_id=thread.id))
    return render_template('contractor/forum_thread.html', thread=thread)

# ---- Community Manager: Content Hub ----
@main.route('/contractor/content-hub', methods=['GET', 'POST'])
@contractor_required(role='community_manager')
def contractor_content_hub(contractor):
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            post = BlogPost(title=title, content=content, author_id=current_user.id)
            db.session.add(post)
            db.session.commit()
            flash('Blog post published!', 'success')
            return redirect(url_for('main.contractor_content_hub'))
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('contractor/content_hub.html', posts=posts)

@main.route('/contractor/content-hub/edit/<int:post_id>', methods=['GET', 'POST'])
@contractor_required(role='community_manager')
def contractor_edit_post(contractor, post_id):
    post = BlogPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        # Update title and content
        post.title = request.form.get('title')
        post.content = request.form.get('content')
        
        # Delete selected media (checkboxes)
        delete_ids = request.form.getlist('delete_media')
        if delete_ids:
            PostMedia.query.filter(PostMedia.id.in_(delete_ids)).delete(synchronize_session=False)
            flash(f'Removed {len(delete_ids)} media file(s).', 'info')
        
        # Add new media
        if 'new_media' in request.files:
            files = request.files.getlist('new_media')
            valid = [f for f in files if f.filename != '']
            if valid:
                # Get current max order
                max_order = db.session.query(db.func.max(PostMedia.order)).filter_by(post_id=post.id).scalar() or -1
                order = max_order + 1
                for file in valid[:10]:
                    url, mime = save_content_media(file)
                    if url:
                        media = PostMedia(post_id=post.id, file_url=url, file_type=mime or file.content_type, order=order)
                        db.session.add(media)
                        order += 1
                db.session.commit()
                flash(f'Added {len(valid)} new media file(s).', 'success')
        
        db.session.commit()
        flash('Post updated!', 'success')
        return redirect(url_for('main.contractor_content_hub'))
    
    return render_template('contractor/edit_blog_post.html', post=post)

@main.route('/contractor/content-hub/delete/<int:post_id>', methods=['POST'])
@contractor_required(role='community_manager')
def delete_blog_post(contractor, post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('main.contractor_content_hub'))

# ---- Community Manager: Analytics ----
@main.route('/contractor/analytics')
@contractor_required(role='community_manager')
def contractor_analytics(contractor):
    from datetime import datetime, timedelta
    total_users = User.query.count()
    active_ads = Posting.query.filter_by(is_active=True).count()
    total_ads = Posting.query.count()
    # New users this month
    first_day = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_users_this_month = User.query.filter(User.created_at >= first_day).count()
    return render_template('contractor/analytics.html',
                         total_users=total_users,
                         active_ads=active_ads,
                         total_ads=total_ads,
                         new_users_this_month=new_users_this_month)

# ---- Sales Rep: Email Automation ----
@main.route('/contractor/email-automation', methods=['GET', 'POST'])
@contractor_required(role='sales_rep')
def contractor_email_automation(contractor):
    leads = Lead.query.filter_by(contractor_id=contractor.id).all()
    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')
        recipient_ids = request.form.getlist('recipients')
        for lead_id in recipient_ids:
            lead = Lead.query.get(int(lead_id))
            if lead and lead.email:
                try:
                    msg = Message(subject, recipients=[lead.email], body=body)
                    mail.send(msg)
                except Exception as e:
                    print(f"Email error: {e}")
        flash('Emails sent.', 'success')
        return redirect(url_for('main.contractor_email_automation'))
    return render_template('contractor/email_automation.html', leads=leads)

# ---- Sales Rep: Support Inbox (Live Chat replacement) ----
@main.route('/contractor/support-inbox')
@contractor_required(role='sales_rep')
def contractor_support_inbox(contractor):
    inquiries = ContactInquiry.query.order_by(ContactInquiry.created_at.desc()).all()
    return render_template('contractor/support_inbox.html', inquiries=inquiries)

@main.route('/blog')
def public_blog():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('blog/public_blog.html', posts=posts)

@main.route('/contractor/content-calendar', methods=['GET', 'POST'])
@contractor_required(role='community_manager')
def contractor_content_calendar(contractor):
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        event_date = request.form.get('event_date')
        event_time = request.form.get('event_time')

        event = CalendarEvent(
            title=title,
            description=description,
            event_date=datetime.strptime(event_date, '%Y-%m-%d').date(),
            event_time=datetime.strptime(event_time, '%H:%M').time() if event_time else None,
            calendar_type='content',
            created_by=current_user.id
        )
        db.session.add(event)
        db.session.commit()
        flash('Content event added!', 'success')
        return redirect(url_for('main.contractor_content_calendar'))

    # Fetch only content events (not team meetings)
    events = CalendarEvent.query.filter_by(calendar_type='content').order_by(CalendarEvent.event_date.asc()).all()
    return render_template('contractor/content_calendar.html', events=events)

@main.route('/feedback', methods=['GET', 'POST'])
def public_feedback():
    if request.method == 'POST':
        feedback = Feedback(
            satisfaction=request.form.get('satisfaction'),
            suggestions=request.form.get('suggestions')
        )
        db.session.add(feedback)
        db.session.commit()
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('main.home'))
    return render_template('feedback/public_form.html')

def save_content_media(file):
    """Upload a media file to Cloudinary and return (secure_url, mime_type)"""
    if file and file.filename != '':
        try:
            upload_result = cloudinary.uploader.upload(
                file,
                resource_type = "auto",          # detects image or video
                folder = "content_hub"           # optional: organise in Cloudinary
            )
            return upload_result['secure_url'], upload_result['resource_type']
        except Exception as e:
            print(f"Cloudinary content upload error: {e}")
            return None, None
    return None, None

@main.route('/content/create', methods=['POST'])
@login_required
def create_content_post():
    title = request.form.get('title')
    content = request.form.get('content')
    if not title or not content:
        flash('Title and content are required.', 'error')
        return redirect(url_for('main.content_hub'))
    
    # Create the blog post
    post = BlogPost(
        title=title,
        content=content,
        author_id=current_user.id
    )
    db.session.add(post)
    db.session.commit()
    
    # Handle uploaded media (if any)
    if 'media' in request.files:
        files = request.files.getlist('media')
        valid_files = [f for f in files if f.filename != '']
        if valid_files:
            order = 0
            for file in valid_files[:10]:   # max 10 files
                url, mime_type = save_content_media(file)
                if url:
                    media = PostMedia(
                        post_id=post.id,
                        file_url=url,
                        file_type=mime_type or file.content_type,
                        order=order
                    )
                    db.session.add(media)
                    order += 1
            db.session.commit()
            flash(f'{order} media file(s) uploaded.', 'success')
    
    flash('Post published successfully!', 'success')
    return redirect(url_for('main.content_hub'))

@main.route('/content-hub')
@login_required
def content_hub():
    posts = BlogPost.query.order_by(BlogPost.created_at.desc()).all()
    return render_template('content_hub.html', posts=posts)

@main.route('/contractor/content-hub/create', methods=['POST'])
@contractor_required(role='community_manager')
def contractor_create_post(contractor):
    title = request.form.get('title')
    content = request.form.get('content')
    if not title or not content:
        flash('Title and content are required.', 'error')
        return redirect(url_for('main.contractor_content_hub'))
    
    post = BlogPost(
        title=title,
        content=content,
        author_id=current_user.id   # or contractor.user_id depending on your User model
    )
    db.session.add(post)
    db.session.commit()
    
    # Handle uploaded media
    if 'media' in request.files:
        files = request.files.getlist('media')
        valid_files = [f for f in files if f.filename != '']
        if valid_files:
            order = 0
            for file in valid_files[:10]:
                url, mime_type = save_content_media(file)  # your helper from earlier
                if url:
                    media = PostMedia(
                        post_id=post.id,
                        file_url=url,
                        file_type=mime_type or file.content_type,
                        order=order
                    )
                    db.session.add(media)
                    order += 1
            db.session.commit()
            flash(f'{order} media file(s) uploaded.', 'success')
    
    flash('Post published successfully!', 'success')
    return redirect(url_for('main.contractor_content_hub'))

@main.route('/contractor/content-hub/delete/<int:post_id>', methods=['POST'])
@contractor_required(role='community_manager')
def contractor_delete_post(contractor, post_id):
    post = BlogPost.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post and all its media deleted.', 'success')
    return redirect(url_for('main.contractor_content_hub'))

# ============================================
# PRODUCT CATALOG (Sales Rep)
# ============================================

@main.route('/contractor/product-catalog')
@contractor_required(role='sales_rep')
def contractor_product_catalog(contractor):
    packages = ProductPackage.query.filter_by(is_active=True).all()
    return render_template('contractor/product_catalog.html', packages=packages)

@main.route('/contractor/product-catalog/create', methods=['POST'])
@contractor_required(role='sales_rep')
def contractor_product_create(contractor):
    name = request.form.get('name')
    price = request.form.get('price')
    features = request.form.get('features')
    if not name or not price:
        flash('Name and price are required.', 'error')
        return redirect(url_for('main.contractor_product_catalog'))
    package = ProductPackage(
        name=name,
        price=float(price),
        features=features,
        created_by=current_user.id
    )
    db.session.add(package)
    db.session.commit()
    flash(f'Package "{name}" created.', 'success')
    return redirect(url_for('main.contractor_product_catalog'))

@main.route('/contractor/product-catalog/edit/<int:package_id>', methods=['POST'])
@contractor_required(role='sales_rep')
def contractor_product_edit(contractor, package_id):
    package = ProductPackage.query.get_or_404(package_id)
    package.name = request.form.get('name')
    package.price = float(request.form.get('price'))
    package.features = request.form.get('features')
    db.session.commit()
    flash('Package updated.', 'success')
    return redirect(url_for('main.contractor_product_catalog'))

@main.route('/contractor/product-catalog/delete/<int:package_id>', methods=['POST'])
@contractor_required(role='sales_rep')
def contractor_product_delete(contractor, package_id):
    package = ProductPackage.query.get_or_404(package_id)
    db.session.delete(package)
    db.session.commit()
    flash('Package deleted.', 'success')
    return redirect(url_for('main.contractor_product_catalog'))