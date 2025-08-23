import os
import json
import pickle
from datetime import datetime, timedelta
from functools import wraps
import secrets
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Google integration (optional)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️  Google libraries not installed. Google integration disabled.")

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# CSRF Protection
csrf = CSRFProtect(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Data storage
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, 'inanis_garage_data.pickle')

# Google configuration
SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_CREDENTIALS', 'credentials.json')
CALENDAR_ID = os.environ.get('CALENDAR_ID', 'primary')

# Global data
users = {}
vehicles = {}
assignments = []
fuel_logs = {}
documents = {}
maintenance_records = {}

# Google services
driveservice = None
calservice = None
google_enabled = False

def init_google_services():
    global driveservice, calservice, google_enabled
    if not GOOGLE_AVAILABLE or not os.path.exists(SERVICE_ACCOUNT_FILE):
        return False
    try:
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
        driveservice = build('drive', 'v3', credentials=credentials)
        calservice = build('calendar', 'v3', credentials=credentials)
        google_enabled = True
        logger.info("✅ Google services initialized for Inanis Garage")
        return True
    except Exception as e:
        logger.error(f"Google initialization failed: {e}")
        return False

def load_data():
    global users, vehicles, assignments, fuel_logs, documents, maintenance_records
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                users = data.get('users', {})
                vehicles = data.get('vehicles', {})
                assignments = data.get('assignments', [])
                fuel_logs = data.get('fuel_logs', {})
                documents = data.get('documents', {})
                maintenance_records = data.get('maintenance_records', {})
        except Exception as e:
            logger.error(f"Failed to load data: {e}")

    # Initialize admin user if no users exist
    if not users:
        users = {
            "admin": {
                "password": generate_password_hash("adminpass"), 
                "role": "admin",
                "created_date": datetime.now().isoformat(),
                "garage_name": "Inanis Garage"
            }
        }
        save_data()

def save_data():
    try:
        data = {
            'users': users,
            'vehicles': vehicles, 
            'assignments': assignments,
            'fuel_logs': fuel_logs,
            'documents': documents,
            'maintenance_records': maintenance_records,
            'garage_info': {
                'name': 'Inanis Garage',
                'version': '2.0.0',
                'last_updated': datetime.now().isoformat()
            }
        }
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    user = users.get(username)
    if user:
        return User(username, user["role"])

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required for Inanis Garage operations.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def upload_file_to_drive(file_path):
    if not google_enabled or not driveservice:
        return None, None
    try:
        file_metadata = {"name": f"InanisGarage_{os.path.basename(file_path)}"}
        media = MediaFileUpload(file_path, resumable=True)
        file = driveservice.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return file.get('id'), file.get('webViewLink')
    except Exception as e:
        logger.error(f"Drive upload failed: {e}")
        return None, None

def create_calendar_event(summary, description, start_date, end_date):
    if not google_enabled or not calservice:
        return None
    try:
        event = {
            'summary': f"[Inanis Garage] {summary}",
            'description': f"{description}\n\nManaged by Inanis Garage System",
            'start': {'date': start_date},
            'end': {'date': end_date},
        }
        event = calservice.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return event.get('htmlLink')
    except Exception as e:
        logger.error(f"Calendar event failed: {e}")
        return None

