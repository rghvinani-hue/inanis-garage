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

# File to save Google Drive backup file ID
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

# Helper functions for backup file id persistence
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

    # Restore backup if local data missing and Drive enabled
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

    # Backup to Drive
    if google_enabled and driveservice:
        try:
            backup_id, backup_link = upload_file_to_drive(DATA_FILE)
            if backup_id:
                logger.info(f"✅ Data backup saved to Drive: {backup_id}")
                save_backup_file_id(backup_id)  # Save backup ID locally
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

# Initialize Google services and load data on app start
init_google_services()
load_data()

# ─── ROUTES ─────────────────────────────────
# (Your existing routes go below)
