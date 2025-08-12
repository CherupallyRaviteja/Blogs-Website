from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash,request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user,logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib,os
from waitress import serve
from forms import *
email=os.getenv("My_email")
pswd=os.getenv("My_email_password")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("Flask_Key")
ckeditor = CKEditor(app)
Bootstrap5(app)

login_manager=LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("Database_URL")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))

# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(250), nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)

class User(UserMixin,db.Model):
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    email: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)

class Pst_Comments(db.Model):
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    post_id:Mapped[int]=mapped_column(Integer,nullable=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    comment:Mapped[str]=mapped_column(Text,nullable=False)

with app.app_context():
    db.create_all()

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register',methods=["GET","POST"])
def register():
    form=RegisterForm()
    if form.validate_on_submit():
        name=form.name.data
        email=form.email.data
        password=form.password.data
        hashed_password=generate_password_hash(password,method='pbkdf2:sha256',salt_length=8)
        new_user=User(name=name,email=email,password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("register.html",form=form,logged_in=current_user.is_authenticated)

@app.route('/login',methods=["GET","POST"])
def login():
    form=LoginForm()
    if form.validate_on_submit():
        email=form.email.data
        password=form.password.data
        find_user=db.session.execute(db.select(User).where(User.email==email)).scalar_one_or_none()
        if find_user and check_password_hash(find_user.password,password):
            login_user(find_user)
            result = db.session.execute(db.select(BlogPost))
            posts = result.scalars().all()
            return render_template("index.html", all_posts=posts,logged_in=current_user.is_authenticated,user=current_user)
        else:
            flash("Invalid Email or Password","danger")
    return render_template("login.html",form=form,logged_in=current_user.is_authenticated)

@app.route('/logout')
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('get_all_posts'))

@app.route('/')
def get_all_posts():
    result = db.session.execute(db.select(BlogPost))
    posts = result.scalars().all()
    return render_template("index.html", all_posts=posts,logged_in=current_user.is_authenticated,user=current_user)

@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    form = CommentForm()
    requested_post = db.get_or_404(BlogPost, post_id)
    all_comments = db.session.execute(
        db.select(Pst_Comments).where(Pst_Comments.post_id == post_id)
    ).scalars().all()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to log in to comment.", "warning")
            return redirect(url_for("login"))
        else:
            new_comment = Pst_Comments(
                post_id=post_id, name=current_user.name, comment=form.comment.data
            )
            db.session.add(new_comment)
            db.session.commit()
            return redirect(url_for("show_post", post_id=post_id))
    return render_template("post.html",post=requested_post,logged_in=current_user.is_authenticated,form=form,comments=all_comments,user=current_user)

@app.route("/new-post", methods=["GET", "POST"])
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user.name,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form,logged_in=current_user.is_authenticated)

@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True,logged_in=current_user.is_authenticated)

@app.route("/delete/<int:post_id>")
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact",methods=["GET","POST"])
def contact():
    if request.method=="POST":
        name=request.form.get("name")
        phone=request.form.get("phone")
        email_id=request.form.get("email")
        msge=request.form.get("message")
        message = f"Subject: User Message!\n\n Name :- {name}\n Email :- {email_id}\n Phone Number :- {phone} \n Message :- {msge}"
        with smtplib.SMTP("smtp.gmail.com",587) as connection:
            connection.starttls()
            connection.login(user=email,password=pswd)
            connection.sendmail(from_addr=email,to_addrs="cherupellyraviteja2005@gmail.com",msg=message)
        return render_template("contact.html", msg_sent=True)
    return render_template("contact.html", msg_sent=False)

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=5002)
