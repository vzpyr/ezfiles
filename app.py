from datetime import datetime, timedelta, timezone
from flask import Flask, request, render_template, jsonify, send_from_directory, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import json
import os
import random
import string
from werkzeug.utils import secure_filename

# definitions
uploadfolder = 'ezfiles'
os.makedirs(uploadfolder, exist_ok=True)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = uploadfolder
app.secret_key = '3q2H^Z*YXA6HMKy79tY7'

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per day"]
)

# functions
def load_files():
    if os.path.exists('files.json'):
        with open('files.json', 'r') as f:
            return json.load(f) or []
    return []

def load_bans():
    if os.path.exists('bans.json'):
        with open('bans.json', 'r') as f:
            bans = json.load(f)
            current_time = datetime.now(timezone.utc)
            active_bans = {}
            for ip, ban_time in bans.items():
                if datetime.fromisoformat(ban_time) > current_time:
                    active_bans[ip] = ban_time
            if len(active_bans) != len(bans):
                with open('bans.json', 'w') as f:
                    json.dump(active_bans, f, indent=4)
            return active_bans
    return {}

def save_files(files):
    with open('files.json', 'w') as f:
        json.dump(files, f, indent=4)

@app.before_request
def check_if_banned():
    if request.remote_addr in load_bans():
        return '''<!DOCTYPE html>
<html>
    <head>
    <title>access denied</title>
    <style>
        body {
            background-color: #121212;
            color: #ffffff;
            font-family: Consolas, monospace;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
    </style>
    </head>
    <body>
    <text style="color: #ff0000; font-size: 2em;">access denied</text>
    <text style="color: #a0a0a0;">your ip has been banned for breaking the tos.</text>
    </body>
</html>''', 403

# hidden routes
@app.route('/upload', methods=['POST'])
@limiter.limit("60 per hour")
@limiter.limit("5 per minute")
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'no selected file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'no selected file'}), 400
    original_extension = os.path.splitext(file.filename)[1]
    file_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    stored_filename = f"{file_id}{original_extension}"
    deletion_key = ''.join(str(random.randint(0, 9)) for _ in range(6))
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], stored_filename))
    files = load_files()
    options = json.loads(request.form.get('options', '{}'))
    expiration_days = int(options.get('expirationDays', 30))
    max_downloads = options.get('maxDownloads')
    password = options.get('password')
    files.append({
        'file': file.filename,
        'id': file_id,
        'uploader': request.remote_addr,
        'deletion_key': deletion_key,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'expires': (datetime.now(timezone.utc) + timedelta(days=expiration_days)).isoformat(),
        'max_downloads': max_downloads,
        'downloads': 0,
        'password': password
    })
    save_files(files)
    return jsonify({
        'message': 'file uploaded successfully',
        'download_url': f'/dl/{file_id}',
        'deletion_key': deletion_key
    })

@app.route('/get/<file_id>')
@limiter.limit("300 per hour")
@limiter.limit("10 per minute")
def get(file_id):
    files = load_files()
    file_info = next((f for f in files if f['id'] == file_id), None)
    if not file_info:
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if datetime.fromisoformat(file_info['expires']) < datetime.now(timezone.utc):
        delete_file(file_id, False)
        files = [f for f in files if f['id'] != file_id]
        save_files(files)
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if file_info['max_downloads'] and file_info['downloads'] >= file_info['max_downloads']:
        delete_file(file_id, False)
        files = [f for f in files if f['id'] != file_id]
        save_files(files)
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if file_info.get('password'):
        provided_password = request.args.get('password')
        if provided_password != file_info['password']:
            return render_template('error.html', error_code=403, error_message="password required"), 403
    file_info['downloads'] += 1
    save_files(files)
    original_extension = os.path.splitext(file_info['file'])[1]
    stored_filename = f"{file_id}{original_extension}"
    return send_from_directory(
        app.config['UPLOAD_FOLDER'], 
        stored_filename,
        as_attachment=True,
        download_name=file_info['file']
    )

@app.route('/report', methods=['POST'])
@limiter.limit("10 per hour")
def report_file():
    data = request.json
    file_id = data.get('fileId')
    reason = data.get('reason')
    reports = []
    if os.path.exists('reports.json'):
        with open('reports.json', 'r') as f:
            reports = json.load(f)
    reports.append({
        'file_id': file_id,
        'reason': reason,
        'reporter_ip': request.remote_addr,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    with open('reports.json', 'w') as f:
        json.dump(reports, f, indent=4)
    return jsonify({'message': 'report submitted successfully.'}), 200

def delete_file(file_id, require_key=True):
    files = load_files()
    file_info = next((f for f in files if f['id'] == file_id), None)
    if not file_info:
        return False
    if require_key:
        deletion_key = request.json.get('key') if request.is_json else None
        if file_info['deletion_key'] != deletion_key:
            return False
    original_extension = os.path.splitext(file_info['file'])[1]
    stored_filename = f"{file_id}{original_extension}"
    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], stored_filename))
    files = [f for f in files if f['id'] != file_id]
    save_files(files)
    return True

@app.route('/check-password/<file_id>', methods=['POST'])
def check_password(file_id):
    data = request.json
    files = load_files()
    file_info = next((f for f in files if f['id'] == file_id), None)
    if not file_info:
        return jsonify({'valid': False})
    if data.get('password') == file_info.get('password'):
        session[f'file_access_{file_id}'] = True
        return jsonify({'valid': True})
    return jsonify({'valid': False})

# viewable routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dl/<file_id>')
def download(file_id):
    files = load_files()
    file_info = next((f for f in files if f['id'] == file_id), None)
    if not file_info:
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if datetime.fromisoformat(file_info['expires']) < datetime.now(timezone.utc):
        delete_file(file_id, False)
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if file_info['max_downloads'] and file_info['downloads'] >= file_info['max_downloads']:
        delete_file(file_id, False)
        return render_template('error.html', error_code=404, error_message="file not found"), 404
    if file_info.get('password') and not session.get(f'file_access_{file_id}'):
        return render_template('download.html', 
                             file_info={'id': file_id, 'password': True}, 
                             os=os,
                             config=app.config,
                             datetime=datetime,
                             timezone=timezone)
    return render_template('download.html', 
                         file_info=file_info, 
                         os=os,
                         config=app.config,
                         datetime=datetime,
                         timezone=timezone)

@app.route('/tos')
def tos():
    return render_template('tos.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html', error_code=404, error_message="page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error_code=500, error_message="internal server error"), 500

# main function
if __name__ == '__main__':
    app.run()
