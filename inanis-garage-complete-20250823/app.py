import os
import json
import pickle
from datetime import datetime
from functools import wraps
import secrets
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ─── Setup logging and app ──────────────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# ─── Directories and data file ────────────────────────────────────────────────
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, 'inanis_garage_data.pickle')

# Create folders for uploads and templates
for folder in ['static/css', 'static/car_thumbnails', 'static/documents', 'temp_uploads', 'templates']:
    os.makedirs(folder, exist_ok=True)

# ─── In-memory data storage ─────────────────────────────────────────────────────
users = {}
vehicles = {}
assignments = []
fuel_logs = {}
documents = {}
maintenance_records = {}

# ─── Google Drive and Calendar setup ────────────────────────────────────────────
driveservice = None
calservice = None
google_enabled = False

def get_google_credentials():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if creds_json:
            return json.loads(creds_json)
        creds = {
            "type": "service_account",
            "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
            "private_key_id": os.environ.get('GOOGLE_PRIVATE_KEY_ID'),
            "private_key": os.environ.get('GOOGLE_PRIVATE_KEY', '').replace('\\n', '\n'),
            "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
            "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get('GOOGLE_CLIENT_CERT_URL')
        }
        if creds['project_id'] and creds['client_email'] and creds['private_key']:
            return creds
        return None
    except Exception as e:
        logger.error(f"Loading Google creds failed: {e}")
        return None

def init_google_services():
    global driveservice, calservice, google_enabled
    creds = get_google_credentials()
    if not creds:
        logger.info("Google Drive disabled")
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/calendar']
        )
        driveservice = build('drive', 'v3', credentials=credentials)
        calservice = build('calendar', 'v3', credentials=credentials)
        google_enabled = True
        logger.info("✅ Google services initialized")
    except Exception as e:
        logger.error(f"Google init failed: {e}")

def upload_file_to_drive(file_path):
    if not google_enabled or not driveservice:
        return None, None
    try:
        from googleapiclient.http import MediaFileUpload
        metadata = {
            'name': os.path.basename(file_path),
            'parents': [os.environ.get('GOOGLE_DRIVE_FOLDER_ID', 'root')]
        }
        media = MediaFileUpload(file_path, resumable=True)
        f = driveservice.files().create(body=metadata, media_body=media, fields='id,webViewLink').execute()
        driveservice.permissions().create(fileId=f['id'], body={'type': 'anyone', 'role': 'reader'}).execute()
        return f['id'], f['webViewLink']
    except Exception as e:
        logger.error(f"Google Drive upload failed: {e}")
        flash(f"⚠️ Google Drive upload error: {e}", "warning")
        return None, None

def create_calendar_event(summary, description, start_date, end_date):
    if not google_enabled or not calservice:
        return None
    try:
        event = {
            'summary': summary,
            'description': description,
            'start': {'date': start_date},
            'end': {'date': end_date},
        }
        e = calservice.events().insert(calendarId='primary', body=event).execute()
        return e.get('htmlLink')
    except Exception as e:
        logger.error(f"Calendar event failed: {e}")
        return None

# ─── Data load/save ─────────────────────────────────────────────────────────────
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
    if not users:
        users["admin"] = {
            "password": generate_password_hash("adminpass"),
            "role": "admin",
            "created_date": datetime.now().isoformat()
        }
        save_data()

def save_data():
    data = {
        'users': users,
        'vehicles': vehicles,
        'assignments': assignments,
        'fuel_logs': fuel_logs,
        'documents': documents,
        'maintenance_records': maintenance_records,
    }
    try:
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

