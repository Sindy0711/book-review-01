import os, requests

from flask import Flask, session, render_template, redirect, request, url_for, jsonify
from flask_session import Session
# from flask_wtf import FlaskForm
# from wtforms import StringField, PasswordField, SubmitField
# from wtforms.validators import InputRequired, Email, Length, EqualTo
from werkzeug.security import generate_password_hash
from sqlalchemy import create_engine ,text
from sqlalchemy.orm import scoped_session, sessionmaker
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import SQLAlchemyError

from dotenv import load_dotenv  #add dotenv load environment
load_dotenv() 

app = Flask(__name__)

# class RegistrationForm(FlaskForm):
#     first_name = StringField('First Name', validators=[InputRequired()])
#     last_name = StringField('Last Name', validators=[InputRequired()])
#     email = StringField('E-mail', validators=[InputRequired(), Email()])
#     password1 = PasswordField('Password', validators=[InputRequired(), Length(min=8), EqualTo('password2', message='Passwords must match')])
#     password2 = PasswordField('Confirm password', validators=[InputRequired()])
#     submit = SubmitField('Register')

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
# elif not os.getenv("KEY"):
#     raise RuntimeError("API KEY is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))
# key = os.getenv("KEY")
# app.config['SECRET_KEY'] = os.urandom(24)

