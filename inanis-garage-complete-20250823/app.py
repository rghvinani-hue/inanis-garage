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

# ─── Configuration ──────────────────────────────────────────────────────────
os.makedirs('logs', exist_ok=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

DATA_DIR = 'data'
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, 'inanis_garage_data.pickle')

# ─── In-Memory Data (persisted via pickle) ─────────────────────────────────
users = {}
vehicles = {}
assignments = []
fuel_logs = {}
documents = {}
maintenance_records = {}

# ─── Google Drive / Calendar Setup ─────────────────────────────────────────
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
            "private_key": os.environ.get('GOOGLE_PRIVATE_KEY','').replace('\\n','\n'),
            "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
            "client_id": os.environ.get('GOOGLE_CLIENT_ID'),
            "auth_uri":"https://accounts.google.com/o/oauth2/auth",
            "token_uri":"https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url":os.environ.get('GOOGLE_CLIENT_CERT_URL')
        }
        if creds['project_id'] and creds['client_email'] and creds['private_key']:
            return creds
        return None
    except Exception as e:
        logger.error(f"Load Google creds failed: {e}")
        return None

def init_google_services():
    global driveservice, calservice, google_enabled
    creds = get_google_credentials()
    if not creds:
        logger.info("Google disabled")
        return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        credentials = service_account.Credentials.from_service_account_info(
            creds, scopes=['https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/calendar']
        )
        driveservice = build('drive','v3',credentials=credentials)
        calservice = build('calendar','v3',credentials=credentials)
        google_enabled = True
        logger.info("Google services initialized")
    except Exception as e:
        logger.error(f"Google init failed: {e}")

def upload_file_to_drive(path):
    if not google_enabled:
        return None, None
    try:
        from googleapiclient.http import MediaFileUpload
        meta={'name':os.path.basename(path),
              'parents':[os.environ.get('GOOGLE_DRIVE_FOLDER_ID','root')]}
        media=MediaFileUpload(path,resumable=True)
        f=driveservice.files().create(body=meta,media_body=media,fields='id,webViewLink').execute()
        driveservice.permissions().create(fileId=f['id'],body={'type':'anyone','role':'reader'}).execute()
        return f['id'],f['webViewLink']
    except Exception as e:
        logger.error(f"Drive upload error: {e}")
        flash(f"⚠️ Drive upload failed: {e}", "warning")
        return None, None

def create_calendar_event(summary, desc, start, end):
    if not google_enabled:
        return None
    try:
        ev={'summary':summary,'description':desc,'start':{'date':start},'end':{'date':end}}
        e=calservice.events().insert(calendarId='primary',body=ev).execute()
        return e.get('htmlLink')
    except Exception as e:
        logger.error(f"Calendar error: {e}")
        return None

# ─── Data Persistence ────────────────────────────────────────────────────────
def load_data():
    global users, vehicles, assignments, fuel_logs, documents, maintenance_records
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE,'rb') as f:
                data=pickle.load(f)
                users=data.get('users',{})
                vehicles=data.get('vehicles',{})
                assignments=data.get('assignments',[])
                fuel_logs=data.get('fuel_logs',{})
                documents=data.get('documents',{})
                maintenance_records=data.get('maintenance_records',{})
        except Exception as e:
            logger.error(f"Load data failed: {e}")
    if not users:
        users={"admin":{"password":generate_password_hash("adminpass"),"role":"admin","created_date":datetime.now().isoformat()}}
        save_data()

def save_data():
    try:
        data={'users':users,'vehicles':vehicles,'assignments':assignments,
              'fuel_logs':fuel_logs,'documents':documents,'maintenance_records':maintenance_records}
        with open(DATA_FILE,'wb') as f:
            pickle.dump(data,f)
    except Exception as e:
        logger.error(f"Save data failed: {e}")

# ─── Authentication ──────────────────────────────────────────────────────────
class User(UserMixin):
    def __init__(self,u,r):
        self.id=u;self.role=r

@login_manager.user_loader
def load_user(uid):
    u=users.get(uid)
    return User(uid,u['role']) if u else None

def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if not current_user.is_authenticated or current_user.role!='admin':
            flash("Admin only","error");return redirect(url_for('index'))
        return f(*a,**k)
    return w

# ─── Routes ─────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    today=datetime.today().strftime("%Y-%m-%d")
    avail=assign=0;status={}
    expiring=[]
    for vid in vehicles:
        who="Available"
        for a in assignments:
            if a['car_id']==vid and a['start_date']<=today<=a['end_date']:
                who=a['driver'];break
        status[vid]=who
        avail+=who=="Available";assign+=who!="Available"
        for d in documents.get(vid,[]):
            if d.get('expiry'):
                days=(datetime.strptime(d['expiry'],'%Y-%m-%d').date()-datetime.now().date()).days
                if -7<=days<=30: expiring.append({'car_id':vid,'doc':d['type'],'days':days})
    return render_template('index.html',vehicles=vehicles,status=status,
                           role=current_user.role,available_count=avail,
                           assigned_count=assign,expiring_docs=expiring[:5])

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u,p=request.form['username'],request.form['password']
        user=users.get(u)
        if user and check_password_hash(user['password'],p):
            login_user(User(u,user['role']))
            flash(f"Welcome {u}!","success");return redirect(url_for('index'))
        flash("Invalid login","error")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user();flash("Logged out","success");return redirect(url_for('login'))