# Routes
@app.route('/')
@login_required
def index():
    status = {}
    available_count = 0
    assigned_count = 0
    expiring_docs = []
    
    today = datetime.today().strftime("%Y-%m-%d")
    for vid, v in vehicles.items():
        who = "Available"
        for a in assignments:
            if a["car_id"] == vid and a["start_date"] <= today <= a["end_date"]:
                who = a["driver"]
                break
        status[vid] = who
        
        if who == "Available":
            available_count += 1
        else:
            assigned_count += 1
    
    # Check for expiring documents
    for car_id, docs in documents.items():
        for doc in docs:
            if doc.get('expiry'):
                try:
                    expiry_date = datetime.strptime(doc['expiry'], '%Y-%m-%d').date()
                    days_until_expiry = (expiry_date - datetime.now().date()).days
                    if -7 <= days_until_expiry <= 30:  # Show expired (last 7 days) and expiring (next 30 days)
                        expiring_docs.append({
                            'car_id': car_id,
                            'vehicle': vehicles.get(car_id, {}),
                            'document': doc['type'],
                            'expiry_date': doc['expiry'],
                            'days_remaining': days_until_expiry,
                            'status': 'expired' if days_until_expiry < 0 else ('expiring_soon' if days_until_expiry <= 7 else 'due_soon')
                        })
                except ValueError:
                    continue
    
    return render_template('index.html', 
                         vehicles=vehicles, 
                         status=status, 
                         role=current_user.role,
                         available_count=available_count,
                         assigned_count=assigned_count,
                         expiring_docs=expiring_docs[:5])  # Show top 5 alerts


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        user = users.get(uname)
        if user and check_password_hash(user["password"], pwd):
            login_user(User(uname, user['role']))
            flash(f"Welcome to Inanis Garage, {uname}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password for Inanis Garage access.", "error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out from Inanis Garage.", "success")
    return redirect(url_for('login'))

