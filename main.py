from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'apex_enterprise_terminal_secure_9988'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apex_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ----------------- ADVANCED DATABASE MODELS ----------------- #

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
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
    account_number = db.Column(db.String(20), nullable=False)
    account_name = db.Column(db.String(150), nullable=False)


class TransactionLedger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    tx_type = db.Column(db.String(50), nullable=False)  # DEPOSIT, WITHDRAW, BUY, SELL, CONVERT
    details = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), nullable=False, default='SUCCESS')
    date = db.Column(db.String(50), nullable=False)


with app.app_context():
    db.create_all()

# Forex & Asset Market Data Catalog
EXCHANGE_RATE_USD_NGN = 1550.0  # Live benchmark rate $1 = ₦1,550

MARKET_CATALOG = {
    'EURUSD': {'name': 'Euro / US Dollar', 'price': 1.0850, 'category': 'Forex', 'type': 'currency'},
    'GBPUSD': {'name': 'British Pound / US Dollar', 'price': 1.2740, 'category': 'Forex', 'type': 'currency'},
    'USDNGN': {'name': 'US Dollar / Nigerian Naira', 'price': 1550.00, 'category': 'Forex', 'type': 'currency'},
    'BTC': {'name': 'Bitcoin Network Token', 'price': 64200.00, 'category': 'Crypto', 'type': 'crypto'},
    'ETH': {'name': 'Ethereum Smart Chain', 'price': 3450.00, 'category': 'Crypto', 'type': 'crypto'},
    'TSLA': {'name': 'Tesla Inc. Equity', 'price': 245.50, 'category': 'Equities', 'type': 'stock'},
    'AAPL': {'name': 'Apple Inc. Stock', 'price': 182.30, 'category': 'Equities', 'type': 'stock'},
    'NVDA': {'name': 'NVIDIA Corporation', 'price': 880.40, 'category': 'Equities', 'type': 'stock'}
}


# ----------------- APPLICATION ROUTES ----------------- #

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
return render_template('index.html', prices=MARKET_CATALOG)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('All input fields are required.')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Username is already taken.')
            return redirect(url_for('register'))

        new_user = User(username=username, password=password, balance_usd=0.0, balance_ngn=0.0)
        db.session.add(new_user)
        db.session.commit()
        session['username'] = username
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = username
            return redirect(url_for('dashboard'))
        flash('Invalid username or password.')
        return redirect(url_for('login'))
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

    # Calculate net worth in USD equivalent
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


@app.route('/link_bank', methods=['POST'])
def link_bank():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    bank_name = request.form.get('bank_name')
    account_number = request.form.get('account_number')
    account_name = request.form.get('account_name')

    if not bank_name or not account_number or not account_name:
        flash('All banking details are required to link account.')
        return redirect(url_for('dashboard'))

    new_bank = BankAccount(username=user.username, bank_name=bank_name, account_number=account_number,
                           account_name=account_name)
    db.session.add(new_bank)
    db.session.commit()
    flash(f'Successfully linked {bank_name} account ending in {account_number[-4:]}!')
    return redirect(url_for('dashboard'))


