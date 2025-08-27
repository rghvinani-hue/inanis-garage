import os
import json
import pickle
from datetime import datetime
from functools import wraps
import secrets
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

# ─── Setup logging and app ──────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ─── Directories and data file ─────────────────────────────────────────
DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, 'inanis_garage_data.pickle')

for folder in ['static/css', 'static/car_thumbnails', 'static/documents', 'temp_uploads', 'templates']:
    os.makedirs(folder, exist_ok=True)

BACKUP_ID_FILE = os.path.join(DATA_DIR, 'backup_file_id.txt')

# ─── In-memory data storage ────────────────────────────────────────────
users = {}
vehicles = {}
assignments = []
fuel_logs = {}
documents = {}
maintenance_records = {}

# ─── Google Drive and Calendar setup ───────────────────────────────────
driveservice = None
calservice = None
google_enabled = False

def get_google_credentials():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            logger.warning("GOOGLE_CREDENTIALS_JSON environment variable not set")
            return None
        creds = json.loads(creds_json)
        logger.info("Google credentials successfully loaded from environment variable")
        return creds
    except Exception as e:
        logger.error(f"Failed to load Google credentials JSON: {e}")
        return None

def init_google_services():
    global driveservice, calservice, google_enabled
    creds = get_google_credentials()
    if not creds:
        logger.info("Google Drive disabled: no valid credentials")
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
        google_enabled = False

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

def download_file_from_drive(file_id, dest_path):
    try:
        from googleapiclient import http as _http
        request = driveservice.files().get_media(fileId=file_id)
        with open(dest_path, 'wb') as f:
            downloader = _http.MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        logger.info(f"✅ Restored data file from Drive ({file_id})")
    except Exception as e:
        logger.error(f"Failed to download data backup from Drive: {e}")

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

def save_backup_file_id(file_id):
    try:
        with open(BACKUP_ID_FILE, 'w') as f:
            f.write(file_id)
    except Exception as e:
        logger.error(f"Failed to save backup file id: {e}")

def load_backup_file_id():
    try:
        if os.path.exists(BACKUP_ID_FILE):
            with open(BACKUP_ID_FILE, 'r') as f:
                return f.read().strip()
    except Exception as e:
        logger.error(f"Failed to load backup file id: {e}")
    return None

def load_data():
    global users, vehicles, assignments, fuel_logs, documents, maintenance_records

    drive_id = os.environ.get('GOOGLE_DATA_BACKUP_FILE_ID') or load_backup_file_id()

    if not os.path.exists(DATA_FILE) and google_enabled and driveservice:
        if drive_id:
            download_file_from_drive(drive_id, DATA_FILE)

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

    if google_enabled and driveservice:
        try:
            backup_id, backup_link = upload_file_to_drive(DATA_FILE)
            if backup_id:
                logger.info(f"✅ Data backup saved to Drive: {backup_id}")
                save_backup_file_id(backup_id)
        except Exception as e:
            logger.error(f"Failed to back up data to Drive: {e}")

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

# --- Data Management Routes ---

@app.route('/vehicles')
@login_required
def list_vehicles():
    return render_template('vehicles.html', vehicles=vehicles)

@app.route('/vehicles/<vehicle_id>')
@login_required
def view_vehicle(vehicle_id):
    vehicle = vehicles.get(vehicle_id)
    if not vehicle:
        flash("Vehicle not found.", "error")
        return redirect(url_for('list_vehicles'))
    return render_template('view_vehicle.html', vehicle=vehicle)

@app.route('/vehicles/add', methods=['GET', 'POST'])
@admin_required
@login_required
def add_vehicle():
    if request.method == 'POST':
        vehicle_id = request.form.get('vehicle_id')
        if not vehicle_id:
            flash("Vehicle ID is required.", "error")
            return redirect(url_for('add_vehicle'))
        if vehicle_id in vehicles:
            flash("Vehicle ID already exists.", "error")
            return redirect(url_for('add_vehicle'))
        vehicles[vehicle_id] = {
            'make': request.form.get('make'),
            'model': request.form.get('model'),
            'year': request.form.get('year'),
        }
        save_data()
        flash("Vehicle added successfully.", "success")
        return redirect(url_for('view_vehicle', vehicle_id=vehicle_id))
    return render_template('add_vehicle.html')

@app.route('/vehicles/<vehicle_id>/edit', methods=['GET', 'POST'])
@admin_required
@login_required
def edit_vehicle(vehicle_id):
    vehicle = vehicles.get(vehicle_id)
    if not vehicle:
        flash("Vehicle not found.", "error")
        return redirect(url_for('list_vehicles'))
    if request.method == 'POST':
        vehicle['make'] = request.form.get('make')
        vehicle['model'] = request.form.get('model')
        vehicle['year'] = request.form.get('year')
        save_data()
        flash("Vehicle updated successfully.", "success")
        return redirect(url_for('view_vehicle', vehicle_id=vehicle_id))
    return render_template('edit_vehicle.html', vehicle=vehicle)

@app.route('/vehicles/<vehicle_id>/delete', methods=['POST'])
@admin_required
@login_required
def delete_vehicle(vehicle_id):
    if vehicle_id in vehicles:
        del vehicles[vehicle_id]
        save_data()
        flash("Vehicle deleted successfully.", "success")
    else:
        flash("Vehicle not found.", "error")
    return redirect(url_for('list_vehicles'))

# Initialize services and load data before the first request
init_google_services()
load_data()
