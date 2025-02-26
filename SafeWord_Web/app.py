from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_bcrypt import Bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure key
bcrypt = Bcrypt(app)

# Define the database path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, 'database')
DATABASE = os.path.join(DATABASE_DIR, 'safeword.db')

# Create the directory if it doesn't exist
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            safe_word TEXT DEFAULT 'help'
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS emergency_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# Twilio credentials (replace with your own)
TWILIO_ACCOUNT_SID = 'ABCD'
TWILIO_AUTH_TOKEN = 'EFGH'
TWILIO_PHONE_NUMBER = '+12******'
EMERGENCY_CONTACT_NUMBER = '+91*********'  # Replace with actual number

# Email configuration (replace with your email credentials)
EMAIL_ADDRESS = 'abc@gmail.com'
EMAIL_PASSWORD = 'xyz'

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        send_contact_email(name, email, message)
        return redirect(url_for('home'))
    return render_template('contact.html')

@app.route('/set_safe_word', methods=['POST'])
def set_safe_word():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "User not logged in"}), 401

    safe_word = request.json.get('safe_word', 'help')
    conn = get_db_connection()
    conn.execute('UPDATE users SET safe_word = ? WHERE id = ?', (safe_word, session['user_id']))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "safe_word": safe_word})

@app.route('/trigger_emergency', methods=['POST'])
def trigger_emergency():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "User not logged in"}), 401

    data = request.json
    location = data.get('location', 'Unknown Location')

    # Send SMS alert
    send_sms(f"Emergency! I need help. My location: {location}")

    # Send email alerts to all emergency contacts
    send_emails(session['user_id'], f"Emergency! I need help. My location: {location}")

    return jsonify({"status": "success", "message": "Alert sent!"})

def send_sms(message):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    try:
        message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=EMERGENCY_CONTACT_NUMBER
        )
        print(f"SMS sent: Emergency! I need help.")
    except Exception as e:
        print(f"Failed to send SMS: {e}")

def send_emails(user_id, message):
    conn = get_db_connection()
    emergency_emails = conn.execute('''
        SELECT email FROM emergency_emails WHERE user_id = ?
    ''', (user_id,)).fetchall()
    conn.close()

    for row in emergency_emails:
        emergency_email = row['email']
        subject = "Emergency Alert from SafeWord"
        body = message

        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = emergency_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, emergency_email, msg.as_string())
            server.quit()
            print(f"Email sent to {emergency_email}!")
        except Exception as e:
            print(f"Failed to send email to {emergency_email}: {e}")

def send_contact_email(name, email, message):
    subject = "New Contact Form Submission"
    body = f"Name: {name}\nEmail: {email}\nMessage: {message}"

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, EMAIL_ADDRESS, msg.as_string())
        server.quit()
        print("Contact email sent!")
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        print("User not logged in. Redirecting to login page.")
        flash('Please log in to access this page.', 'error')
        return redirect(url_for('login'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if user:
        print(f"User found: {user['email']}")
        return render_template('profile.html', user=user)
    else:
        print("User not found in the database.")
        flash('User not found.', 'error')
        return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        emergency_emails = request.form.get('emergency_emails')  # Get comma-separated emergency emails
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        conn = get_db_connection()
        try:
            # Insert user into the users table
            cursor = conn.execute('''
                INSERT INTO users (email, password)
                VALUES (?, ?)
            ''', (email, hashed_password))
            user_id = cursor.lastrowid  # Get the ID of the newly created user

            # Insert emergency emails into the emergency_emails table
            for emergency_email in emergency_emails.split(','):
                emergency_email = emergency_email.strip()  # Remove leading/trailing spaces
                conn.execute('''
                    INSERT INTO emergency_emails (user_id, email)
                    VALUES (?, ?)
                ''', (user_id, emergency_email))

            conn.commit()
            flash('Signup successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists. Please use a different email.', 'error')
        finally:
            conn.close()

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('profile'))  # Redirect to profile page
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db() 
    app.run(debug=True)