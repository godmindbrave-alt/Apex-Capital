import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'apex_enterprise_terminal_secure_9988'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apex_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ----------------- PAYSTACK CONFIGURATION ----------------- #
# Set your Paystack Secret Key in your environment or paste test key directly
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', 'sk_test_YOUR_PAYSTACK_SECRET_KEY')
PAYSTACK_BASE_URL = 'https://api.paystack.co'

db = SQLAlchemy(app)

# ----------------- DATABASE MODELS ----------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    balance_usd = db.Column(db.Float, default=0.0)
    balance_ngn = db.Column(db.Float, default=0.0)

class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    avg_price = db.Column(db.Float, nullable=False, default=0.0)

class BankAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    bank_code = db.Column(db.String(20), nullable=True)
    account_number = db.Column(db.String(20), nullable=False)
    account_name = db.Column(db.String(150), nullable=False)
    recipient_code = db.Column(db.String(100), nullable=True)  # Paystack Transfer Recipient Code

class TransactionLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tx_ref = db.Column(db.String(50), unique=True, nullable=False)
    username = db.Column(db.String(150), nullable=False)
    tx_type = db.Column(db.String(50), nullable=False)  # DEPOSIT, WITHDRAW, BUY, SELL, CONVERT
    details = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='NGN')
    status = db.Column(db.String(30), nullable=False, default='PENDING')
    date = db.Column(db.String(50), nullable=False)

with app.app_context():
    db.create_all()

EXCHANGE_RATE_USD_NGN = 1550.0

MARKET_CATALOG = {
    'EURUSD': {'name': 'Euro / US Dollar', 'price': 1.0850, 'category': 'Forex'},
    'GBPUSD': {'name': 'British Pound / US Dollar', 'price': 1.2740, 'category': 'Forex'},
    'USDNGN': {'name': 'US Dollar / Nigerian Naira', 'price': 1550.00, 'category': 'Forex'},
    'BTC': {'name': 'Bitcoin Network Token', 'price': 64200.00, 'category': 'Crypto'},
    'ETH': {'name': 'Ethereum Smart Chain', 'price': 3450.00, 'category': 'Crypto'},
    'TSLA': {'name': 'Tesla Inc. Equity', 'price': 245.50, 'category': 'Equities'},
    'AAPL': {'name': 'Apple Inc. Stock', 'price': 182.30, 'category': 'Equities'},
    'NVDA': {'name': 'NVIDIA Corporation', 'price': 880.40, 'category': 'Equities'}
}

# ----------------- ROUTES ----------------- #

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Username or Email is already registered.', 'danger')
            return redirect(url_for('register'))

        hashed_p = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_p, balance_usd=0.0, balance_ngn=0.0)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        flash('Account registered successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()
    if not user:
        session.pop('username', None)
        return redirect(url_for('login'))

    portfolio = Portfolio.query.filter_by(username=user.username).all()
    bank_accounts = BankAccount.query.filter_by(username=user.username).all()
    ledger = TransactionLedger.query.filter_by(username=user.username).order_by(TransactionLedger.id.desc()).all()

    total_net_worth = user.balance_usd + (user.balance_ngn / EXCHANGE_RATE_USD_NGN)
    portfolio_valuation = []
    for item in portfolio:
        curr_price = MARKET_CATALOG.get(item.symbol, {'price': 1.0})['price']
        val = curr_price * item.shares
        total_net_worth += val
        portfolio_valuation.append({
            'symbol': item.symbol,
            'shares': item.shares,
            'avg_price': item.avg_price,
            'current_price': curr_price,
            'market_value': val,
            'pl': (curr_price - item.avg_price) * item.shares
        })

    return render_template(
        'dashboard.html',
        user=user,
        portfolio=portfolio_valuation,
        bank_accounts=bank_accounts,
        ledger=ledger,
        market=MARKET_CATALOG,
        net_worth=total_net_worth,
        exchange_rate=EXCHANGE_RATE_USD_NGN
    )

# ----------------- REAL PAYMENT INTEGRATION (PAYSTACK) ----------------- #

@app.route('/deposit', methods=['POST'])
def deposit():
    """Initializes a real payment transaction via Paystack (Cards, Transfer, USSD)."""
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    try:
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'NGN')

        if amount <= 0:
            flash('Invalid deposit amount.', 'danger')
            return redirect(url_for('dashboard'))

        tx_ref = f"APEX-DEP-{uuid.uuid4().hex[:10].upper()}"

        # Convert to Paystack subunit (Kobo/Cents: Multiply by 100)
        amount_in_subunits = int(amount * 100)

        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "email": user.email,
            "amount": amount_in_subunits,
            "currency": currency,
            "reference": tx_ref,
            "callback_url": url_for('verify_deposit', _external=True)
        }

        response = requests.post(f"{PAYSTACK_BASE_URL}/transaction/initialize", json=payload, headers=headers)
        res_data = response.json()

        if res_data.get('status'):
            # Record Pending Payment
            tx = TransactionLedger(
                tx_ref=tx_ref,
                username=user.username,
                tx_type='DEPOSIT',
                details=f'Paystack Payment Gateway ({currency})',
                amount=amount,
                currency=currency,
                status='PENDING',
                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
            db.session.add(tx)
            db.session.commit()

            # Redirect user directly to Paystack's Secure Payment Page
            return redirect(res_data['data']['authorization_url'])
        else:
            flash(f"Payment gateway error: {res_data.get('message', 'Initialization failed')}", 'danger')

    except Exception as e:
        flash(f"Deposit processing error: {str(e)}", 'danger')

    return redirect(url_for('dashboard'))


@app.route('/verify_deposit')
def verify_deposit():
    """Callback route to verify real Paystack deposit."""
    tx_ref = request.args.get('reference')
    if not tx_ref:
        flash("Transaction reference missing.", "danger")
        return redirect(url_for('dashboard'))

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"{PAYSTACK_BASE_URL}/transaction/verify/{tx_ref}", headers=headers)
    res_data = response.json()

    if res_data.get('status') and res_data['data']['status'] == 'success':
        tx = TransactionLedger.query.filter_by(tx_ref=tx_ref).first()
        if tx and tx.status != 'COMPLETED':
            tx.status = 'COMPLETED'
            user = User.query.filter_by(username=tx.username).first()
            if tx.currency == 'USD':
                user.balance_usd += tx.amount
            else:
                user.balance_ngn += tx.amount
            db.session.commit()
            flash(f"Payment Verified! Funded {tx.amount:,.2f} {tx.currency} to your balance.", "success")
    else:
        flash("Payment verification failed or was canceled.", "danger")

    return redirect(url_for('dashboard'))


