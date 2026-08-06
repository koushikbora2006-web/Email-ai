import sqlite3
import os
import time
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "email_ai.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users & OTP table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            used INTEGER DEFAULT 0
        )
    ''')

    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            prompt TEXT NOT NULL,
            subject TEXT,
            body TEXT NOT NULL,
            model TEXT NOT NULL,
            tone TEXT,
            length TEXT,
            rag_used INTEGER DEFAULT 0,
            ocr_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Saved emails table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            tone TEXT,
            category TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Templates table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            prompt TEXT NOT NULL,
            default_subject TEXT
        )
    ''')

    # Knowledge Base / RAG Documents
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            content TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # App Settings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT UNIQUE NOT NULL,
            ollama_url TEXT DEFAULT 'http://localhost:11434',
            default_model TEXT DEFAULT 'llama3',
            sender_name TEXT DEFAULT '',
            sender_email TEXT DEFAULT '',
            receiver_name TEXT DEFAULT 'Manager / Recipient',
            receiver_email TEXT DEFAULT 'recipient@example.com',
            smtp_server TEXT DEFAULT 'smtp.gmail.com',
            smtp_port INTEGER DEFAULT 587,
            smtp_user TEXT DEFAULT '',
            brevo_api_key TEXT DEFAULT '',
            default_signature TEXT DEFAULT 'Best regards,\nKoushik'
        )
    ''')

    # Migration check for new columns in settings
    cursor.execute("PRAGMA table_info(settings)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'receiver_name' not in columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN receiver_name TEXT DEFAULT 'Manager / Recipient'")
    if 'receiver_email' not in columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN receiver_email TEXT DEFAULT 'recipient@example.com'")
    if 'brevo_api_key' not in columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN brevo_api_key TEXT DEFAULT ''")
    if 'profile_picture' not in columns:
        cursor.execute("ALTER TABLE settings ADD COLUMN profile_picture TEXT DEFAULT ''")

    # Insert default templates if table is empty
    cursor.execute('SELECT COUNT(*) FROM email_templates')
    if cursor.fetchone()[0] == 0:
        default_templates = [
            ("Job Application Email", "Career", "Write a professional job application email for a Senior Developer role highlighting my experience in Python, AI, and cloud systems.", "Application for Senior Software Developer Position"),
            ("3-Day Sick Leave Request", "HR / Internal", "Create a formal leave request email to my manager asking for 3 days leave due to medical reasons.", "Leave Application - 3 Days"),
            ("Resignation Notice Email", "HR / Internal", "Draft a polite and professional two-week resignation notice email to my manager and HR.", "Formal Resignation Notice - [Your Name]"),
            ("Salary Review / Promotion Request", "Career", "Create a persuasive email requesting a performance and salary review based on my recent accomplishments.", "Request for Performance & Salary Review"),
            ("Interview Follow-Up & Thank You", "Career", "Write a thoughtful thank-you email following up after a recent job interview.", "Thank You - Interview for [Job Title]"),
            ("Job Referral Request", "Career", "Draft an email asking a former colleague or connection for a professional referral for a new job opportunity.", "Inquiry Regarding Professional Referral"),
            ("Project Follow-up Email", "Business", "Draft a friendly yet firm follow-up email regarding the pending project review and deliverables.", "Follow-up: Project Review & Deliverables Status"),
            ("Meeting Request Email", "Business", "Create a concise email inviting team leads to a quarterly strategy meeting next Tuesday.", "Invitation: Quarterly Strategy & Planning Meeting"),
            ("Project Status & Milestone Update", "Business", "Write a structured project status update email detailing current progress, upcoming milestones, and risks.", "Project Status Update: [Project Name]"),
            ("Cold Sales Pitch / Outreach", "Sales", "Write a compelling cold outreach email offering our software services to prospective business clients.", "Streamlining Your Team Workflow - Quick Inquiry"),
            ("Product Demo Invitation", "Sales", "Draft an engaging invitation email inviting a prospect to a live demonstration of our new AI platform.", "Exclusive Invitation: Live Product Demo"),
            ("Client Onboarding Welcome", "Business", "Draft a warm welcome email to a new client detailing next steps and key contact details.", "Welcome to [Company Name] - Getting Started"),
            ("Contract / Agreement Renewal Notice", "Legal / Business", "Write a professional email notifying a client that their annual service contract is up for renewal.", "Upcoming Contract Renewal Notice"),
            ("Overdue Invoice / Payment Reminder", "Finance", "Write a polite yet firm payment reminder email for an overdue invoice.", "Reminder: Invoice #[Number] Overdue Payment"),
            ("Budget Approval Request", "Finance", "Draft a clear justification email requesting department budget approval for new software tools.", "Budget Approval Request: New Productivity Tools"),
            ("Client Complaint Response", "Customer Support", "Write a polite and empathetic email addressing a client complaint about delayed service delivery and offering a resolution.", "Response to your recent service feedback"),
            ("Service Outage / Maintenance Notice", "Customer Support", "Write an urgent yet reassuring email informing users of scheduled system maintenance and temporary downtime.", "Scheduled Service Maintenance Notice"),
            ("Product Feedback Request", "Customer Support", "Draft a short, friendly email asking users for feedback on their recent product experience.", "We'd love your feedback on your recent experience")
        ]
        cursor.executemany(
            'INSERT INTO email_templates (title, category, prompt, default_subject) VALUES (?, ?, ?, ?)',
            default_templates
        )

    # Insert default admin user if not exists
    cursor.execute('SELECT COUNT(*) FROM users WHERE email = ?', ('koushik@example.com',))
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO users (email) VALUES (?)', ('koushik@example.com',))
        cursor.execute(
            'INSERT INTO settings (user_email, ollama_url, default_model) VALUES (?, ?, ?)',
            ('koushik@example.com', 'http://localhost:11434', 'llama3')
        )

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully.")
