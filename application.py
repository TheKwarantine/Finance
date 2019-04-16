import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio = db.execute("SELECT ticker, sum(shares) shares FROM purchase WHERE id = :sid GROUP BY ticker",
                           sid=session["user_id"])
    userDetails = db.execute("SELECT * FROM users WHERE id = :sid", sid=session["user_id"])
    value = 0.00
    cash = usd(userDetails[0]["cash"])

    # Iterating through users portfolio and cleaning up values for display
    for row in portfolio:
        details = lookup(row["ticker"])
        row["name"] = details['name']
        row["price"] = usd(details['price'])
        row["value"] = usd(details['price'] * row['shares'])
        value += details['price'] * row['shares']

    value = usd(value + userDetails[0]["cash"])
    return render_template("index.html", portfolio=portfolio, cash=cash, value=value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        try:
            buyCount = int(request.form.get("shares"))
        except ValueError:
            return apology("Please Provide an Integer")

        buyCount = int(request.form.get("shares"))
        details = lookup(request.form.get("symbol"))

        # Checks if stock sent is valid
        if details == None:
            return apology("Stock not found")

        if buyCount > 0:
            dbQuery = db.execute("SELECT * FROM users WHERE id = :sessionId", sessionId=session["user_id"])

            # Updating Stock Tickers table if no one has purchased the stock before
            if db.execute("SELECT EXISTS(SELECT symbol FROM stock_tickers WHERE symbol = :symbol)", symbol=details['symbol']):
                db.execute("INSERT INTO stock_tickers (symbol, name) VALUES(:symbol, :name)",
                           symbol=details["symbol"], name=details["name"])

            # Checking cash balance to confirm if enough to complete the purchase
            if float(details['price']) * float(buyCount) < float(dbQuery[0]['cash']):
                db.execute("INSERT INTO purchase (id, ticker, price, shares) VALUES(:sid, :ticker, :price, :shares)",
                           sid=session["user_id"], ticker=details["symbol"], price=details["price"], shares=buyCount)
                newBalance = (float(dbQuery[0]['cash']) - (float(details['price']) * float(buyCount)))
                db.execute("UPDATE users SET cash = :balance WHERE id = :sessionId",
                           balance=newBalance, sessionId=session["user_id"])
                flash("Purchase Successful")
                return redirect('/')

            # If user doesn't have enough Balance, reject purchase.
            else:
                return apology("Balance Insufficient", 403)

        else:
            return apology("Please Provide a Postive Value")

    # Server response if reached via GET
    else:
        dbQuery = db.execute("SELECT cash FROM users WHERE id = :sessionId", sessionId=session["user_id"])
        balance = usd(dbQuery[0]["cash"])
        return render_template("buy.html", balance=balance)


@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")

    # Checks server for if the username exists
    result = db.execute("SELECT * FROM users WHERE EXISTS (SELECT * FROM users WHERE username = :username)", username=username)

    # Returns via JSON whether name is available or not
    if not result and len(username) > 0:
        return jsonify(True)
    else:
        return jsonify(False)


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute(
        "SELECT * FROM purchase LEFT JOIN stock_tickers ON purchase.ticker = stock_tickers.symbol WHERE purchase.id = :sid", sid=session["user_id"])

    # Updates each transaction with screen ready data
    for row in transactions:
        row["price"] = usd(row["price"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must haz username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash('Successfully Logged In')
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

    # If user reached via POST, display results
    if request.method == "POST":
        quote = lookup(request.form.get("symbol"))

        # Checks if stock sent for quote was valid
        if quote == None:
            return apology("Stock not found", 400)

        # Returns stock price in a readable format
        stock_price = usd(quote["price"])
        return render_template("quoted.html", quote=quote, stock_price=stock_price)

    # If user reached via GET, display quote page
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Verify user reached by POST or GET
    if request.method == "POST":

        # Check if Username was submitted empty
        if not request.form.get("username"):
            return apology("Username haz EMPTY", 400)

        # Check if Password or Confirmation was submitted empty
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Pazzword haz EMPTY", 400)

        # Check that Password and Confirmation match
        elif not request.form.get("password") == request.form.get("confirmation"):
            return apology("Pazzword No Match", 400)

        # Check if Username is taken
        result = db.execute("SELECT * FROM users WHERE EXISTS (SELECT * FROM users WHERE username = :username)",
                            username=request.form.get("username"))

        if not result and len(request.form.get("username")) > 0:

            # If user name is long enough and exists, Hash Password and register user database
            hsp = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
            usn = request.form.get("username")
            db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=usn, hash=hsp)

            # Check database for existence
            rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

            # Setup session ID for user
            session["user_id"] = rows[0]["id"]

            # Return to homepage
            flash("Registration Successful")
            return redirect("/")

        # If Username is taken, return apology
        else:
            return apology("Username Taken", 400)

    # If user requested via GET, send them form to register
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # If user requested via POST, run checks to sell stock
    if request.method == "POST":
        sellTicker = request.form.get("symbol")
        sellShares = float(request.form.get("shares"))
        portfolio = db.execute("SELECT ticker, sum(shares) shares FROM purchase WHERE id = :sid AND ticker = :symbol",
                               sid=session["user_id"], symbol=sellTicker)

        # Checks if user has enough shares to sell
        if sellShares > portfolio[0]["shares"]:
            return apology("Unable to Process Request (Not Enough Shares)")

        # Checks if user chose a stock
        elif sellTicker == None:
            return apology("Unable to Process Request (Must choose a Stock to sell)")

        # Checks if user provided a positive number to sell
        elif sellShares < 1:
            return apology("Unable to Process Request (Please Provide Positive Number)")

        # Begins to sell stock
        else:
            details = lookup(sellTicker)
            userDetails = db.execute("SELECT cash FROM users WHERE id = :sid", sid=session["user_id"])
            newTotal = userDetails[0]["cash"] + (details['price'] * sellShares)

            # Update table with new cash value after sell
            db.execute("UPDATE users SET cash = :total WHERE id = :sid", total=newTotal, sid=session["user_id"])

            # Update purchase table with purchase details
            db.execute("INSERT INTO purchase (id, ticker, price, shares) VALUES(:sid, :ticker, :price, :shares)",
                       sid=session["user_id"], ticker=details["symbol"], price=details["price"], shares=(0 - sellShares))
            flash("Transaction Successful")
            return redirect("/")

    # If user submitted via GET
    else:
        symbols = db.execute("SELECT ticker, sum(shares) shares FROM purchase WHERE id = :sid GROUP BY ticker",
                             sid=session["user_id"])
        return render_template("sell.html", symbols=symbols)


@app.route("/password", methods=["GET", "POST"])
@login_required
def password():
    """Change Password"""

    # If user submitted form
    if request.method == "POST":

        # Checks if Old Password was provided
        if not request.form.get("oldPassword"):
            return apology("Old Password is Needed", 403)

        # Checks if New Password was provided
        if not request.form.get("newPassword"):
            return apology("Need a New Password", 403)

        # Checks if New Password was typed in correctly the second time
        if not request.form.get("newPassword") == request.form.get("confirmation"):
            return apology("New Passwords Don't Match", 403)

        details = db.execute("SELECT * FROM users WHERE id = :sid", sid=session["user_id"])

        # Checks if old password matches and if it does, updates to new password
        if check_password_hash(details[0]["hash"], request.form.get("oldPassword")):
            hsp = generate_password_hash(request.form.get("newPassword"), method='pbkdf2:sha256', salt_length=8)
            db.execute("UPDATE users SET hash = :hash WHERE id = :sid", hash=hsp, sid=session["user_id"])
            flash("Password Updated")
            return redirect("/")
    else:
        return render_template("password.html")


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    """Deposit More Money!"""

    # If user arrived via POST, prepare to add more money
    if request.method == "POST":

        cash = int(request.form.get("deposit"))

        # Checks if deposit amount is positive
        if cash < 0:
            return apology("Must be a Positive Integer")

        # Checks current balance and then adds the deposit amount and resaves the value
        details = db.execute("SELECT * FROM users WHERE id = :sid", sid=session["user_id"])
        newTotal = cash + details[0]["cash"]
        db.execute("UPDATE users SET cash = :cash WHERE id = :sid", cash=newTotal, sid=session["user_id"])

        # Return to home, confirming deposit to user
        flash("Money Deposited, Baller!")
        return redirect("/")
    else:
        return render_template("deposit.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