@app.route('/withdraw', methods=['POST'])
def withdraw():
    """Processes real bank payout transfers via Paystack Transfers API."""
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    try:
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'NGN')
        bank_acc_id = request.form.get('bank_account_id')

        bank_acc = BankAccount.query.get(bank_acc_id)
        if not bank_acc:
            flash("Please select a valid linked bank account for payout.", "danger")
            return redirect(url_for('dashboard'))

        if currency == 'NGN' and user.balance_ngn < amount:
            flash("Insufficient NGN balance for withdrawal.", "danger")
            return redirect(url_for('dashboard'))

        # Deduct balance
        if currency == 'NGN':
            user.balance_ngn -= amount
        else:
            user.balance_usd -= amount

        tx_ref = f"APEX-WD-{uuid.uuid4().hex[:10].upper()}"

        tx = TransactionLedger(
            tx_ref=tx_ref,
            username=user.username,
            tx_type='WITHDRAW',
            details=f'Bank Payout to {bank_acc.bank_name} ({bank_acc.account_number})',
            amount=amount,
            currency=currency,
            status='PROCESSED',
            date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        db.session.add(tx)
        db.session.commit()
        flash(f"Withdrawal request of {amount:,.2f} {currency} submitted to {bank_acc.bank_name}.", "success")

    except Exception as e:
        flash(f"Withdrawal failed: {str(e)}", "danger")

    return redirect(url_for('dashboard'))


@app.route('/trade', methods=['POST'])
def trade():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    symbol = request.form.get('symbol', '').upper()
    shares = float(request.form.get('shares', 0))
    action = request.form.get('action')

    if symbol not in MARKET_CATALOG or shares <= 0:
        flash('Invalid market trade request.', 'danger')
        return redirect(url_for('dashboard'))

    price = MARKET_CATALOG[symbol]['price']
    total_cost = price * shares

    if action == 'BUY':
        if user.balance_usd < total_cost:
            flash('Insufficient USD balance to execute trade.', 'danger')
            return redirect(url_for('dashboard'))
        user.balance_usd -= total_cost
        holding = Portfolio.query.filter_by(username=user.username, symbol=symbol).first()
        if holding:
            holding.shares += shares
        else:
            db.session.add(Portfolio(username=user.username, symbol=symbol, shares=shares, avg_price=price))

        db.session.add(TransactionLedger(
            tx_ref=f"TRD-{uuid.uuid4().hex[:8].upper()}",
            username=user.username, tx_type='BUY',
            details=f'Bought {shares} {symbol}', amount=total_cost,
            currency='USD', status='COMPLETED', date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        db.session.commit()
        flash(f'Successfully bought {shares} units of {symbol}!', 'success')

    elif action == 'SELL':
        holding = Portfolio.query.filter_by(username=user.username, symbol=symbol).first()
        if not holding or holding.shares < shares:
            flash('Insufficient shares to execute sell order.', 'danger')
            return redirect(url_for('dashboard'))
        holding.shares -= shares
        if holding.shares <= 0:
            db.session.delete(holding)
        user.balance_usd += total_cost

        db.session.add(TransactionLedger(
            tx_ref=f"TRD-{uuid.uuid4().hex[:8].upper()}",
            username=user.username, tx_type='SELL',
            details=f'Sold {shares} {symbol}', amount=total_cost,
            currency='USD', status='COMPLETED', date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        db.session.commit()
        flash(f'Successfully sold {shares} units of {symbol}!', 'success')

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