## Helper
def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.12/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("email") is None:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if session.get("email") is not None:
        return render_template('search.html')
    else:
        return render_template('index.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    # if GET, show the registration form
    if request.method == "GET":
        return render_template("register.html")

    # if POST, validate and commit to database

    else:
        #if form values are empty show error
        if not request.form.get("first_name"):
            return render_template("error.html", message="Must provide First Name")
        elif not request.form.get("last_name"):
            return render_template("error.html", message="Must provide Last Name")
        elif  not request.form.get("email"):
            return render_template("error.html", message="Must provide E-mail")
        elif not request.form.get("password1") or not request.form.get("password2"):
            return render_template("error.html", message="Must provide password")
        elif request.form.get("password1") != request.form.get("password2"):
            return render_template("error.html", message="Password does not match")
        ## end validation
        else :
            ## assign to variables
            first_name = request.form.get("first_name")
            last_name = request.form.get("last_name")
            email = request.form.get("email")
            password = request.form.get("password1")
            # try to commit to database, raise error if any
            try:
                db.execute(text("INSERT INTO users (firstname, lastname, email, password) VALUES (:firstname, :lastname, :email, :password)"
                            ),
                               {"firstname": first_name, "lastname": last_name, "email":email, "password": generate_password_hash(password)}        
                )
            except Exception as e:
                return render_template("error.html", message=e)
            
            db.commit()
            #success - redirect to login
            Q = db.execute(
                text("SELECT * FROM users WHERE email LIKE :email"),
                {"email": email},
            ).fetchone()
            print(Q.userid)
            # Remember which user has logged in
            session["user_id"] = Q.userid
            session["email"] = Q.email
            session["firstname"] = Q.firstname
            session["logged_in"] = True
            return redirect(url_for("search"))


@app.route("/login", methods=["GET", "POST"])
def login():

    # Forget any user_id
    session.clear()

    if request.method == "POST":
        form_email = request.form.get("email")
        form_password = request.form.get("password")

        # Ensure username and password was submitted
        if not form_email:
            return render_template("error.html", message="must provide username")
        elif not form_password:
            return render_template("error.html", message="must provide password")

        # Query database for email and password
        Q = db.execute(text("SELECT * FROM users WHERE email LIKE :email"), {"email": form_email}).fetchone()
        db.commit()
        # User exists ?
        if Q is None:
            return render_template("error.html", message="User doesn't exists")
        # Valid password ?
        if not check_password_hash( Q.password, form_password):
            return  render_template("error.html", message = "Invalid password")

        # Remember which user has logged in
        session["user_id"] = Q.userid
        session["email"] = Q.email
        session["firstname"] = Q.firstname
        session["logged_in"] = True
        return redirect(url_for("search"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    # Forget any user_id
    session.clear()

    # Redirect user to login index
    return redirect(url_for("index"))


@app.route("/search", methods=["GET","POST"])
@login_required
def search():
    if request.method == "GET":
        return render_template("search.html")
    else:
        query = request.form.get("input-search")
        if query is None:
            return render_template("error.html", message="Search field can not be empty!")
        try:
            result = db.execute(text('SELECT * FROM books WHERE LOWER(isbn) LIKE :query OR LOWER(title) LIKE :query OR LOWER(author) LIKE :query'), {"query": "%" + query.lower() + "%"}).fetchall()
        except Exception as e:
            return render_template("error.html", message=e)
        if not result:
            return render_template("error.html", message="Your query did not match any documents")
        return render_template("list.html", result=result)


@app.route("/details/<int:bookid>", methods=["GET","POST"])
@login_required
def details(bookid):
    if request.method == "GET":
        #Get book details
        result = db.execute(text("SELECT * from books WHERE bookid = :bookid"), {"bookid": bookid}).fetchone()

        #Get API data from OpenLibrary
        try:
            #Check API to get 'works' key for putting it to a new link in order to get ratings count.
            openlib_details = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{result.isbn}&jscmd=details&format=json")
        except Exception as e:
            return render_template("error.html", message = e)
        #Get 'works' key
        openlibrary_workskey = openlib_details.json()[f"ISBN:{result.isbn}"]["details"]['works'][0]['key']
        #Get ratings data
        openlibrary_ratings = requests.get("https://openlibrary.org/" + openlibrary_workskey + "/ratings.json")
        #get cover book
        openlib_data = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{result.isbn}&jscmd=data&format=json")
        cover = openlib_data.json()[f"ISBN:{result.isbn}"]["cover"]['medium']
        #get descriptions
        try:
            openlib_descriptions = requests.get("https://openlibrary.org/" + openlibrary_workskey + ".json").json()["description"]["value"]
        except Exception as e:
            openlib_descriptions = "No descriptions"
        # Get comments particular to one book
        comment_list = db.execute(text("SELECT u.firstname, u.lastname, u.email, r.rating, r.comment from reviews r JOIN users u ON u.userid=r.user_id WHERE book_id = :id"), {"id": bookid}).fetchall()
        if not result:
            return render_template("error.html", message="Invalid book id")

        return render_template("details.html", result=result, comment_list=comment_list , bookid=bookid, openlib=openlibrary_ratings.json()['summary'], cover=cover, descriptions = openlib_descriptions)
    else:
        ######## Check if the user commented on this particular book before ###########
        user_reviewed_before = db.execute(text("SELECT * from reviews WHERE user_id = :user_id AND book_id = :book_id"),  {"user_id": session["user_id"], "book_id": bookid}).fetchone()
        if user_reviewed_before:
            return render_template("error.html", message = "You reviewed this book before!")
        ######## Proceed to get user comment ###########
        user_comment = request.form.get("comments")
        user_rating = request.form.get("rating")

        if not user_comment:
            return render_template("error.html", message="Comment section cannot be empty")

        # try to commit to database, raise error if any
        try:
            db.execute(text("INSERT INTO reviews (user_id, book_id, rating, comment) VALUES (:user_id, :book_id, :rating, :comment)"),
                           {"user_id": session["user_id"], "book_id": bookid, "rating":user_rating, "comment": user_comment})
        except Exception as e:
            return render_template("error.html", message=e)

        #success - redirect to details page
        db.commit()
        return redirect(url_for("details", bookid=bookid))



# Create app's API 
@app.route("/api/<string:isbn>")
@login_required
def api(isbn):
    """Return details about a single book in json format"""

    # Make sure ISBN exists in the database
    try:
        book = db.execute(text("SELECT * from books WHERE isbn = :isbn"), {"isbn": isbn}).fetchone()
    except Exception as e:
        return render_template("error.html", message=e)
    if book is None:
        return jsonify({"error": "Not Found"}), 404
    # Get GoodReads API datad
    goodreads2  = goodreads = requests.get("https://openlibrary.org/api/books?bibkeys=ISBN:1857231082&jscmd=details&format=json")
    key1 = goodreads2 .json()["ISBN:1857231082"]["details"]['works'][0]['key']
    goodreads3 = requests.get(
        f"https://openlibrary.org/{key1}/ratings.json"
    ).json()
    goodreads_book = goodreads3["summary"]
    # Return book details in JSON
    return jsonify({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book.isbn,
            "average": goodreads_book["average"],
            "count": goodreads_book["count"]
          })
if __name__ == "__main__":
    app.run()
    app.run(debug=True)