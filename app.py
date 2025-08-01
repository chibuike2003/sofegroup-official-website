
import os
import re
from flask import Flask, render_template, request, redirect, flash, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import string, random
from functools import wraps
import logging # Import logging module for app.logger

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = 'fgvbhnjhbggyt67654567899iuhyghuhytgyuhygthytghyt' # **CRITICAL: In a real app, use a more secure, environment-variable-based key.**

# --- Database Configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sofe.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- UPLOAD_FOLDER Configuration for Receipts ---
# It's good to define UPLOAD_FOLDER and ALLOWED_EXTENSIONS early and clearly.
# Removed duplicate 'UPLOAD_FOLDER' and 'ALLOWED_EXTENSIONS' definitions.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads', 'receipts')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'} # Standard file types for receipts

# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Database Initialization ---
db = SQLAlchemy(app)

# --- Flask-Login Initialization ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The route name for your login page for regular users

@login_manager.user_loader
def load_user(user_id):
    """
    This function is crucial! It tells Flask-Login how to load a user
    given their ID, which is stored in the session.
    It should query your User model to find the user.
    """
    return User.query.get(int(user_id))

# Custom decorator to restrict access to admin users
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('admin_login')) # Redirect to admin login if not authenticated
        # Check if user is an admin
        if not current_user.is_admin:
            flash('You do not have administrative access.', 'danger')
            return redirect(url_for('dashboard')) # Redirect to regular dashboard or home if not admin
        return f(*args, **kwargs)
    return decorated_function

# Custom decorator to restrict access to partner users
def partner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('partner_login')) # Redirect to partner login if not authenticated
        if not current_user.is_partner:
            flash('You do not have partner access.', 'danger')
            return redirect(url_for('dashboard')) # Redirect to regular dashboard if not a partner
        return f(*args, **kwargs)
    return decorated_function