@app.route('/add_vehicle',methods=['GET','POST'])
@login_required@admin_required
def add_vehicle():
    if request.method=='POST':
        vid=request.form['reg_no'].strip().upper()
        if vid in vehicles:
            flash("Exists","error");return render_template('add_vehicle.html')
        make,model,year,color = [request.form[k].strip() for k in ('make','model','year','color')]
        odo=float(request.form['odo']);desc=request.form['desc'].strip()
        thumbnail_url=None;thumb=request.files.get('car_thumbnail')
        if thumb and thumb.filename:
            fn=secure_filename(thumb.filename);ts=datetime.now().strftime("%Y%m%d_%H%M%S")
            name=f"car_{vid}_{ts}_{fn}"
            d=os.path.join('static','car_thumbnails');os.makedirs(d,exist_ok=True)
            path=os.path.join(d,name);thumb.save(path)
            thumbnail_url=url_for('static',filename=f'car_thumbnails/{name}')
        vehicles[vid]={"make":make,"model":model,"year":int(year),"reg_no":vid,
                      "color":color,"odo":odo,"desc":desc,
                      "created_date":datetime.now().isoformat(),"garage":"Inanis Garage",
                      "thumbnail_url":thumbnail_url}
        save_data();flash("Vehicle added","success");return redirect(url_for('index'))
    return render_template('add_vehicle.html')

@app.route('/vehicle/<car_id>')
@login_required
def vehicle(car_id):
    v = vehicles.get(car_id)
    if not v:
        flash("Vehicle not found.", "error")
        return redirect(url_for('index'))

    docs = documents.get(car_id, [])
    flogs = fuel_logs.get(car_id, [])

    # Calculate overall average mileage
    mileages = [log.get('fuel_efficiency') for log in flogs if log.get('fuel_efficiency')]
    overall_avg_mileage = round(sum(mileages) / len(mileages), 2) if mileages else None

    return render_template('vehicle.html', v=v, docs=docs, flogs=flogs,
                           overall_avg_mileage=overall_avg_mileage,
                           role=current_user.role)


@app.route('/upload_document/<car_id>',methods=['GET','POST'])
@login_required@admin_required
def upload_document(car_id):
    if request.method=='POST':
        f=request.files.get('doc_file');t=request.form.get('doc_type')
        if not f or not t:flash("Select file&type","error");return render_template('add_document.html',car_id=car_id)
        fn=secure_filename(f.filename);ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        name=f"doc_{car_id}_{t.replace(' ','_')}_{ts}_{fn}"
        d=os.path.join('static','documents');os.makedirs(d,exist_ok=True)
        path=os.path.join(d,name);f.save(path)
        url=url_for('static',filename=f'documents/{name}')
        drive_id,drive_link=upload_file_to_drive(path)
        rec={"type":t,"expiry":request.form.get('expiry'),"uploaded_date":datetime.now().isoformat(),
             "drive_link":drive_link,"document_url":url,"original_filename":f.filename}
        documents.setdefault(car_id,[]).append(rec);save_data()
        flash("Document uploaded","success");return redirect(url_for('vehicle',car_id=car_id))
    return render_template('add_document.html',car_id=car_id)

@app.route('/view_document/<car_id>/<filename>')
@login_required
def view_document(car_id,filename):
    if car_id not in vehicles:flash("Not found","error");return redirect(url_for('index'))
    for d in ['static/documents','static/car_thumbnails','temp_uploads']:
        path=os.path.join(d,filename)
        if os.path.exists(path):return send_file(path)
    flash("File missing","error");return redirect(url_for('vehicle',car_id=car_id))

@app.route('/add_user',methods=['GET','POST'])
@login_required@admin_required
def add_user():
    if request.method=='POST':
        u,p,r=request.form['username'],request.form['password'],request.form['role']
        if u in users:flash("Exists","error");return render_template('add_user.html')
        users[u]={'password':generate_password_hash(p),'role':r,'created_date':datetime.now().isoformat()}
        save_data();flash("User added","success");return redirect(url_for('index'))
    return render_template('add_user.html')

if __name__=="__main__":
    for d in ['temp_uploads','static/css','static/documents','static/car_thumbnails','templates']:
        os.makedirs(d,exist_ok=True)
    init_google_services();load_data()
    app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=False)
