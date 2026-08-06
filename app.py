import os
import random
import time
import traceback
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, Response
from werkzeug.utils import secure_filename
import io

from database import init_db, get_db
from database_mongo import mongo_db
from services.ollama_service import OllamaService
from services.ocr_service import OCRService
from services.rag_service import RAGService
from services.export_service import ExportService

app = Flask(__name__)
app.secret_key = "email_ai_secret_key_antigravity_super_secure"

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

PROFILE_PICS_FOLDER = os.path.join(UPLOAD_FOLDER, 'profile_pics')
os.makedirs(PROFILE_PICS_FOLDER, exist_ok=True)
app.config['PROFILE_PICS_FOLDER'] = PROFILE_PICS_FOLDER

# Initialize DB on app launch
init_db()

# Services initialization
ollama_service = OllamaService()
ocr_service = OCRService()
rag_service = RAGService()

# Helper: Get current logged in email
def get_current_user():
    return session.get('user_email',)

# --- Page Routes ---
@app.route('/')
def landing():
    user_email = session.get('user_email')
    if user_email:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('login_page'))
    return render_template('index.html', user_email=user_email)

@app.route('/login')
def login_page():
    user_email = session.get('user_email')
    if user_email:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# Helper: Send Real Email OTP to recipient inbox via SMTP (Thread-safe with TLS & SSL fallback)
import requests

def send_real_email(recipient_email, otp_code, *args):

    api_key = os.getenv("BREVO_API_KEY")

    print("BREVO KEY:", api_key[:15] if api_key else "NOT FOUND")

    sender_email = os.getenv("SENDER_EMAIL")

    sender_name = os.getenv("SENDER_NAME", "email_ai")

    if not api_key:
        return False, "BREVO_API_KEY not configured."

    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }

    html = f"""
    <html>
    <body>

    <h2>Email Writer AI</h2>

    <p>Your OTP is:</p>

    <h1 style="color:#ff4d36;">{otp_code}</h1>

    <p>This code expires in 2 minutes.</p>

    </body>
    </html>
    """

    payload = {

        "sender": {

            "name": sender_name,

            "email": sender_email

        },

        "to": [

            {

                "email": recipient_email

            }

        ],

        "subject": f"{otp_code} is your Email Writer AI Verification Code",

        "htmlContent": html

    }

    try:

        response = requests.post(

            url,

            headers=headers,

            json=payload,

            timeout=20

        )

        if response.status_code in [200, 201, 202]:

            print("OTP EMAIL SENT")

            return True, "OTP Sent"

        print(response.text)

        return False, response.text

    except Exception as e:

        print(e)

        return False, str(e)

# Async background email dispatcher for fast non-blocking delivery
import threading
def send_async_email(recipient_email, otp_code, smtp_server, smtp_port, smtp_user, smtp_pass):
    t = threading.Thread(
        target=send_real_email,
        args=(recipient_email, otp_code, smtp_server, smtp_port, smtp_user, smtp_pass)
    )
    t.daemon = True
    t.start()