# User model - Modified to include is_admin flag and referred_by_id
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    referral_code = db.Column(db.String(10), unique=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    bank_details = db.relationship('Bank', backref='owner', lazy=True, uselist=False)
    enrollments = db.relationship('CourseEnrollment', backref='enroller', lazy=True)

    # Store the ID of the user who referred this user
    referred_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referrer = db.relationship('User', remote_side=[id], backref='referred_users') # Relationship to referrers

    # NEW: Fields for Partner users
    is_partner = db.Column(db.Boolean, default=False)
    company_name = db.Column(db.String(150), nullable=True)
    contact_name = db.Column(db.String(150), nullable=True) # Could be same as 'name' for non-partner users, but good to have
    phone = db.Column(db.String(20), nullable=True)
    business_type = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"User('{self.name}', '{self.email}', Admin: {self.is_admin}, Partner: {self.is_partner})"


class Help(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, default=datetime.utcnow)

class Hire(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    company_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    service_interest = db.Column(db.String(100), nullable=False)
    project_details = db.Column(db.Text, nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Link to User if logged in

    def __repr__(self):
        return f"Hire('{self.full_name}', '{self.service_interest}', '{self.submission_date}')"

class Testimonial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    service_used = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 to 5
    message = db.Column(db.Text, nullable=False)
    consent_to_display = db.Column(db.Boolean, default=False)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Link to User if logged in

    def __repr__(self):
        return f"Testimonial('{self.name}', '{self.service_used}', '{self.rating}')"

class ContactInquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    submission_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Link to User if logged in

    def __repr__(self):
        return f"ContactInquiry('{self.full_name}', '{self.subject}', '{self.submission_date}')"

class Bank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    account_number = db.Column(db.String(10), nullable=False) # Assuming 10 digits as per HTML pattern
    account_type = db.Column(db.String(50), nullable=False) # Added from the form
    date_linked = db.Column(db.DateTime, nullable=False, default=db.func.current_timestamp())

    def __repr__(self):
        return f"Bank('{self.bank_name}', '{self.account_number}', User_ID: {self.user_id})"


# NEW MODEL: CourseEnrollment
class CourseEnrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    course_name = db.Column(db.String(255), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False) # Storing as float for currency
    transaction_id = db.Column(db.String(100), nullable=True)
    receipt_filename = db.Column(db.String(255), nullable=False) # Path to the uploaded receipt file
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending') # e.g., 'pending', 'approved', 'rejected'

    def __repr__(self):
        return f"Enrollment('{self.full_name}', '{self.course_name}', Status: '{self.status}')"



# Helper function for allowed file types
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Context processor to make datetime available in all templates
@app.context_processor
def inject_now():
    return {'datetime': datetime}


# Helper function to generate referral code
def generate_referral_code(length=8):
    """Generates a random alphanumeric referral code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Create database tables within the application context
with app.app_context():
    db.create_all()

# --- PUBLIC FACING ROUTES ---

@app.route('/home', methods=['GET', 'POST'])
def home():
    """Renders the home page."""
    return render_template('index.html')

@app.route('/about', methods=['GET', 'POST'])
def about():
    """Renders the about page."""
    return render_template('about.html')

@app.route('/gallery', methods=['GET', 'POST'])
def gallery():
    """Renders the gallery page."""
    return render_template('gallery.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """Handles user registration."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        # Retrieve the referral code from the form, default to empty string if not provided
        provided_referral_code = request.form.get('referral_code', '').strip()

        # Store form data to re-populate if validation fails (good UX)
        form_data = {
            'name': name,
            'email': email,
            'referral_code': provided_referral_code
        }

        # Form validation
        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template('signup.html', form_data=form_data) # Pass form data back
        
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('signup.html', form_data=form_data) # Pass form data back

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "warning")
            return render_template('signup.html', form_data=form_data) # Pass form data back

        # --- Referral Code Validation ---
        referrer_user = None
        if provided_referral_code: # Only validate if a code was actually provided
            referrer_user = User.query.filter_by(referral_code=provided_referral_code).first()
            if not referrer_user:
                flash(f"The referral code '{provided_referral_code}' is invalid. Please check it or leave it blank.", "danger")
                return render_template('signup.html', form_data=form_data) # Pass form data back
            # Optional: Prevent self-referral if current_user could somehow be the referrer (though unlikely during signup)
            # if current_user.is_authenticated and referrer_user.id == current_user.id:
            #     flash("You cannot refer yourself.", "danger")
            #     return render_template('signup.html', form_data=form_data)

        # Hash password
        hashed_password = generate_password_hash(password)

        # Generate unique referral code for the new user
        new_user_referral_code = generate_referral_code()
        while User.query.filter_by(referral_code=new_user_referral_code).first():
            new_user_referral_code = generate_referral_code()

        # Create new user (not an admin by default)
        new_user = User(name=name, email=email, password=hashed_password, referral_code=new_user_referral_code, is_admin=False)
        
        # If a valid referrer was found, you might want to link them or give credit.
        # This is where your referral logic would go. For example:
        # if referrer_user:
        #     # Example: Increment a referral count for referrer_user
        #     # referrer_user.referral_count = (referrer_user.referral_count or 0) + 1
        #     # Or create a separate referral tracking entry:
        #     # referral_entry = ReferralTracker(new_user_id=new_user.id, referrer_id=referrer_user.id)
        #     # db.session.add(referral_entry)
        #     flash(f"Account created successfully! You were referred by {referrer_user.name}. Your referral code is: {new_user_referral_code}", "success")
        # else:
        flash("Account created successfully! Your referral code is: " + new_user_referral_code, "success")


        db.session.add(new_user)
        db.session.commit()

        # You might want to log the referrer for analytics or rewards
        if referrer_user:
            # Example: Log a referral event
            print(f"User {new_user.email} was referred by {referrer_user.email} ({referrer_user.referral_code})")
            # You would typically add logic here to give the referrer credit, e.g.,
            # referrer_user.add_referral_reward()
            # db.session.add(referrer_user) # If you modified the referrer_user object
            # db.session.commit()


        return redirect(url_for('login'))

    return render_template('signup.html', form_data={}) # Pass empty form_data on GET request

    
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        # Redirect to admin dashboard if they are an admin
        if current_user.is_admin:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')

        if not email or not password:
            flash("Please fill in all fields", "danger")
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        # Check if the user is an admin trying to log in via the regular login form
        if user and user.is_admin:
            flash("Administrators should use the admin login page.", "warning")
            return redirect(url_for('admin_login'))

        # Validate user credentials
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for('login'))

        # Login successful - use Flask-Login's login_user
        login_user(user)
        flash(f"Welcome back, {user.name}!", "success")
        return redirect(url_for('dashboard'))

    return render_template('login.html')

@app.route('/dashboard')
@login_required # Requires user to be logged in
def dashboard():
    """Renders the user dashboard."""
    # current_user is provided by Flask-Login and refers to the logged-in user object
    flash('Welcome To Your Dashboard.', 'success')
    return render_template('dashboard.html', user=current_user)

@app.route('/signup-success')
@login_required # Requires user to be logged in
def signup_success():
    """Renders the signup success page."""
    return render_template('success.html', name=current_user.name, referral_code=current_user.referral_code)

@app.route('/contact-support', methods=['GET', 'POST'])
@login_required # Requires user to be logged in
def contact_support():
    """Handles user support requests."""
    user = current_user # Use current_user from Flask-Login

    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')

        if not subject or not message:
            flash("Subject and message are required.", "danger")
            return redirect(url_for('contact_support'))

        help_request = Help(
            user_id=user.id,
            name=user.name,
            email=user.email,
            subject=subject,
            message=message
        )
        db.session.add(help_request)
        db.session.commit()
        flash("Your support request has been submitted.", "success")
        return redirect(url_for('contact_support'))

    return render_template('help.html', user=user)

@app.route('/hire', methods=['GET', 'POST'])
def hire():
    """Handles hire inquiries."""
    # Pre-fill data if user is logged in
    full_name_prefill = current_user.name if current_user.is_authenticated else ''
    email_prefill = current_user.email if current_user.is_authenticated else ''
    user_id_for_db = current_user.id if current_user.is_authenticated else None

    if request.method == 'POST':
        form_full_name = request.form.get('full_name')
        form_company_name = request.form.get('company_name')
        form_email = request.form.get('email')
        form_phone = request.form.get('phone')
        form_service_interest = request.form.get('service_interest')
        form_project_details = request.form.get('project_details')

        # Server-side validation
        if not form_full_name or not form_email or not form_service_interest or not form_project_details:
            flash('Please fill in all required fields: Full Name, Work Email, Service Interest, and Project Details.', 'danger')
            return render_template('hire.html',
                                   full_name=form_full_name, # Use form data for re-populating
                                   email=form_email,
                                   company_name=form_company_name,
                                   phone=form_phone,
                                   service_interest=form_service_interest,
                                   project_details=form_project_details)
        
        # Save information to the Hire table
        new_hire_inquiry = Hire(
            full_name=form_full_name,
            company_name=form_company_name,
            email=form_email,
            phone=form_phone,
            service_interest=form_service_interest,
            project_details=form_project_details,
            user_id=user_id_for_db # Link to User if logged in
        )
        db.session.add(new_hire_inquiry)
        db.session.commit()

        flash('Your inquiry has been successfully submitted! We will get back to you soon.', 'success')
        return redirect(url_for('hire_success'))

    # For GET requests, render the form with potentially pre-filled data
    return render_template('hire.html', full_name=full_name_prefill, email=email_prefill)

@app.route('/hire_success')
def hire_success():
    """Renders the hire success page."""
    return render_template('hire_success.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """Handles general contact inquiries."""
    # Initialize variables for pre-filling the form
    name_prefill = ''
    email_prefill = ''
    phone_prefill = ''
    subject_prefill = ''
    message_prefill = ''
    user_id_for_db = None

    # Check if a user is logged in to pre-fill the form on GET request
    if current_user.is_authenticated:
        user_id_for_db = current_user.id
        name_prefill = current_user.name
        email_prefill = current_user.email

    if request.method == 'POST':
        # Retrieve form data
        form_name = request.form.get('name')
        form_email = request.form.get('email')
        form_phone = request.form.get('phone')
        form_subject = request.form.get('subject')
        form_message = request.form.get('message')

        # Server-side validation
        errors = []
        if not form_name:
            errors.append('Your Full Name is required.')
        if not form_email:
            errors.append('Your Email Address is required.')
        elif not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", form_email): # More robust email regex
            errors.append('Please enter a valid email address.')
        if not form_subject:
            errors.append('Please choose a subject for your inquiry.')
        if not form_message:
            errors.append('Your Message is required.')
        elif len(form_message) < 20: # Example: minimum message length
            errors.append('Your message should be at least 20 characters long.')
        
        if errors:
            # If there are validation errors
            for error in errors:
                flash(error, 'danger')

            # Re-render the form, preserving user's invalid input
            return render_template('contact.html',
                                   name=form_name,
                                   email=form_email,
                                   phone=form_phone,
                                   subject=form_subject,
                                   message=form_message)
        
        # If validation passes, proceed to save information
        new_contact_inquiry = ContactInquiry(
            full_name=form_name,
            email=form_email,
            phone=form_phone,
            subject=form_subject,
            message=form_message,
            user_id=user_id_for_db # This will be None if not logged in, or the user's ID
        )
        db.session.add(new_contact_inquiry)
        db.session.commit()

        flash('Your message has been sent successfully! We will get back to you soon.', 'success')
        return redirect(url_for('contact_success')) # Redirect to a success page

    # For GET requests, render the form with potentially pre-filled data
    return render_template('contact.html',
                           name=name_prefill,
                           email=email_prefill,
                           phone=phone_prefill,
                           subject=subject_prefill,
                           message=message_prefill)

@app.route('/contact_success')
def contact_success():
    """Renders the contact success page."""
    return render_template('contact_success.html')

@app.route('/testimonial', methods=['GET', 'POST'])
@login_required # Ensure user is logged in to submit a testimonial
def testimonial():
    """Handles user testimonials."""
    # Variables to pre-fill the form, retaining submitted data on error
    name_prefill = current_user.name
    email_prefill = current_user.email
    service_used_prefill = request.form.get('service_used')
    rating_prefill = int(request.form.get('rating')) if request.form.get('rating') else None
    testimonial_message_prefill = request.form.get('testimonial_message')
    consent_prefill = request.form.get('consent') == 'true' # Convert checkbox to boolean

    if request.method == 'POST':
        # Retrieve form data from the POST request
        name = request.form.get('name')
        email = request.form.get('email')
        service_used = request.form.get('service_used')
        rating_str = request.form.get('rating') # Get as string first
        testimonial_message = request.form.get('testimonial_message')
        consent = request.form.get('consent') == 'true'

        # Server-side validation
        errors = []
        if not name:
            errors.append('Full Name is required.')
        if not email:
            errors.append('Email Address is required.')
        if not service_used:
            errors.append('Please select a service.')
        if not rating_str:
            errors.append('Please provide a rating.')
        if not testimonial_message:
            errors.append('Your testimonial message is required.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            # Re-render the template with previously submitted data to avoid loss
            return render_template('testimonial.html',
                                   name=name, email=email, service_used=service_used,
                                   rating=int(rating_str) if rating_str else None,
                                   testimonial_message=testimonial_message,
                                   consent=consent)
        try:
            rating_int = int(rating_str) # Convert to integer after validation
            if not (1 <= rating_int <= 5):
                flash('Rating must be between 1 and 5 stars.', 'danger')
                return render_template('testimonial.html',
                                       name=name, email=email, service_used=service_used,
                                       rating=rating_int, testimonial_message=testimonial_message,
                                       consent=consent)

            # Create a new Testimonial object with the data
            new_testimonial = Testimonial(
                name=name,
                email=email,
                service_used=service_used,
                rating=rating_int,
                message=testimonial_message,
                consent_to_display=consent,
                user_id=current_user.id # This correctly links the testimonial to the logged-in user
            )

            db.session.add(new_testimonial)
            db.session.commit()

            flash('Thank you for your testimonial! It has been submitted successfully.', 'success')
            return redirect(url_for('testimonial')) # Redirect to prevent form resubmission

        except ValueError:
            flash('Invalid rating value provided.', 'danger')
            return render_template('testimonial.html',
                                   name=name, email=email, service_used=service_used,
                                   rating=None, testimonial_message=testimonial_message, # Clear rating on error
                                   consent=consent)
        except Exception as e:
            db.session.rollback() # Rollback changes if any other error occurs
            app.logger.error(f"Error saving testimonial: {e}")
            flash('An unexpected error occurred. Please try again later.', 'danger')
            return render_template('testimonial.html',
                                   name=name, email=email, service_used=service_used,
                                   rating=int(rating_str) if rating_str else None,
                                   testimonial_message=testimonial_message,
                                   consent=consent)

    # For GET requests, render the form with pre-filled data
    return render_template('testimonial.html',
                           name=name_prefill, email=email_prefill,
                           service_used=service_used_prefill, rating=rating_prefill,
                           testimonial_message=testimonial_message_prefill,
                           consent=consent_prefill)

@app.route('/link_bank_account', methods=['POST'])
@login_required # Requires user to be logged in
def link_bank_account():
    """Handles linking bank account details for the logged-in user."""
    bank_name = request.form.get('bank_name')
    account_name = request.form.get('account_name')
    account_number = request.form.get('account_number')
    account_type = request.form.get('account_type')

    if not bank_name or not account_name or not account_number or not account_type:
        flash('All bank details fields are required.', 'danger')
        return redirect(url_for('dashboard'))

    if not account_number.isdigit() or len(account_number) != 10:
        flash('Account number must be exactly 10 digits.', 'danger')
        return redirect(url_for('dashboard'))

    # Check if the user already has bank details linked (current_user is available)
    if current_user.bank_details:
        flash('You have already linked your bank account. Please update it if needed.', 'warning')
        return redirect(url_for('dashboard'))

    try:
        new_bank_details = Bank(
            user_id=current_user.id, # current_user.id will now be available
            bank_name=bank_name,
            account_name=account_name,
            account_number=account_number,
            account_type=account_type
        )
        db.session.add(new_bank_details)
        db.session.commit()
        flash('Bank account linked successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while linking your bank account: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))




@app.route('/course')
@login_required # Ensure user is logged in to access this page
def courses():
    """
    Displays the main courses page, showing all available courses and
    the logged-in user's enrolled courses.
    """
    enrolled_courses = []
    # current_user is guaranteed to be authenticated by @login_required,
    # so no need for if current_user.is_authenticated: check here.
    enrolled_courses = current_user.enrollments # Assumes User model has a 'enrollments' relationship

    return render_template('course.html',
                           user_full_name=current_user.name,
                           user_email=current_user.email,
                           enrolled_courses=enrolled_courses)


@app.route('/enroll', methods=['POST'])
@login_required # Only logged-in users can enroll
def enroll_course():
    """
    Handles the course enrollment form submission.
    Validates input, uploads receipt, and saves enrollment to the database.
    """
    if request.method == 'POST':
        full_name = request.form.get('fullName')
        email = request.form.get('email')
        course_name = request.form.get('courseName')
        amount_paid_str = request.form.get('amountPaid')
        transaction_id = request.form.get('transactionId')
        payment_receipt = request.files.get('paymentReceipt')

        # --- Input Validation ---
        if not (full_name and email and course_name and amount_paid_str):
            flash('Please fill out all required fields: Full Name, Email, Course Name, and Amount Paid.', 'danger')
            app.logger.warning("Enrollment attempt: Missing required form fields.")
            return redirect(url_for('courses'))

        app.logger.debug(f"Received amountPaid string from form: '{amount_paid_str}'")

        # Validate Amount Paid is a number
        amount_paid_float = 0.0
        try:
            cleaned_amount_str = amount_paid_str.replace('₦', '').replace('$', '').replace(',', '').strip()
            
            if not cleaned_amount_str:
                raise ValueError("Amount string is empty or only contained symbols after cleaning.")
            
            amount_paid_float = float(cleaned_amount_str)
            
            if amount_paid_float <= 0:
                flash('Amount paid must be a positive numerical value.', 'danger')
                app.logger.warning(f"Enrollment attempt: Invalid amount paid: {amount_paid_float}. Must be positive.")
                return redirect(url_for('courses'))
        except ValueError as e:
            app.logger.error(f"Enrollment attempt: ValueError converting amount paid: {e}. Original: '{amount_paid_str}'")
            flash('Invalid amount paid. Please enter a numerical value (e.g., 15000.00).', 'danger')
            return redirect(url_for('courses'))

        # Handle Payment Receipt Upload
        receipt_filename = None
        if payment_receipt and payment_receipt.filename != '':
            if allowed_file(payment_receipt.filename):
                filename = secure_filename(payment_receipt.filename)
                receipt_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                try:
                    payment_receipt.save(receipt_path)
                    receipt_filename = filename
                    app.logger.info(f"Payment receipt '{filename}' saved successfully.")
                except Exception as e:
                    flash(f'Error saving receipt file: {e}. Please try again.', 'danger')
                    app.logger.error(f"Error saving receipt file '{filename}': {e}", exc_info=True)
                    return redirect(url_for('courses'))
            else:
                flash('Invalid payment receipt file. Allowed formats: PNG, JPG, JPEG, GIF, PDF.', 'danger')
                app.logger.warning(f"Enrollment attempt: Invalid file format for payment receipt: {payment_receipt.filename}")
                return redirect(url_for('courses'))
        else:
            flash('Payment receipt is required for enrollment. Please upload a file.', 'danger')
            app.logger.warning("Enrollment attempt: No payment receipt file provided.")
            return redirect(url_for('courses'))

        # --- Database Interaction ---
        try:
            new_enrollment = CourseEnrollment(
                user_id=current_user.id,
                full_name=full_name,
                email=email,
                course_name=course_name,
                amount_paid=amount_paid_float,
                transaction_id=transaction_id,
                receipt_filename=receipt_filename,
                status='pending'
            )
            db.session.add(new_enrollment)
            db.session.commit()
            flash(f'Enrollment for "{course_name}" submitted successfully! Your payment will be reviewed.', 'success')
            app.logger.info(f"Enrollment for user {current_user.id} and course '{course_name}' submitted successfully.")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Database error during enrollment for user {current_user.id}: {e}", exc_info=True)
            flash(f'An unexpected error occurred during enrollment. Please try again.', 'danger')
        
        # --- Final Redirect ---
        return redirect(url_for('courses', _anchor='all-courses'))

    app.logger.debug("Received a non-POST request to /enroll.")
    return render_template('course.html') # Render the courses page if it's a GET request





@app.route('/logout')
@login_required # Only logged in users can logout
def logout():
    """Logs out the current user."""
    logout_user() # Use Flask-Login's logout_user
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# --- ADMIN ROUTES ---

@app.route('/admin/signup', methods=['GET', 'POST'])
def admin_signup():
    """
    Handles the creation of the first admin account.
    Restricts access if an admin already exists and the current user is not an admin.
    """
    # If an admin already exists and the current user is not an authenticated admin,
    # redirect them to the admin login page. This prevents multiple public admin signups.
    if User.query.filter_by(is_admin=True).first() and not (current_user.is_authenticated and current_user.is_admin):
        flash('An administrator account already exists. Please log in as an administrator.', 'warning')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm-password']

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "danger")
            return redirect(url_for('admin_signup'))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('admin_signup'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Use a different email or log in.", "warning")
            return redirect(url_for('admin_signup'))

        hashed_password = generate_password_hash(password)

        # Generate referral code even for admin (can be ignored if not needed for admin)
        referral_code = generate_referral_code()
        while User.query.filter_by(referral_code=referral_code).first():
            referral_code = generate_referral_code()

        # Create new user and set as admin
        new_admin = User(name=name, email=email, password=hashed_password, referral_code=referral_code, is_admin=True)
        db.session.add(new_admin)
        db.session.commit()

        flash("Admin account created successfully! Please log in.", "success")
        return redirect(url_for('admin_login'))

    return render_template('admin_signup.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handles administrator login."""
    # If already logged in as an admin, redirect to admin dashboard
    if current_user.is_authenticated and current_user.is_admin:
        flash('You are already logged in as an administrator.', 'info')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')

        if not email or not password:
            flash("Please fill in all fields", "danger")
            return redirect(url_for('admin_login'))

        user = User.query.filter_by(email=email).first()

        # Validate credentials
        if not user or not check_password_hash(user.password, password):
            flash("Invalid email or password", "danger")
            return redirect(url_for('admin_login'))

        # Ensure the user has admin privileges
        if not user.is_admin:
            flash("This account does not have administrative privileges.", "danger")
            return redirect(url_for('admin_login'))

        # Login successful for admin
        login_user(user)
        flash(f"Welcome to the Admin Dashboard, {user.name}!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_login.html')


@app.route('/admin/dashboard') # Or @admin_bp.route('/dashboard') if using a blueprint
@login_required # Requires login
@admin_required # Requires admin privileges
def admin_dashboard():
    partners = User.query.filter_by(is_partner=True).all()
    # NEW: Get all users who are admins
    admins = User.query.filter_by(is_admin=True).all()

    # NEW: Get all users who have referred at least one other user
    # This queries for users where their 'referred_users' relationship is not empty
    # We use .has_any() for the relationship to check for existence of referred users
    referrers = User.query.filter(User.referred_users.any()).all()


    total_users = User.query.count()
    total_hires = Hire.query.count()
    total_contacts = ContactInquiry.query.count()
    total_testimonials = Testimonial.query.count()
    
    # Fetch recent data for display on dashboard (e.g., last 5 entries)
    recent_users = User.query.order_by(User.id.desc()).limit(5).all()
    recent_hires = Hire.query.order_by(Hire.submission_date.desc()).limit(5).all()
    recent_contacts = ContactInquiry.query.order_by(ContactInquiry.submission_date.desc()).limit(5).all()
    recent_testimonials = Testimonial.query.order_by(Testimonial.submission_date.desc()).limit(5).all()

    return render_template('admin_dashboard.html',
                           partners=partners,
                           admins=admins, # Pass admins to the template
                           referrers=referrers, # Pass referrers to the template

                           total_users=total_users,
                           total_hires=total_hires,
                           total_contacts=total_contacts,
                           total_testimonials=total_testimonials,
                           recent_users=recent_users,
                           recent_hires=recent_hires,
                           recent_contacts=recent_contacts,
                           recent_testimonials=recent_testimonials)

# You will likely also need a route to view all referrers in detail if not already present
@app.route('/admin/referrers')
@login_required
@admin_required
def admin_referrers_list():
    referrers = User.query.filter(User.referred_users.any()).all()
    return render_template('admin_referrers_list.html', referrers=referrers)

# And a route to view all admins
@app.route('/admin/admins')
@login_required
@admin_required
def admin_admins_list():
    admins = User.query.filter_by(is_admin=True).all()
    return render_template('admin_admins_list.html', admins=admins)
@app.route('/admin_logout')
@login_required # Only logged in users can logout
@admin_required
def admin_logout():
    """Logs out the current user."""
    logout_user() # Use Flask-Login's logout_user
    flash('Logged out successfully.', 'info')
    return redirect(url_for('admin_login'))



@app.route('/admin/users')
@login_required
@admin_required
def all_users():
    """Displays a list of all users."""
    users = User.query.all() # Fetch all users from the database
    return render_template('allusers.html', users=users)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Handles adding a new user by an admin."""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password') # Remember to hash passwords!
        referral_code = request.form.get('referral_code')
        is_admin_str = request.form.get('is_admin') # Get admin status from form

        # Basic validation
        if not all([name, email, password]): # referral_code can be generated
            flash('Name, email, and password are required.', 'danger')
            return redirect(url_for('add_user'))

        # Generate referral code if not provided
        if not referral_code:
            referral_code = generate_referral_code()
            while User.query.filter_by(referral_code=referral_code).first():
                referral_code = generate_referral_code()

        # Check for existing email
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('add_user'))

        hashed_password = generate_password_hash(password)
        is_admin = (is_admin_str == 'true') # Convert string 'true' to boolean True

        new_user = User(name=name, email=email, password=hashed_password, referral_code=referral_code, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('all_users'))
    
    # GET request - render the add user form
    return render_template('add_user_form.html')

@app.route('/admin/users/<int:user_id>')
@login_required
@admin_required
def view_user(user_id):
    """Displays details of a single user."""
    user = User.query.get_or_404(user_id)
    return render_template('user_details.html', user=user)

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    """Handles editing an existing user by an admin."""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.referral_code = request.form.get('referral_code')
        
        new_password = request.form.get('password')
        if new_password: # Only update password if provided
            user.password = generate_password_hash(new_password)
        
        # Admin status can also be edited by another admin
        is_admin_str = request.form.get('is_admin')
        user.is_admin = (is_admin_str == 'true') # Convert string 'true' to boolean True

        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('all_users'))
    
    # GET request - render the edit user form, pre-filled with existing data
    return render_template('edit_user_form.html', user=user)




@app.route('/admin/referrer/<int:user_id>/referred_users')
@admin_required
def admin_referred_users_by_referrer(user_id):
    """
    Displays the details of users referred by a specific referrer.
    """
    referrer = User.query.get_or_404(user_id)

    # Ensure the user being viewed is actually a referrer or could be one
    if not referrer.referred_users:
        flash(f"User '{referrer.name}' (ID: {referrer.id}) has not referred anyone yet.", "info")
        return redirect(url_for('admin_referrers_list'))

    referred_users_details = []
    for referred_user in referrer.referred_users:
        referred_users_details.append({
            'name': referred_user.name,
            'email': referred_user.email,
            'referral_code': referred_user.referral_code,
            # Add other details of the referred user if needed, e.g., join date
            'join_date': referred_user.id # Assuming ID or another field can represent join date or order
        })
    
    # Optional: Sort referred users by name or join date
    referred_users_details.sort(key=lambda x: x['name'])


    return render_template('admin_referred_users_details.html',
                           referrer=referrer,
                           referred_users=referred_users_details)


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Handles deleting a user by an admin."""
    user = User.query.get_or_404(user_id)
    # Prevent admin from deleting their own account
    if current_user.id == user.id:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('all_users'))

    # Important: Consider deleting related records (e.g., bank_details, help requests, hires, testimonials, contacts)
    # or setting up CASCADE DELETE in your SQLAlchemy model relationships for proper data integrity.
    # For simplicity, here we just delete the user.
    if user.bank_details:
        db.session.delete(user.bank_details)
    # You might want to delete related Help, Hire, ContactInquiry, Testimonial entries as well,
    # or handle them based on your application's logic (e.g., set user_id to NULL, or delete).
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('all_users'))

# --- ADMIN SPECIFIC ROUTES FOR OTHER MODELS ---

@app.route('/admin/help_requests')
@login_required
@admin_required
def view_help_requests():
    """Displays all help requests."""
    help_requests = Help.query.order_by(Help.date_sent.desc()).all()
    return render_template('admin_help_requests.html', help_requests=help_requests)

@app.route('/admin/help_requests/<int:request_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_help_request(request_id):
    """Deletes a specific help request."""
    help_request = Help.query.get_or_404(request_id)
    db.session.delete(help_request)
    db.session.commit()
    flash('Help request deleted successfully!', 'success')
    return redirect(url_for('view_help_requests'))

@app.route('/admin/hire_inquiries')
@login_required
@admin_required
def view_hire_inquiries():
    """Displays all hire inquiries."""
    hire_inquiries = Hire.query.order_by(Hire.submission_date.desc()).all()
    return render_template('admin_hire_inquiries.html', hire_inquiries=hire_inquiries)

@app.route('/admin/hire_inquiries/<int:inquiry_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_hire_inquiry(inquiry_id):
    """Deletes a specific hire inquiry."""
    hire_inquiry = Hire.query.get_or_404(inquiry_id)
    db.session.delete(hire_inquiry)
    db.session.commit()
    flash('Hire inquiry deleted successfully!', 'success')
    return redirect(url_for('view_hire_inquiries'))

@app.route('/admin/contact_inquiries')
@login_required
@admin_required
def view_contact_inquiries():
    """Displays all contact inquiries."""
    contact_inquiries = ContactInquiry.query.order_by(ContactInquiry.submission_date.desc()).all()
    return render_template('admin_contact_inquiries.html', contact_inquiries=contact_inquiries)

@app.route('/admin/contact_inquiries/<int:inquiry_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_contact_inquiry(inquiry_id):
    """Deletes a specific contact inquiry."""
    contact_inquiry = ContactInquiry.query.get_or_404(inquiry_id)
    db.session.delete(contact_inquiry)
    db.session.commit()
    flash('Contact inquiry deleted successfully!', 'success')
    return redirect(url_for('view_contact_inquiries'))

@app.route('/admin/testimonials')
@login_required
@admin_required
def view_testimonials():
    """Displays all testimonials."""
    testimonials = Testimonial.query.order_by(Testimonial.submission_date.desc()).all()
    return render_template('admin_testimonials.html', testimonials=testimonials)

@app.route('/admin/testimonials/<int:testimonial_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_testimonial(testimonial_id):
    """Deletes a specific testimonial."""
    testimonial_item = Testimonial.query.get_or_404(testimonial_id)
    db.session.delete(testimonial_item)
    db.session.commit()
    flash('Testimonial deleted successfully!', 'success')
    return redirect(url_for('view_testimonials'))






# --- PARTNERSHIP ROUTES ---

@app.route('/partner_signup', methods=['GET', 'POST'])
def partner_signup():
    """Handles partner registration."""
    if current_user.is_authenticated:
        if current_user.is_partner:
            flash('You are already logged in as a partner.', 'info')
            return redirect(url_for('partner_dashboard'))
        else:
            flash('You are already logged in as a regular user. Please log out to sign up as a partner.', 'info')
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        company_name = request.form['company_name'].strip()
        contact_name = request.form['contact_name'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm-password']
        phone = request.form.get('phone', '').strip()
        business_type = request.form.get('business_type', '').strip()

        # Store form data for re-population
        form_data = {
            'company_name': company_name,
            'contact_name': contact_name,
            'email': email,
            'phone': phone,
            'business_type': business_type
        }

        # Form validation
        if not all([company_name, contact_name, email, password, confirm_password, business_type]):
            flash("All required fields must be filled.", "danger")
            return render_template('partner_signup.html', form_data=form_data)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('partner_signup.html', form_data=form_data)

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please use a different email or log in.", "warning")
            return render_template('partner_signup.html', form_data=form_data)

        # Generate unique referral code for the new partner
        partner_referral_code = generate_referral_code()
        while User.query.filter_by(referral_code=partner_referral_code).first():
            partner_referral_code = generate_referral_code()

        # Hash password
        hashed_password = generate_password_hash(password)

        new_partner_user = User(
            name=contact_name, # Using contact_name as the user's name for Flask-Login
            email=email,
            password=hashed_password,
            referral_code=partner_referral_code,
            is_admin=False,
            is_partner=True, # Mark as partner
            company_name=company_name,
            contact_name=contact_name,
            phone=phone,
            business_type=business_type
        )
        db.session.add(new_partner_user)
        db.session.commit()

        flash(f"Partnership account for {company_name} created successfully! Your referral code is: {partner_referral_code}", "success")
        return redirect(url_for('partner_login'))

    return render_template('partner_signup.html', form_data={})

@app.route('/partner_login', methods=['GET', 'POST'])
def partner_login():
    """Handles partner login."""
    if current_user.is_authenticated:
        if current_user.is_partner:
            flash('You are already logged in as a partner.', 'info')
            return redirect(url_for('partner_dashboard'))
        else:
            flash('You are already logged in as a regular user. Please log out to log in as a partner.', 'info')
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email').strip()
        password = request.form.get('password')

        if not email or not password:
            flash("Please fill in all fields", "danger")
            return redirect(url_for('partner_login'))

        user = User.query.filter_by(email=email).first()

        # Check if the user exists and is actually a partner
        if not user or not user.is_partner:
            flash("Invalid email or password for partner account.", "danger")
            return redirect(url_for('partner_login'))

        # Validate password
        if not check_password_hash(user.password, password):
            flash("Invalid email or password for partner account.", "danger")
            return redirect(url_for('partner_login'))

        # Login successful - use Flask-Login's login_user
        login_user(user)
        flash(f"Welcome back, {user.company_name}!", "success")
        return redirect(url_for('partner_dashboard'))

    return render_template('partner_login.html')

@app.route('/partner_dashboard')
@partner_required # Ensure only logged-in partners can access
def partner_dashboard():
    """Renders the partner dashboard, displaying referred users."""
    partner = current_user # This is the logged-in partner user object

    # Fetch users who were referred by this partner
    referred_users = User.query.filter_by(referred_by_id=partner.id).all()

    flash(f'Welcome To Your Partner Dashboard, {partner.company_name}.', 'success')
    return render_template('partner_dashboard.html', partner=partner, referred_users=referred_users)





if __name__ == '__main__':
    app.run(debug=True)