# ─── Authentication ───────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, username, role):
        self.id = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    u = users.get(username)
    return User(username, u['role']) if u else None

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash("Admin access required.", "error")
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ─── Routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    today = datetime.today().strftime("%Y-%m-%d")
    status = {}
    available_count = 0
    assigned_count = 0
    expiring_docs = []

    for vid in vehicles:
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

        for doc in documents.get(vid, []):
            if doc.get('expiry'):
                try:
                    expiry_date = datetime.strptime(doc['expiry'], '%Y-%m-%d').date()
                    days_until_expiry = (expiry_date - datetime.now().date()).days
                    if -7 <= days_until_expiry <= 30:
                        expiring_docs.append({
                            'car_id': vid,
                            'document': doc['type'],
                            'expiry_date': doc['expiry'],
                            'days_remaining': days_until_expiry,
                            'status': 'expired' if days_until_expiry < 0 else 'expiring_soon'
                        })
                except ValueError:
                    continue

    return render_template('index.html',
                           vehicles=vehicles,
                           status=status,
                           role=current_user.role,
                           available_count=available_count,
                           assigned_count=assigned_count,
                           expiring_docs=expiring_docs[:5])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        user = users.get(uname)
        if user and check_password_hash(user['password'], pwd):
            login_user(User(uname, user['role']))
            flash(f"Welcome to Inanis Garage, {uname}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
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

        make = request.form['make'].strip()
        model = request.form['model'].strip()
        year = int(request.form['year'])
        color = request.form['color'].strip()
        odo = float(request.form['odo'])
        desc = request.form['desc'].strip()

        thumbnail_url = None
        car_thumbnail = request.files.get('car_thumbnail')
        if car_thumbnail and car_thumbnail.filename != '':
            try:
                filename = secure_filename(car_thumbnail.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir = os.path.join('static', 'car_thumbnails')
                os.makedirs(save_dir, exist_ok=True)
                saved_filename = f"{vid}_{timestamp}_{filename}"
                save_path = os.path.join(save_dir, saved_filename)
                car_thumbnail.save(save_path)
                thumbnail_url = url_for('static', filename=f'car_thumbnails/{saved_filename}')
            except Exception as e:
                logger.error(f"Thumbnail upload failed: {e}")
                flash("Car thumbnail upload failed, continuing without image.", "warning")

        vehicles[vid] = {
            "make": make,
            "model": model,
            "year": year,
            "color": color,
            "odo": odo,
            "desc": desc,
            "reg_no": vid,
            "thumbnail_url": thumbnail_url,
            "created_date": datetime.now().isoformat(),
            "garage": "Inanis Garage",
        }

        save_data()
        flash(f"Vehicle {vid} added successfully.", "success")
        return redirect(url_for('index'))

    return render_template('add_vehicle.html')

@app.route('/edit_vehicle/<car_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_vehicle(car_id):
    v = vehicles.get(car_id)
    if not v:
        flash("Vehicle not found.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        new_reg = request.form['reg_no'].strip().upper()
        if new_reg != car_id and new_reg in vehicles:
            flash(f"Registration number {new_reg} already exists.", "error")
            return render_template('edit_vehicle.html', v=v)

        make = request.form['make'].strip()
        model = request.form['model'].strip()
        year = int(request.form['year'])
        color = request.form['color'].strip()
        odo = float(request.form['odo'])
        desc = request.form['desc'].strip()
        car_thumbnail = request.files.get('car_thumbnail')
        thumbnail_url = v.get('thumbnail_url')
        if car_thumbnail and car_thumbnail.filename != '':
            try:
                filename = secure_filename(car_thumbnail.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_dir = os.path.join('static', 'car_thumbnails')
                os.makedirs(save_dir, exist_ok=True)
                saved_filename = f"{new_reg}_{timestamp}_{filename}"
                save_path = os.path.join(save_dir, saved_filename)
                car_thumbnail.save(save_path)
                thumbnail_url = url_for('static', filename=f'car_thumbnails/{saved_filename}')
            except Exception as e:
                logger.error(f"Thumbnail update failed: {e}")
                flash("Car thumbnail update failed.", "warning")

        updated_vehicle = {
            "make": make,
            "model": model,
            "year": year,
            "color": color,
            "odo": odo,
            "desc": desc,
            "reg_no": new_reg,
            "thumbnail_url": thumbnail_url,
            "created_date": v.get('created_date', datetime.now().isoformat()),
            "updated_date": datetime.now().isoformat(),
            "garage": "Inanis Garage",
        }

        if new_reg != car_id:
            vehicles[new_reg] = updated_vehicle
            del vehicles[car_id]
            for assignment in assignments:
                if assignment['car_id'] == car_id:
                    assignment['car_id'] = new_reg
            if car_id in fuel_logs:
                fuel_logs[new_reg] = fuel_logs[car_id]
                del fuel_logs[car_id]
            if car_id in documents:
                documents[new_reg] = documents[car_id]
                del documents[car_id]
            if car_id in maintenance_records:
                maintenance_records[new_reg] = maintenance_records[car_id]
                del maintenance_records[car_id]
        else:
            vehicles[car_id] = updated_vehicle

        save_data()
        flash(f"Vehicle {new_reg} updated successfully.", "success")
        return redirect(url_for('vehicle', car_id=new_reg))

    return render_template('edit_vehicle.html', v=v)

@app.route('/vehicle/<car_id>')
@login_required
def vehicle(car_id):
    v = vehicles.get(car_id)
    if not v:
        flash("Vehicle not found.", "error")
        return redirect(url_for('index'))
    docs = documents.get(car_id, [])
    flogs = fuel_logs.get(car_id, [])
    mileages = [log.get('fuel_efficiency') for log in flogs if log.get('fuel_efficiency')]
    overall_avg_mileage = round(sum(mileages) / len(mileages), 2) if mileages else None
    return render_template('vehicle.html', v=v, docs=docs, flogs=flogs,
                           overall_avg_mileage=overall_avg_mileage,
                           role=current_user.role)

@app.route('/add_fuel/<car_id>', methods=['POST'])
@login_required
def add_fuel(car_id):
    if car_id not in vehicles:
        flash("Vehicle not found.", "error")
        return redirect(url_for('index'))
    try:
        prev_odo = float(request.form['prev_odo'])
        curr_odo = float(request.form['curr_odo'])
        liters = float(request.form['liters'])
        date = request.form['date']
        if curr_odo <= prev_odo:
            flash("Current odometer must be greater than previous.", "error")
            return redirect(url_for('vehicle', car_id=car_id))
        if liters <= 0:
            flash("Fuel liters must be positive.", "error")
            return redirect(url_for('vehicle', car_id=car_id))
        distance = curr_odo - prev_odo
        fuel_efficiency = distance / liters
        log_entry = {
            "car_id": car_id,
            "prev_odo": prev_odo,
            "curr_odo": curr_odo,
            "distance": distance,
            "liters": liters,
            "fuel_efficiency": round(fuel_efficiency, 2),
            "date": date,
            "driver": current_user.id,
            "created_date": datetime.now().isoformat(),
            "garage": "Inanis Garage"
        }
        fuel_logs.setdefault(car_id, []).append(log_entry)
        vehicles[car_id]['odo'] = curr_odo
        save_data()
        flash(f"Fuel log added: {distance} km @ {fuel_efficiency:.2f} km/L.", "success")
    except Exception as e:
        logger.error(f"Fuel log error: {e}")
        flash("Failed to add fuel log.", "error")
    return redirect(url_for('vehicle', car_id=car_id))

@app.route('/upload_document/<car_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_document(car_id):
    # Ensure the vehicle exists
    if car_id not in vehicles:
        flash("Vehicle not found in Inanis Garage.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        file = request.files.get('doc_file')
        doc_type = request.form.get('doc_type')
        expiry = request.form.get('expiry')
        notes = request.form.get('notes', '')

        if not file or not file.filename or not doc_type:
            flash("File and document type required.", "error")
            return render_template('add_document.html', car_id=car_id)

        try:
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder = os.path.join('static', 'documents')
            os.makedirs(folder, exist_ok=True)
            safe_filename = f"doc_{car_id}_{doc_type.replace(' ', '_')}_{timestamp}_{filename}"
            file_path = os.path.join(folder, safe_filename)
            file.save(file_path)
            document_url = url_for('static', filename=f'documents/{safe_filename}')

            days_until_expiry = None
            expiry_status = "valid"
            expiry_alert = ""
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                    today_date = datetime.now().date()
                    days_until_expiry = (expiry_date - today_date).days
                    if days_until_expiry < 0:
                        expiry_status = "expired"
                        expiry_alert = f"⚠️ EXPIRED {abs(days_until_expiry)} days ago"
                    elif days_until_expiry <= 7:
                        expiry_status = "expiring_soon"
                        expiry_alert = f"⚠️ Expires in {days_until_expiry} days"
                    elif days_until_expiry <= 30:
                        expiry_status = "expiring_soon"
                        expiry_alert = f"📅 Expires in {days_until_expiry} days"
                    else:
                        expiry_alert = f"✅ Valid for {days_until_expiry} days"
                except ValueError:
                    logger.warning(f"Invalid expiry date {expiry}")

            # Attempt upload to Google Drive
            drive_id, drive_link = None, None
            storage_location = "Local Storage"
            if google_enabled and driveservice:
                try:
                    drive_id, drive_link = upload_file_to_drive(file_path)
                    if drive_link:
                        storage_location = "Google Drive + Local Backup"
                        logger.info(f"✅ Document uploaded to Drive: {drive_link}")
                        flash(f"Document '{doc_type}' uploaded to Google Drive successfully!", "success")
                    else:
                        raise Exception("No Drive link returned")
                except Exception as e:
                    logger.error(f"Drive upload fallback: {e}")
                    flash(f"Document '{doc_type}' saved locally (Google Drive unavailable).", "warning")
            else:
                flash(f"Document '{doc_type}' saved locally (Drive disabled).", "warning")

            doc_record = {
                'id': f"doc_{timestamp}_{car_id}",
                'type': doc_type,
                'expiry': expiry,
                'expiry_status': expiry_status,
                'days_until_expiry': days_until_expiry,
                'expiry_alert': expiry_alert,
                'filename': safe_filename,
                'original_filename': filename,
                'file_path': file_path,
                'document_url': document_url,
                'drive_id': drive_id,
                'drive_link': drive_link,
                'storage_location': storage_location,
                'notes': notes,
                'uploaded_date': datetime.now().isoformat(),
                'uploaded_by': current_user.id,
                'file_size': os.path.getsize(file_path),
                'garage': 'Inanis Garage'
            }

            documents.setdefault(car_id, []).append(doc_record)
            save_data()
            return redirect(url_for('vehicle', car_id=car_id))
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            flash(f"Document upload failed: {e}", "error")
            return render_template('add_document.html', car_id=car_id)

    return render_template('add_document.html', car_id=car_id)

@app.route('/view_document/<car_id>/<filename>')
@login_required
def view_document(car_id, filename):
    if car_id not in vehicles:
        flash("Vehicle not found.", "error")
        return redirect(url_for('index'))

    for folder in ['static/documents', 'static/car_thumbnails', 'temp_uploads']:
        file_path = os.path.join(folder, filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=False)

    flash("Document not found.", "error")
    return redirect(url_for('vehicle', car_id=car_id))

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
        flash(f"User {uname} added successfully.", "success")
        return redirect(url_for('index'))
    return render_template('add_user.html')

# ─── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_google_services()
    load_data()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