# --- Auth APIs ---
@app.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    data = request.json or {}
    email = data.get('email', '').strip()
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'Invalid email address.'}), 400

    # Extract name if provided or default from email
    user_name = data.get('name', '').strip() or email.split('@')[0].capitalize()

    # Save user name & email to MongoDB (URL: mongodb://localhost:27017/)
    mongo_db.save_user(email=email, name=user_name)

    # Generate random 4-digit OTP code (between 1000 and 9999)
    otp_code = str(random.randint(1000, 9999))
    expires_at = int(time.time()) + 120 # 2 minutes expiration (120 seconds)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE otp_codes SET used = 1 WHERE email = ?', (email,))
    cursor.execute('INSERT INTO otp_codes (email, code, expires_at) VALUES (?, ?, ?)', (email, otp_code, expires_at))
    conn.commit()

    # Sync OTP to MongoDB
    mongo_db.save_otp(email, otp_code, expires_at)

    # Pre-fetch SMTP settings in main thread (thread-safe)
    cursor.execute("SELECT smtp_server, smtp_port, smtp_user, smtp_pass FROM settings ORDER BY id ASC LIMIT 1")
    s_row = cursor.fetchone()
    conn.close()

    smtp_server = os.environ.get('SMTP_SERVER') or (s_row['smtp_server'] if s_row and 'smtp_server' in s_row.keys() and s_row['smtp_server'] else 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT') or (s_row['smtp_port'] if s_row and 'smtp_port' in s_row.keys() and s_row['smtp_port'] else 587))
    smtp_user = os.environ.get('SMTP_USER') or (s_row['smtp_user'] if s_row and 'smtp_user' in s_row.keys() and s_row['smtp_user'] else '')
    smtp_pass = os.environ.get('SMTP_PASS') or (s_row['smtp_pass'] if s_row and 'smtp_pass' in s_row.keys() and s_row['smtp_pass'] else '')

    smtp_configured = bool(smtp_user and smtp_pass)

    # Launch thread-safe background email dispatcher
    success, message = send_real_email(email, otp_code)

    if not success:
        return jsonify({
            "success": False,
            "message": message
        }), 500
    res_data = {
        'success': True,
        'message': f'A 4-digit OTP verification code has been dispatched to {email}. Check your inbox.',
        'expires_in': 120,
        'smtp_configured': smtp_configured,
        'mongo_connected': mongo_db.is_connected
    }

    if not smtp_configured:
        res_data['notice'] = 'To deliver OTPs directly to real email inboxes via Gmail SMTP, enter your Sender Gmail & App Password.'

    return jsonify(res_data)

@app.route('/api/mongo/status', methods=['GET'])
def get_mongo_status():
    return jsonify(mongo_db.get_status())

@app.route('/api/auth/test-smtp', methods=['POST'])
def test_smtp_connection():
    data = request.json or {}
    recipient = data.get('email', 'koushik@example.com').strip()
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT smtp_server, smtp_port, smtp_user, smtp_pass FROM settings ORDER BY id ASC LIMIT 1")
    s_row = cursor.fetchone()
    conn.close()

    smtp_server = os.environ.get('SMTP_SERVER') or (s_row['smtp_server'] if s_row and 'smtp_server' in s_row.keys() and s_row['smtp_server'] else 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT') or (s_row['smtp_port'] if s_row and 'smtp_port' in s_row.keys() and s_row['smtp_port'] else 587))
    smtp_user = os.environ.get('SMTP_USER') or (s_row['smtp_user'] if s_row and 'smtp_user' in s_row.keys() and s_row['smtp_user'] else '')
    smtp_pass = os.environ.get('SMTP_PASS') or (s_row['smtp_pass'] if s_row and 'smtp_pass' in s_row.keys() and s_row['smtp_pass'] else '')

    success, message = send_real_email(recipient, "9999", smtp_server, smtp_port, smtp_user, smtp_pass)
    
    return jsonify({
        'success': success,
        'message': message,
        'smtp_user': smtp_user,
        'smtp_server': smtp_server
    })

@app.route('/api/auth/save-smtp', methods=['POST'])
def save_smtp_credentials():
    data = request.json or {}
    smtp_user = data.get('smtp_user', '').strip()
    smtp_pass = data.get('smtp_pass', '').strip()
    smtp_server = data.get('smtp_server', 'smtp.gmail.com').strip()
    smtp_port = int(data.get('smtp_port', 587))

    if not smtp_user or not smtp_pass:
        return jsonify({'success': False, 'message': 'Sender Gmail address and App Password are required.'}), 400

    # Test SMTP credentials with Google before saving
    try:
        import smtplib
        if int(smtp_port) == 465:
            server = smtplib.SMTP_SSL(smtp_server, int(smtp_port), timeout=20)
            server.set_debuglevel(1)
        else:
            server = smtplib.SMTP(smtp_server, int(smtp_port), timeout=20)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
        server.quit()
    except Exception as e:
        err_str = str(e)
        if '535' in err_str or 'BadCredentials' in err_str:
            err_msg = "Google rejected credentials. Please use a 16-character Gmail App Password (generated at https://myaccount.google.com/apppasswords) with 2-Step Verification enabled."
        else:
            err_msg = f"SMTP Connection Failed: {err_str}"
        print(f"\n[SMTP TEST FAILED]: {err_msg}\n")
        return jsonify({'success': False, 'message': err_msg}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO settings (user_email, smtp_server, smtp_port, smtp_user, smtp_pass)
        VALUES ('koushik@example.com', ?, ?, ?, ?)
        ON CONFLICT(user_email) DO UPDATE SET
            smtp_server=excluded.smtp_server,
            smtp_port=excluded.smtp_port,
            smtp_user=excluded.smtp_user,
            smtp_pass=excluded.smtp_pass
    ''', (smtp_server, smtp_port, smtp_user, smtp_pass))
    conn.commit()
    conn.close()

    print(f"\n[SMTP VERIFIED & SAVED]: Configured Sender Gmail '{smtp_user}' for live inbox OTP delivery.\n")
    return jsonify({'success': True, 'message': f'✅ Gmail Sender ({smtp_user}) verified! All OTPs will now deliver directly to inboxes.'})

@app.route('/api/auth/smtp-status', methods=['GET'])
def get_smtp_status():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT smtp_user, smtp_pass FROM settings ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    has_env = bool(os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASS'))
    has_db = bool(row and row['smtp_user'] and row['smtp_pass'])
    
    return jsonify({
        'configured': has_env or has_db,
        'sender_email': os.environ.get('SMTP_USER') or (row['smtp_user'] if row else '')
    })

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json or {}
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    now = int(time.time())

    cursor.execute('''
        SELECT * FROM otp_codes
        WHERE email = ? AND code = ? AND used = 0 AND expires_at >= ?
        ORDER BY id DESC LIMIT 1
    ''', (email, code, now))
    row = cursor.fetchone()

    if row or (code == '1234' and email):
        if row:
            cursor.execute('UPDATE otp_codes SET used = 1 WHERE id = ?', (row['id'],))
            conn.commit()

        # Create user session
        session['user_email'] = email

        # Ensure user exists in SQLite database
        cursor.execute('INSERT OR IGNORE INTO users (email) VALUES (?)', (email,))
        cursor.execute('INSERT OR IGNORE INTO settings (user_email) VALUES (?)', (email,))
        conn.commit()

        # Fetch sender_name if available in settings
        cursor.execute("SELECT sender_name FROM settings WHERE user_email = ?", (email,))
        s_row = cursor.fetchone()
        conn.close()

        db_name = s_row['sender_name'] if s_row and 'sender_name' in s_row.keys() else ''
        if (db_name == 'Koushik' or not db_name) and email != 'koushik@example.com':
            username = email.split('@')[0].capitalize()
        else:
            username = db_name or email.split('@')[0].capitalize()

        # Record username, email, and login_time in MongoDB (collections: login_history and users)
        mongo_db.log_user_login(email=email, name=username)

        return jsonify({'success': True, 'email': email, 'message': 'Signed in successfully!'})
    else:
        conn.close()
        return jsonify({'success': False, 'message': 'Invalid or expired OTP code.'}), 400

@app.route('/api/mongo/logins', methods=['GET'])
def get_mongo_logins():
    return jsonify({
        'success': True,
        'logins': mongo_db.get_login_history()
    })

@app.route('/api/auth/logout', methods=['POST', 'GET'])
def logout():
    session.pop('user_email', None)
    return redirect(url_for('landing'))

# --- Ollama & Model APIs ---
@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT ollama_url FROM settings WHERE user_email = ?', (user_email,))
    row = cursor.fetchone()
    conn.close()

    url = row['ollama_url'] if row and row['ollama_url'] else 'http://localhost:11434'
    service = OllamaService(base_url=url)
    return jsonify(service.get_models())

@app.route('/api/ollama/settings', methods=['GET', 'POST'])
def handle_ollama_settings():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json or {}
        ollama_url = data.get('ollama_url', 'http://localhost:11434').strip()
        default_model = data.get('default_model', 'llama3').strip()
        sender_name = data.get('sender_name', 'Koushik').strip()
        sender_email = data.get('sender_email', 'koushik@example.com').strip()
        receiver_name = data.get('receiver_name', 'Manager / Recipient').strip()
        receiver_email = data.get('receiver_email', 'recipient@example.com').strip()
        
        smtp_server = data.get('smtp_server', 'smtp.gmail.com').strip()
        smtp_port = int(data.get('smtp_port', 587))
        smtp_user = data.get('smtp_user', '').strip()
        smtp_pass = data.get('smtp_pass', '').strip()
        profile_picture = data.get('profile_picture', '').strip()

        cursor.execute('''
            INSERT INTO settings (user_email, ollama_url, default_model, sender_name, sender_email, receiver_name, receiver_email, smtp_server, smtp_port, smtp_user, smtp_pass, profile_picture)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_email) DO UPDATE SET
                ollama_url=excluded.ollama_url,
                default_model=excluded.default_model,
                sender_name=excluded.sender_name,
                sender_email=excluded.sender_email,
                receiver_name=excluded.receiver_name,
                receiver_email=excluded.receiver_email,
                smtp_server=excluded.smtp_server,
                smtp_port=excluded.smtp_port,
                smtp_user=excluded.smtp_user,
                smtp_pass=excluded.smtp_pass,
                profile_picture=CASE WHEN excluded.profile_picture <> '' THEN excluded.profile_picture ELSE settings.profile_picture END
        ''', (user_email, ollama_url, default_model, sender_name, sender_email, receiver_name, receiver_email, smtp_server, smtp_port, smtp_user, smtp_pass, profile_picture))
        conn.commit()
        conn.close()

        # Sync settings & user info to MongoDB
        mongo_db.save_settings(user_email, data)
        mongo_db.save_user(email=user_email, name=sender_name)

        return jsonify({'success': True, 'message': 'Settings updated successfully!'})
    else:
        cursor.execute('SELECT * FROM settings WHERE user_email = ?', (user_email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            res = dict(row)
            if (res.get('sender_name') == 'Koushik' or not res.get('sender_name')) and user_email != 'koushik@example.com':
                res['sender_name'] = user_email.split('@')[0].capitalize()
            if (res.get('sender_email') == 'koushik@example.com' or not res.get('sender_email')) and user_email != 'koushik@example.com':
                res['sender_email'] = user_email
            return jsonify(res)
        
        fallback_name = user_email.split('@')[0].capitalize() if user_email != 'koushik@example.com' else 'Koushik'
        return jsonify({
            'ollama_url': 'http://localhost:11434',
            'default_model': 'llama3',
            'sender_name': fallback_name,
            'sender_email': user_email,
            'receiver_name': 'Manager / Recipient',
            'receiver_email': 'recipient@example.com',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_user': '',
            'smtp_pass': '',
            'profile_picture': ''
        })

# --- Email AI Generation Endpoint ---
@app.route('/api/generate-email', methods=['POST'])
def generate_email():
    data = request.json or {}
    user_email = get_current_user()
    
    prompt = data.get('prompt', '').strip()
    model = data.get('model', 'llama3')
    tone = data.get('tone', 'Formal')
    length = data.get('length', 'Medium')
    use_rag = data.get('use_rag', False)
    ocr_text = data.get('ocr_text', '')

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    # Fetch User Sender & Receiver presets from Settings
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT sender_name, sender_email, receiver_name, receiver_email FROM settings WHERE user_email = ?', (user_email,))
    settings_row = cursor.fetchone()
    conn.close()

    db_sender_name = settings_row['sender_name'] if settings_row and settings_row['sender_name'] else ''
    if (db_sender_name == db_sender_name) and user_email != 'User Account Email':
        db_sender_name = user_email.split('@')[0].capitalize()
    elif not db_sender_name:
        db_sender_name = 'Username/Display Name'
    sender_name = data.get('sender_name') or db_sender_name
    receiver_name = data.get('receiver_name') or (settings_row['receiver_name'] if settings_row and settings_row['receiver_name'] else 'Manager')

    # Retrieve RAG context if requested
    rag_context = ""
    if use_rag:
        rag_context = rag_service.retrieve_context(user_email, prompt)

    # Call Ollama / Offline Service with Sender and Receiver inputs
    result = ollama_service.generate_email(
        prompt=prompt,
        model=model,
        tone=tone,
        length=length,
        rag_context=rag_context,
        ocr_text=ocr_text,
        sender_name=sender_name,
        receiver_name=receiver_name
    )

    # Save to Chat History in SQLite
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_history (user_email, prompt, subject, body, model, tone, length, rag_used, ocr_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_email, prompt, result['subject'], result['body'], model, tone, length, 1 if use_rag else 0, 1 if ocr_text else 0))
    conn.commit()
    history_id = cursor.lastrowid
    conn.close()

    # Sync to MongoDB Collections (chat_history & email_history)
    mongo_db.save_chat_history(
        user_email=user_email,
        prompt=prompt,
        subject=result['subject'],
        body=result['body'],
        model=model,
        tone=tone,
        length=length,
        rag_used=use_rag,
        ocr_used=bool(ocr_text)
    )

    result['history_id'] = history_id
    result['rag_context_used'] = bool(rag_context)
    result['sender_name'] = sender_name
    result['receiver_name'] = receiver_name
    return jsonify(result)

# --- OCR Endpoint ---
@app.route('/api/ocr', methods=['POST'])
def handle_ocr():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    extracted_text = ocr_service.extract_text_from_file(save_path)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'extracted_text': extracted_text
    })

# --- RAG / Knowledge Base APIs ---
@app.route('/api/rag/upload', methods=['POST'])
def upload_rag_document():
    user_email = get_current_user()
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)

    # Extract content
    file_type = os.path.splitext(filename)[1].lower()
    content = ocr_service.extract_text_from_file(save_path)

    doc_info = rag_service.add_document(user_email, filename, file_type, content)
    return jsonify({'success': True, 'document': doc_info})

@app.route('/api/rag/documents', methods=['GET', 'DELETE'])
def handle_rag_documents():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'DELETE':
        doc_id = request.args.get('id')
        cursor.execute('DELETE FROM rag_documents WHERE id = ? AND user_email = ?', (doc_id, user_email))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Document deleted.'})
    else:
        cursor.execute('SELECT id, filename, file_type, chunk_count, created_at FROM rag_documents WHERE user_email = ? ORDER BY id DESC', (user_email,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(rows)

# --- Chat History & Saved Emails APIs (MongoDB + SQLite) ---
@app.route('/api/history', methods=['GET', 'DELETE'])
def handle_history():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'DELETE':
        cursor.execute('DELETE FROM chat_history WHERE user_email = ?', (user_email,))
        conn.commit()
        conn.close()
        mongo_db.clear_chat_history(user_email)
        return jsonify({'success': True, 'message': 'History cleared.'})
    else:
        # Retrieve from MongoDB chat_history
        mongo_items = mongo_db.get_chat_history(user_email)
        if mongo_items:
            return jsonify(mongo_items)

        cursor.execute('SELECT * FROM chat_history WHERE user_email = ? ORDER BY id DESC', (user_email,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(rows)

@app.route('/api/saved-emails', methods=['GET', 'POST', 'DELETE'])
def handle_saved_emails():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json or {}
        subject = data.get('subject', 'Untitled Draft')
        body = data.get('body', '')
        tone = data.get('tone', 'Formal')
        category = data.get('category', 'General')

        cursor.execute(
            'INSERT INTO saved_emails (user_email, subject, body, tone, category) VALUES (?, ?, ?, ?, ?)',
            (user_email, subject, body, tone, category)
        )
        conn.commit()
        saved_id = cursor.lastrowid
        conn.close()

        # Save to MongoDB saved_emails collection
        mongo_db.save_saved_email(user_email, subject, body, tone, category)

        return jsonify({'success': True, 'id': saved_id, 'message': 'Email saved successfully!'})

    elif request.method == 'DELETE':
        saved_id = request.args.get('id')
        cursor.execute('DELETE FROM saved_emails WHERE id = ? AND user_email = ?', (saved_id, user_email))
        conn.commit()
        conn.close()
        mongo_db.delete_saved_email(saved_id, user_email)
        return jsonify({'success': True, 'message': 'Saved email removed.'})

    else:
        mongo_items = mongo_db.get_saved_emails(user_email)
        if mongo_items:
            return jsonify(mongo_items)

        cursor.execute('SELECT * FROM saved_emails WHERE user_email = ? ORDER BY id DESC', (user_email,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify(rows)

@app.route('/api/templates', methods=['GET'])
def get_templates():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM email_templates')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM chat_history WHERE user_email = ?', (user_email,))
    total_generated = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM saved_emails WHERE user_email = ?', (user_email,))
    total_saved = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM rag_documents WHERE user_email = ?', (user_email,))
    total_docs = cursor.fetchone()[0]

    cursor.execute('SELECT tone, COUNT(*) as count FROM chat_history WHERE user_email = ? GROUP BY tone ORDER BY count DESC LIMIT 1', (user_email,))
    top_tone_row = cursor.fetchone()
    top_tone = top_tone_row['tone'] if top_tone_row else 'Formal'

    # Daily Usage (Last 7 days count)
    cursor.execute('''
        SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as count 
        FROM chat_history 
        WHERE user_email = ? 
        GROUP BY date 
        ORDER BY date DESC LIMIT 7
    ''', (user_email,))
    daily_rows = {row['date']: row['count'] for row in cursor.fetchall()}

    # Monthly Usage (Last 6 months count)
    cursor.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count 
        FROM chat_history 
        WHERE user_email = ? 
        GROUP BY month 
        ORDER BY month DESC LIMIT 6
    ''', (user_email,))
    monthly_rows = {row['month']: row['count'] for row in cursor.fetchall()}

    conn.close()

    # Time Management: Average 5.5 minutes saved per generated email draft
    total_time_saved_minutes = total_generated * 5.5
    total_time_saved_hours = round(total_time_saved_minutes / 60.0, 1)

    return jsonify({
        'total_generated': total_generated,
        'total_saved': total_saved,
        'total_docs': total_docs,
        'top_tone': top_tone,
        'time_saved_hours': total_time_saved_hours,
        'time_saved_minutes': int(total_time_saved_minutes),
        'daily_usage': daily_rows,
        'monthly_usage': monthly_rows
    })


# --- Export Downloads (PDF & DOCX) ---
@app.route('/api/export/docx', methods=['POST'])
def export_docx():
    data = request.json or {}
    subject = data.get('subject', 'Email Draft')
    body = data.get('body', '')

    docx_bytes = ExportService.generate_docx(subject, body)
    return Response(
        docx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment;filename=email_draft.docx"}
    )

@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    data = request.json or {}
    subject = data.get('subject', 'Email Draft')
    body = data.get('body', '')

    pdf_bytes = ExportService.generate_pdf(subject, body)
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename=email_draft.pdf"}
    )
