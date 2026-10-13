from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import datetime

app = Flask(__name__)
app.secret_key = 'apex_global_fintech_secure_key_2026'


# Database Initialization
def init_db():
    conn = sqlite3.connect('platform.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 1000.00
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'Completed',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# Core Routes
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    conn = sqlite3.connect('platform.db')
    conn.row_factory = sqlite3.Row
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    transactions = conn.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC',
                                (session['user_id'],)).fetchall()
    conn.close()
    return render_template('dashboard.html', user=user, transactions=transactions)


# Auth Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = generate_password_hash(data.get('password'))

    try:
        conn = sqlite3.connect('platform.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        session['user_id'] = user_id
        return jsonify({'status': 'success', 'message': 'Registration successful'})
    except sqlite3.IntegrityError:
        return jsonify({'status': 'error', 'message': 'Username or Email already exists'}), 400


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = sqlite3.connect('platform.db')
    conn.row_factory = sqlite3.Row
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password'], password):
        session['user_id'] = user['id']
        return jsonify({'status': 'success', 'message': 'Login successful'})
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# Transaction Routes
@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    amount = float(request.json.get('amount', 0))
    if amount <= 0:
        return jsonify({'status': 'error', 'message': 'Invalid amount'}), 400

    conn = sqlite3.connect('platform.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE id = ?', (amount, session['user_id']))
    cursor.execute('INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)',
                   (session['user_id'], 'Deposit', amount))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f'Deposited ${amount:.2f}'})


@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    amount = float(request.json.get('amount', 0))

    conn = sqlite3.connect('platform.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    user = cursor.execute('SELECT balance FROM users WHERE id = ?', (session['user_id'],)).fetchone()

    if amount <= 0 or user['balance'] < amount:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Insufficient funds or invalid amount'}), 400

    cursor.execute('UPDATE users SET balance = balance - ? WHERE id = ?', (amount, session['user_id']))
    cursor.execute('INSERT INTO transactions (user_id, type, amount) VALUES (?, ?, ?)',
                   (session['user_id'], 'Withdrawal', amount))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'message': f'Withdrew ${amount:.2f}'})


if __name__ == '__main__':
    app.run(debug=True)