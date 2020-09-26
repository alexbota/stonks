import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)
app.secret_key = '3gnd43k19'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Enable function call from jinja
app.jinja_env.globals.update(lookup=lookup)
app.jinja_env.globals.update(usd=usd)


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    cash = db.execute(
        "SELECT cash FROM users WHERE id=:user", user=user)[0].get("cash")
    stocks = db.execute(
        "SELECT * FROM shareholders WHERE user=:user ORDER BY symbol", user=user)
    return render_template("index.html", cash=cash, stocks=stocks)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        shares = float(request.form.get("shares"))
        quoted = lookup(symbol)

        # Check for valid symbol
        if quoted == None:
            flash('Invalid symbol', 'error')
            return render_template('buy.html')

        price = quoted.get('price')
        user = session["user_id"]
        cost = quoted.get('price') * shares
        """Get user's cash"""
        cash = db.execute(
            "SELECT cash FROM users WHERE id == :user", user=user)[0].get('cash')

        """Check if user has enough funds"""
        if cash < cost:
            flash('Not enough funds to buy shares', 'error')
            return render_template('buy.html')
        else:
            name = quoted.get('name')
            symbol = quoted.get('symbol')
            date = datetime.now().replace(second=0, microsecond=0)
            new_cash = cash - (shares * price)
            db.execute("INSERT INTO history (user, symbol, shares, price, date) VALUES (:user, :symbol, :shares, :price, :date)",
                       user=user, symbol=symbol, shares=shares, price=price, date=date)
            db.execute("UPDATE users SET cash=:cash WHERE id=:user",
                       cash=new_cash, user=user)
            x = db.execute(
                "SELECT symbol FROM shareholders WHERE symbol=:symbol AND user=:user", symbol=symbol, user=user)

            """Check if user already has shares of a stock and if he does update the number of shares"""
            if not x:
                db.execute("INSERT INTO shareholders (user, name, symbol, shares) VALUES (:user, :name, :symbol, :shares)",
                           user=user, name=name, symbol=symbol, shares=shares)
            else:
                shares = shares + db.execute(
                    "SELECT shares FROM shareholders WHERE symbol=:symbol AND user=:user", symbol=symbol, user=user)[0].get("shares")
                db.execute("UPDATE shareholders SET shares=:shares WHERE symbol=:symbol AND user=:user",
                           shares=shares, symbol=symbol, user=user)
                flash('Bought!', 'success')
            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    rows = db.execute(
        "SELECT * FROM history WHERE user=:user ORDER BY date", user=user)
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash('Must provide username', 'error')
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Must provide password", 'error')
            return render_template("login.html")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash('Invalid username and/or password', 'error')
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == 'GET':
        return render_template('quote.html')
    else:
        symbol = request.form.get("symbol")
        quoted = lookup(symbol)
        if quoted == None:
            flash('Invalid symbol', 'error')
            return render_template('quote.html')
        else:
            name = quoted.get('name')
            price = usd(quoted.get('price'))
            symbol = quoted.get('symbol')
            return render_template("/quoted.html", name=name, price=price, symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == 'GET':
        return render_template('register.html')
    else:
        username = request.form.get("username")
        usernames = db.execute(
            "SELECT username FROM users WHERE username=:username", username=username)
        if usernames:
            flash('Username already exsists', 'error')
            return render_template('register.html')
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        if password == confirm_password:
            password = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                       username=username, hash=password)
            return redirect("/login")
        else:
            flash('Both password inputs must match', 'error')
            return render_template('register.html')


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """View and change account settings"""
    return render_template("account.html")


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change account password"""
    if request.method == "GET":
        return render_template("password.html")
    else:
        rows = db.execute("SELECT * FROM users WHERE id = :id",
                          id=session["user_id"])
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash('Incorrect Password', 'error')
            return render_template("password.html")
        elif request.form.get("new_password") != request.form.get("confirm_password"):
            flash('Both password inputs must match', 'error')
            return render_template("password.html")
        else:
            password = generate_password_hash(
                request.form.get("new_password"))
            db.execute("UPDATE users SET hash=:password WHERE id=:id",
                       password=password, id=session["user_id"])
            flash('Password changed successfully', 'success')
            return redirect("/account")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user = session["user_id"]
        stocks = db.execute(
            "SELECT * FROM shareholders WHERE user=:user ORDER BY symbol", user=user)
        return render_template("sell.html", stocks=stocks)
    else:
        user = session["user_id"]
        symbol = request.form.get("symbol")
        shares = float(request.form.get("shares"))
        quoted = lookup(symbol)
        price = quoted.get('price')
        date = datetime.now().replace(second=0, microsecond=0)
        user_shares = db.execute(
            "SELECT shares FROM shareholders WHERE symbol=:symbol AND user=:user", symbol=symbol, user=user)[0].get("shares")
        if shares > user_shares:
            flash('Number of shares exceed portofolio', 'error')
            return render_template('sell.html')
        else:
            cash = db.execute("SELECT cash FROM users WHERE id=:user", user=user)[
                0].get("cash")
            new_cash = cash + (price * shares)
            db.execute("INSERT INTO history (user, symbol, shares, price, date) VALUES (:user, :symbol, :shares, :price, :date)",
                       user=user, symbol=symbol, shares=-shares, price=price, date=date)
            db.execute("UPDATE users SET cash=:cash WHERE id=:user",
                       cash=new_cash, user=user)
            shares = user_shares - shares
            db.execute("UPDATE shareholders SET shares=:shares WHERE symbol=:symbol AND user=:user",
                       shares=shares, symbol=symbol, user=user)
            db.execute("DELETE FROM shareholders WHERE shares=0")
            flash('Sold!', 'success')
            return redirect("/")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit more cash into account"""
    if request.method == "GET":
        return render_template("deposit.html")
    else:
        funds = float(request.form.get("funds"))
        cash = db.execute(
            "SELECT cash FROM users WHERE id=:id", id=session["user_id"])[0].get("cash")
        cash = funds + cash
        db.execute("UPDATE users SET cash=:cash WHERE id=:id",
                   cash=cash, id=session["user_id"])
        flash('You successfully deposited funds!', 'success')
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