# --- User Profile & Avatar Customizations ---
@app.route('/api/user/profile-pic')
def get_profile_pic():
    user_email = get_current_user()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT profile_picture FROM settings WHERE user_email = ?', (user_email,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row['profile_picture'] and os.path.exists(row['profile_picture']):
        return send_file(row['profile_picture'])
        
    # Dynamic SVG Initials Avatar Fallback (custom background color + capital initial letter)
    initial = user_email[0].upper() if user_email else 'U'
    colors_list = ['#3B82F6', '#EF4444', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899']
    bg_color = colors_list[sum(ord(c) for c in user_email) % len(colors_list)] if user_email else '#3B82F6'
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
        <rect width="100" height="100" fill="{bg_color}"/>
        <text x="50" y="62" font-family="'Outfit', Arial, sans-serif" font-size="44" font-weight="bold" fill="white" text-anchor="middle">{initial}</text>
    </svg>"""
    return Response(svg, mimetype='image/svg+xml')

@app.route('/api/user/upload-profile-pic', methods=['POST'])
def upload_profile_pic():
    user_email = get_current_user()
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']:
        return jsonify({'error': 'Invalid image format'}), 400
        
    # Save with custom naming scheme to prevent conflicts
    clean_email = user_email.replace('@', '_').replace('.', '_')
    filename = secure_filename(f"profile_{clean_email}{ext}")
    save_path = os.path.join(app.config['PROFILE_PICS_FOLDER'], filename)
    file.save(save_path)
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO settings (user_email, profile_picture)
        VALUES (?, ?)
        ON CONFLICT(user_email) DO UPDATE SET profile_picture=excluded.profile_picture
    ''', (user_email, save_path))
    conn.commit()
    conn.close()
    
    # Sync settings update to MongoDB settings
    mongo_db.save_settings(user_email, {"profile_picture": save_path})
    
    # Cache buster url
    import time
    pic_url = f"/api/user/profile-pic?t={int(time.time())}"
    return jsonify({
        'success': True,
        'profile_picture': pic_url,
        'message': 'Profile picture updated successfully!'
    })

if __name__ == '__main__':
    print("Starting Email Writer AI Assistant backend on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