@app.route('/deposit', methods=['POST'])
def deposit():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    try:
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'USD')
        bank = request.form.get('bank_name')

        if amount <= 0:
            flash('Deposit amount must be greater than zero.')
            return redirect(url_for('dashboard'))

        if currency == 'NGN':
            user.balance_ngn += amount
        else:
            user.balance_usd += amount

        tx = TransactionLedger(
            username=user.username,
            tx_type='DEPOSIT',
            details=f'Bank Deposit via {bank}',
            amount=amount,
            status='COMPLETED',
            date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        db.session.add(tx)
        db.session.commit()
        flash(f'Successfully funded wallet with {amount:,.2f} {currency}!')
    except ValueError:
        flash('Invalid numeric amount entered.')
    return redirect(url_for('dashboard'))


@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    try:
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'USD')
        bank_target = request.form.get('bank_target')

        if currency == 'NGN':
            if user.balance_ngn < amount:
                flash('Insufficient NGN balance for withdrawal.')
                return redirect(url_for('dashboard'))
            user.balance_ngn -= amount
        else:
            if user.balance_usd < amount:
                flash('Insufficient USD balance for withdrawal.')
                return redirect(url_for('dashboard'))
            user.balance_usd -= amount

        tx = TransactionLedger(
            username=user.username,
            tx_type='WITHDRAW',
            details=f'Payout Transfer to {bank_target}',
            amount=amount,
            status='PROCESSED',
            date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        db.session.add(tx)
        db.session.commit()
        flash(f'Withdrawal of {amount:,.2f} {currency} sent to {bank_target}.')
    except ValueError:
        flash('Invalid withdrawal request.')
    return redirect(url_for('dashboard'))


@app.route('/convert', methods=['POST'])
def convert():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    try:
        direction = request.form.get('direction')
        amount = float(request.form.get('amount', 0))

        if amount <= 0:
            flash('Invalid conversion amount.')
            return redirect(url_for('dashboard'))

        if direction == 'USD_TO_NGN':
            if user.balance_usd < amount:
                flash('Insufficient USD balance.')
                return redirect(url_for('dashboard'))
            converted = amount * EXCHANGE_RATE_USD_NGN
            user.balance_usd -= amount
            user.balance_ngn += converted
            flash(f'Converted ${amount:.2f} USD to ₦{converted:,.2f} NGN')
        elif direction == 'NGN_TO_USD':
            if user.balance_ngn < amount:
                flash('Insufficient NGN balance.')
                return redirect(url_for('dashboard'))
            converted = amount / EXCHANGE_RATE_USD_NGN
            user.balance_ngn -= amount
            user.balance_usd += converted
            flash(f'Converted ₦{amount:,.2f} NGN to ${converted:.2f} USD')

        db.session.commit()
    except ValueError:
        flash('Currency exchange error.')
    return redirect(url_for('dashboard'))


@app.route('/trade', methods=['POST'])
def trade():
    if 'username' not in session:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=session['username']).first()

    symbol = request.form.get('symbol').upper()
    try:
        shares = float(request.form.get('shares', 0))
    except ValueError:
        flash('Invalid quantity.')
        return redirect(url_for('dashboard'))

    action = request.form.get('action')
    if symbol not in MARKET_CATALOG or shares <= 0:
        flash('Selected asset or quantity is invalid.')
        return redirect(url_for('dashboard'))

    price = MARKET_CATALOG[symbol]['price']
    total_cost = price * shares

    if action == 'BUY':
        if user.balance_usd < total_cost:
            flash('Insufficient USD funds for trade execution.')
            return redirect(url_for('dashboard'))
        user.balance_usd -= total_cost

        holding = Portfolio.query.filter_by(username=user.username, symbol=symbol).first()
        if holding:
            total_shares = holding.shares + shares
            holding.avg_price = ((holding.avg_price * holding.shares) + (price * shares)) / total_shares
            holding.shares = total_shares
        else:
            new_h = Portfolio(username=user.username, symbol=symbol, shares=shares, avg_price=price)
            db.session.add(new_h)

        tx = TransactionLedger(username=user.username, tx_type='BUY', details=f'Bought {shares} units of {symbol}',
                               amount=total_cost, status='SUCCESS', date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        db.session.add(tx)
        db.session.commit()
        flash(f'Successfully bought {shares} units of {symbol}!')

    elif action == 'SELL':
        holding = Portfolio.query.filter_by(username=user.username, symbol=symbol).first()
        if not holding or holding.shares < shares:
            flash('You do not own enough units to sell.')
            return redirect(url_for('dashboard'))

        holding.shares -= shares
        if holding.shares <= 0:
            db.session.delete(holding)
        user.balance_usd += total_cost

        tx = TransactionLedger(username=user.username, tx_type='SELL', details=f'Sold {shares} units of {symbol}',
                               amount=total_cost, status='SUCCESS', date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        db.session.add(tx)
        db.session.commit()
        flash(f'Successfully sold {shares} units of {symbol}!')

    return redirect(url_for('dashboard'))


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