@app.route('/add_vehicle', methods=['GET', 'POST'])
@login_required
@admin_required
def add_vehicle():
    if request.method == 'POST':
        vid = request.form['reg_no'].strip().upper()
        if vid in vehicles:
            flash("Vehicle already exists in Inanis Garage.", "error")
            return render_template('add_vehicle.html')
        
        # Get form data
        make = request.form['make'].strip()
        model = request.form['model'].strip()
        year = int(request.form['year'])
        color = request.form['color'].strip()
        
        # 📸 Handle car thumbnail upload
        thumbnail_url = None
        thumbnail_filename = None
        
        car_thumbnail = request.files.get('car_thumbnail')
        if car_thumbnail and car_thumbnail.filename:
            try:
                # Secure filename
                filename = secure_filename(car_thumbnail.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                thumbnail_filename = f"car_{vid}_{timestamp}_{filename}"
                
                # Create thumbnails directory
                thumbnails_dir = os.path.join('static', 'car_thumbnails')
                os.makedirs(thumbnails_dir, exist_ok=True)
                
                # Save file
                thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                car_thumbnail.save(thumbnail_path)
                
                # Generate URL for accessing the image
                thumbnail_url = url_for('static', filename=f'car_thumbnails/{thumbnail_filename}')
                
                logger.info(f"✅ Thumbnail saved: {thumbnail_filename}")
                
            except Exception as e:
                logger.error(f"Thumbnail upload failed: {e}")
                flash("⚠️ Car thumbnail upload failed, but vehicle was added successfully.", "warning")
        
        vehicles[vid] = {
            "make": make,
            "model": model,
            "year": year,
            "reg_no": vid,
            "color": color,
            "odo": float(request.form['odo']),
            "desc": request.form['desc'].strip(),
            "created_date": datetime.now().isoformat(),
            "garage": "Inanis Garage",
            # 📸 Store thumbnail information
            "thumbnail_url": thumbnail_url,
            "thumbnail_filename": thumbnail_filename,
            "has_custom_image": thumbnail_url is not None
        }
        save_data()
        
        success_msg = f"✅ Vehicle {vid} added to Inanis Garage!"
        if thumbnail_url:
            success_msg += " Car thumbnail uploaded successfully!"
            
        flash(success_msg, "success")
        logger.info(f"Vehicle {vid} added by {current_user.id} with thumbnail: {bool(thumbnail_url)}")
        return redirect(url_for('index'))
    
    return render_template('add_vehicle.html')



@app.route('/edit_vehicle/<car_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_vehicle(car_id):
    """Edit vehicle master data - Admin only"""
    if car_id not in vehicles:
        flash("Vehicle not found in Inanis Garage.", "error")
        return redirect(url_for('index'))
    
    v = vehicles[car_id]
    
    if request.method == 'POST':
        try:
            # Get form data
            old_reg = v['reg_no']
            new_reg = request.form['reg_no'].strip().upper()
            new_make = request.form['make'].strip()
            new_model = request.form['model'].strip()
            new_year = int(request.form['year'])
            new_color = request.form['color'].strip()
            new_odo = float(request.form['odo'])
            new_desc = request.form['desc'].strip()
            new_status = request.form.get('status', 'active')
            
            # Validation: If registration number changed, check if new one exists
            if old_reg != new_reg and new_reg in vehicles:
                flash(f"Registration number '{new_reg}' already exists in garage.", "error")
                return render_template('edit_vehicle.html', v=v, car_id=car_id)
            
            # Update vehicle information
            updated_vehicle = {
                'make': new_make,
                'model': new_model,
                'year': new_year,
                'reg_no': new_reg,
                'color': new_color,
                'odo': new_odo,
                'desc': new_desc,
                'status': new_status,
                'created_date': v.get('created_date', datetime.now().isoformat()),
                'updated_date': datetime.now().isoformat(),
                'updated_by': current_user.id,
                'garage': 'Inanis Garage',
                'image_url': v.get('image_url'),  # Keep existing image
                'image_fetched': v.get('image_fetched', False)
            }
            
            # If registration number changed, we need to move all related data
            if old_reg != new_reg:
                logger.info(f"Registration change: {old_reg} → {new_reg}")
                
                # Update the main vehicles dictionary
                vehicles[new_reg] = updated_vehicle
                del vehicles[old_reg]
                
                # Update all assignments that reference this vehicle
                for assignment in assignments:
                    if assignment['car_id'] == old_reg:
                        assignment['car_id'] = new_reg
                        logger.info(f"Updated assignment: {assignment}")
                
                # Update fuel logs dictionary key
                if old_reg in fuel_logs:
                    fuel_logs[new_reg] = fuel_logs[old_reg]
                    del fuel_logs[old_reg]
                    logger.info(f"Moved fuel logs: {old_reg} → {new_reg}")
                
                # Update documents dictionary key
                if old_reg in documents:
                    documents[new_reg] = documents[old_reg]
                    del documents[old_reg]
                    logger.info(f"Moved documents: {old_reg} → {new_reg}")
                
                # Update maintenance records if they exist
                if old_reg in maintenance_records:
                    maintenance_records[new_reg] = maintenance_records[old_reg]
                    del maintenance_records[old_reg]
                    logger.info(f"Moved maintenance records: {old_reg} → {new_reg}")
                
                car_id = new_reg  # Update for redirect
            else:
                # Just update the existing vehicle
                vehicles[car_id] = updated_vehicle
            
            # Save all changes
            save_data()
            
            flash(f"✅ Vehicle {new_reg} updated successfully by {current_user.id}!", "success")
            logger.info(f"Vehicle {new_reg} updated by {current_user.id}")
            
            return redirect(url_for('vehicle', car_id=car_id))
            
        except ValueError as e:
            flash("❌ Please enter valid numbers for year and odometer.", "error")
            logger.error(f"Vehicle update validation error: {e}")
        except Exception as e:
            logger.error(f"Vehicle update failed: {e}")
            flash("❌ Vehicle update failed. Please try again.", "error")
    
    # GET request - show edit form
    return render_template('edit_vehicle.html', v=v, car_id=car_id)

@app.route('/vehicle/<car_id>')
@login_required
def vehicle(car_id):
    v = vehicles.get(car_id)
    if not v:
        flash("Vehicle not found in Inanis Garage.", "error")
        return redirect(url_for('index'))

    docs = documents.get(car_id, [])
    flogs = fuel_logs.get(car_id, [])
    assigned = [a for a in assignments if a["car_id"] == car_id]
    maintenance = maintenance_records.get(car_id, [])

    return render_template('vehicle.html', v=v, docs=docs, flogs=flogs, 
                         assignments=assigned, maintenance=maintenance, role=current_user.role)

@app.route('/assign_driver/<car_id>', methods=['POST'])
@login_required
@admin_required
def assign_driver(car_id):
    driver = request.form['driver'].strip()
    start_date = request.form['start_date']
    end_date = request.form['end_date']

    assignment = {
        "car_id": car_id, "driver": driver, "start_date": start_date, "end_date": end_date,
        "assigned_by": current_user.id, "garage": "Inanis Garage"
    }
    assignments.append(assignment)

    event_link = create_calendar_event(
        summary=f"Vehicle {car_id} assigned to {driver}",
        description=f"Vehicle assignment from Inanis Garage",
        start_date=start_date, end_date=end_date
    )

    save_data()
    if event_link:
        flash("Driver assigned! Calendar event created.", "success")
    else:
        flash("Driver assigned successfully in Inanis Garage!", "success")
    return redirect(url_for('vehicle', car_id=car_id))

@app.route('/add_fuel/<car_id>', methods=['POST'])
@login_required
def add_fuel(car_id):
    try:
        prev = float(request.form['prev_odo'])
        curr = float(request.form['curr_odo'])
        liters = float(request.form['liters'])
        cost = float(request.form.get('cost', 0))

        log = {
            "date": request.form['date'],
            "prev_odo": prev, "curr_odo": curr,
            "liters": liters, "cost": cost,
            "driver": current_user.id
        }
        fuel_logs.setdefault(car_id, []).append(log)
        vehicles[car_id]["odo"] = curr
        save_data()
        flash(f"Fuel log added for {car_id}", "success")
    except ValueError:
        flash("Please enter valid numbers.", "error")
    return redirect(url_for('vehicle', car_id=car_id))

@app.route('/upload_document/<car_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_document(car_id):
    if request.method == "POST":
        file = request.files.get('doc_file')
        doc_type = request.form.get('doc_type')
        expiry = request.form.get('expiry')
        notes = request.form.get('notes', '')
        
        if not file or not file.filename:
            flash("Please select a file to upload.", "error")
            return render_template('add_document.html', car_id=car_id)
        
        if not doc_type:
            flash("Please select a document type.", "error")
            return render_template('add_document.html', car_id=car_id)
        
        try:
            filename = secure_filename(file.filename)
            # Add timestamp to avoid conflicts
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{car_id}_{doc_type.replace(' ', '_')}_{timestamp}_{filename}"
            
            # Create document storage directory
            doc_dir = os.path.join('data', 'documents', car_id)
            os.makedirs(doc_dir, exist_ok=True)
            os.makedirs('temp_uploads', exist_ok=True)
            
            # Save to both locations for reliability
            local_path = os.path.join('temp_uploads', safe_filename)
            permanent_path = os.path.join(doc_dir, safe_filename)
            
            file.save(local_path)
            
            # Copy to permanent storage
            import shutil
            shutil.copy2(local_path, permanent_path)
            
            # Try to upload to Google Drive (if available)
            file_id, web_link = upload_file_to_drive(local_path)
            
            # Calculate days until expiry
            days_until_expiry = None
            expiry_status = "valid"
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                    days_until_expiry = (expiry_date - datetime.now().date()).days
                    if days_until_expiry < 0:
                        expiry_status = "expired"
                    elif days_until_expiry <= 30:
                        expiry_status = "expiring_soon"
                except ValueError:
                    pass
            
            # Create view URL for local file
            local_view_url = url_for('view_document', car_id=car_id, filename=safe_filename)
            
            doc_record = {
                'type': doc_type,
                'expiry': expiry,
                'expiry_status': expiry_status,
                'days_until_expiry': days_until_expiry,
                'filename': safe_filename,
                'original_filename': file.filename,
                'local_path': permanent_path,
                'local_view_url': local_view_url,
                'drive_link': web_link,
                'drive_id': file_id,
                'notes': notes,
                'uploaded_date': datetime.now().isoformat(),
                'uploaded_by': current_user.id,
                'garage': 'Inanis Garage'
            }
            
            documents.setdefault(car_id, []).append(doc_record)
            save_data()
            
            logger.info(f"✅ Document uploaded for {car_id} by {current_user.id}")
            
            if web_link:
                flash(f"✅ Document '{doc_type}' uploaded to Google Drive successfully!", "success")
            else:
                flash(f"✅ Document '{doc_type}' saved securely. You can view it from the vehicle page.", "success")
                
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            flash("❌ Document upload failed. Please try again.", "error")
        finally:
            # Clean up temp file (but keep permanent copy)
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except:
                    pass
                
        return redirect(url_for('vehicle', car_id=car_id))
    
    # GET request - show upload form
    return render_template('add_document.html', car_id=car_id)


@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        uname = request.form['username'].strip()
        pwd = request.form['password']
        role = request.form['role']

        if uname in users:
            flash("Username already exists.", "error")
            return render_template('add_user.html')

        users[uname] = {
            "password": generate_password_hash(pwd),
            "role": role,
            "created_date": datetime.now().isoformat()
        }
        save_data()
        flash(f"User {uname} added to Inanis Garage!", "success")
        return redirect(url_for('index'))

    return render_template('add_user.html')

@app.route('/update_driver_license/<username>', methods=['GET', 'POST'])
@login_required
def update_driver_license(username):
    if current_user.role != "admin" and current_user.id != username:
        flash("You cannot update this profile.", "error")
        return redirect(url_for('index'))

    user = users.get(username)
    if not user or user['role'] != 'driver':
        flash("Driver not found.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        license_num = request.form['license_number']
        license_doc_link = request.form['license_doc_link']

        user['license_number'] = license_num
        user['license_doc_link'] = license_doc_link
        save_data()
        flash("Driver license info updated!", "success")
        return redirect(url_for('index'))

    return render_template('update_driver_license.html', user=user, username=username)

if __name__ == "__main__":
    os.makedirs('temp_uploads', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('templates', exist_ok=True)

    init_google_services()
    load_data()

    print("🔧 Inanis Garage Management System Starting...")
    print(f"📊 Google Integration: {'✅ Enabled' if google_enabled else '❌ Disabled'}")
    print(f"👥 Users: {len(users)}")
    print(f"🚙 Vehicles: {len(vehicles)}")
    print("🌐 Access: http://localhost:5000")
    print("🚗 Welcome to Inanis Garage!")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
@app.route('/view_document/<car_id>/<filename>')
@login_required
def view_document(car_id, filename):
    """
    Serve uploaded documents for viewing
    """
    try:
        # Security: Only allow viewing documents for cars user has access to
        if car_id not in vehicles:
            flash("Vehicle not found.", "error")
            return redirect(url_for('index'))
        
        # Check if file exists in temp_uploads
        file_path = os.path.join('temp_uploads', filename)
        if os.path.exists(file_path):
            from flask import send_file
            return send_file(file_path, as_attachment=False)
        
        # Check if file exists in data directory
        file_path = os.path.join('data', 'documents', car_id, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=False)
            
        flash("Document file not found.", "error")
        return redirect(url_for('vehicle', car_id=car_id))
        
    except Exception as e:
        logger.error(f"Error serving document: {e}")
        flash("Error loading document.", "error")
        return redirect(url_for('vehicle', car_id=car_id))
def get_indian_car_icon(make, model, year, color=""):
    """
    Get car icon URL for Indian vehicles - 100% FREE
    """
    make_lower = make.lower().replace(' ', '').replace('-', '')
    
    # Indian Car Brand Logos (Free CDN links)
    indian_car_logos = {
        'maruti': 'https://logos-world.net/wp-content/uploads/2021/03/Suzuki-Logo.png',
        'marutisuzuki': 'https://logos-world.net/wp-content/uploads/2021/03/Suzuki-Logo.png',
        'suzuki': 'https://logos-world.net/wp-content/uploads/2021/03/Suzuki-Logo.png',
        'tata': 'https://logos-world.net/wp-content/uploads/2021/03/Tata-Logo.png',
        'mahindra': 'https://logos-world.net/wp-content/uploads/2021/03/Mahindra-Logo.png',
        'hyundai': 'https://logos-world.net/wp-content/uploads/2021/03/Hyundai-Logo.png',
        'honda': 'https://logos-world.net/wp-content/uploads/2021/03/Honda-Logo.png',
        'toyota': 'https://logos-world.net/wp-content/uploads/2021/03/Toyota-Logo.png',
        'kia': 'https://logos-world.net/wp-content/uploads/2021/03/Kia-Logo.png',
        'mg': 'https://logos-world.net/wp-content/uploads/2021/08/MG-Logo.png',
        'renault': 'https://logos-world.net/wp-content/uploads/2021/03/Renault-Logo.png',
        'nissan': 'https://logos-world.net/wp-content/uploads/2021/03/Nissan-Logo.png',
        'ford': 'https://logos-world.net/wp-content/uploads/2021/03/Ford-Logo.png',
        'volkswagen': 'https://logos-world.net/wp-content/uploads/2021/03/Volkswagen-Logo.png',
        'skoda': 'https://logos-world.net/wp-content/uploads/2021/03/Skoda-Logo.png',
        'bmw': 'https://logos-world.net/wp-content/uploads/2021/03/BMW-Logo.png',
        'mercedes': 'https://logos-world.net/wp-content/uploads/2021/03/Mercedes-Benz-Logo.png',
        'audi': 'https://logos-world.net/wp-content/uploads/2021/03/Audi-Logo.png',
        'jeep': 'https://logos-world.net/wp-content/uploads/2021/03/Jeep-Logo.png',
        'datsun': 'https://1000logos.net/wp-content/uploads/2018/03/Datsun-Logo.png',
    }
    
    # Try to get brand logo first
    brand_logo = indian_car_logos.get(make_lower)
    if brand_logo:
        return {
            'type': 'logo',
            'url': brand_logo,
            'alt': f"{make} Logo"
        }
    
    # Fallback: Create custom placeholder with Indian car info
    return get_indian_car_placeholder(make, model, year, color)

def get_indian_car_placeholder(make, model, year, color):
    """
    Create custom placeholder for Indian cars
    """
    # Color mapping for Indian preferences
    color_codes = {
        'white': 'F8F9FA',
        'black': '212529', 
        'silver': 'ADB5BD',
        'gray': '6C757D',
        'grey': '6C757D',
        'red': 'DC3545',
        'blue': '0D6EFD',
        'green': '198754',
        'yellow': 'FFC107',
        'brown': '795548',
        'orange': 'FD7E14',
        'pearl': 'E9ECEF',
        'maroon': '800020'
    }
    
    bg_color = color_codes.get(color.lower(), '007AFF')  # Default Apple blue
    text_color = 'FFFFFF' if bg_color in ['212529', '6C757D', '800020', 'DC3545', '198754'] else '000000'
    
    # Create abbreviated text
    car_text = f"{make[:3]}{model[:3]}".upper()
    if len(car_text) > 6:
        car_text = car_text[:6]
    
    placeholder_url = f"https://via.placeholder.com/300x200/{bg_color}/{text_color}?text={car_text}"
    
    return {
        'type': 'placeholder',
        'url': placeholder_url,
        'alt': f"{make} {model} {year}"
    }

def get_popular_indian_cars():
    """
    Popular Indian car models for suggestions
    """
    return {
        'Maruti Suzuki': ['Swift', 'Baleno', 'Wagon R', 'Alto', 'Vitara Brezza', 'Ertiga', 'Dzire', 'Ciaz'],
        'Tata': ['Nexon', 'Harrier', 'Safari', 'Altroz', 'Tigor', 'Tiago', 'Punch'],
        'Hyundai': ['Creta', 'i20', 'Venue', 'Verna', 'Santro', 'Grand i10'],
        'Mahindra': ['XUV700', 'XUV300', 'Scorpio', 'Bolero', 'Thar', 'Marazzo'],
        'Honda': ['City', 'Amaze', 'WR-V', 'Jazz'],
        'Toyota': ['Innova Crysta', 'Fortuner', 'Glanza', 'Urban Cruiser'],
        'Kia': ['Seltos', 'Sonet', 'Carens'],
        'Renault': ['Kiger', 'Triber', 'Kwid'],
        'Nissan': ['Magnite', 'Kicks']
    }
