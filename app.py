import requests
import re
import os
import atexit
import json
import flask_login
import uuid as uuid_
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, request, flash, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

import models
from database import db

load_dotenv()

REGEX = r'(?P<CUSTOMPROFILE>https?://steamcommunity.com/id/[A-Za-z_0-9]+)|(?P<CUSTOMURL>/id/[A-Za-z_0-9]+)|(?P<PROFILE>https?://steamcommunity.com/profiles/[0-9]+)|(?P<STEAMID2>STEAM_[10]:[10]:[0-9]+)|(?P<STEAMID3>\[U:[10]:[0-9]+\])|(?P<steam_account>[^/][0-9]{8,})'
UNSUPPORTED_GROUPS = ["STEAMID2", "STEAMID3"] # Don't know, don't care

def background_task():
    with app.app_context():
        if accounts := db.session.execute(db.select(models.SteamAccount).order_by(models.SteamAccount.id)).scalars():
            for account in accounts:
                if not account.admin_account.admin_lvl == 0:
                    bans = get_bans("https://steamcommunity.com/profiles/" + account.steam_id)
                    new_ban = False
                    for ban in bans:
                        if ban[1] == "vac":
                            if account.vac_banned == False:
                                new_ban = True
                                account.vac_banned = True
                                account.times_banned = account.times_banned + 1
                        
                        if ban[1] == "game":
                            if account.game_banned == False:
                                new_ban = True
                                account.game_banned = True
                                account.times_banned = account.times_banned + 1
                        
                        if new_ban:
                            account.banned_since = datetime.now()
                            
                    app.jinja_env.globals["LAST_CHECK"] = datetime.now()
                    db.session.commit()    

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=background_task, trigger="interval", seconds=120)
scheduler.start()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URI")

# All timezones: https://gist.github.com/heyalexej/8bf688fd67d7199be4a1682b3eec7568
app.jinja_env.globals["TIMEZONE"] = timezone(os.environ.get("TIMEZONE", "UTC"))
app.jinja_env.globals["LAST_CHECK"] = datetime.now()

db.init_app(app)

with app.app_context():
    db.create_all()
    if not db.session.execute(db.select(models.AdminAccount).filter_by(admin_lvl=2)).scalar_one_or_none():
        pw = os.environ.get("DEFAULT_ADMIN_PASSWORD", None) or os.urandom(24).hex()
        print(f"No admin account with admin lvl 2 found, created a new one:\nUsername: admin\nPassword: {pw}")
        new_admin = models.AdminAccount(
            uuid = str(uuid_.uuid4()),
            username = "admin",
            password = generate_password_hash(pw),
            admin_lvl = 2
        )
        db.session.add(new_admin)
        db.session.commit()

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(user_id):
    user = db.session.execute(db.select(models.AdminAccount).filter_by(id=user_id)).scalar_one_or_none()
    return user


@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')
    user = db.session.execute(db.select(models.AdminAccount).filter_by(username=username)).scalar_one_or_none()
    return user

@login_manager.unauthorized_handler
def unauthorized_handler():
    flash("Unauthorized")
    return redirect(url_for("index"))

def get_bans(account_url):  
    res = requests.get(account_url)
    soup = BeautifulSoup(res.content, "html.parser")
    page = soup.find(id="responsive_page_template_content")
    
    found_bans = []
    
    if bans := page.find("div", class_="profile_ban_status"):

        for line in bans.prettify().splitlines():
            if line.endswith("on record"):
                # Account has been banned
                found_bans.append(line.strip().lower().split(" ")[0:2])
    
    return found_bans
            
def parse_account(steam_account: str, matched_group: str):
    if matched_group in UNSUPPORTED_GROUPS:
        return False
    
    if matched_group == "PROFILE":
        # Get id from url
        return steam_account.split("/")[-1]
        
    elif matched_group == "CUSTOMPROFILE":
        # Get id from api
        return get_steamid(steam_account.split("/")[-1])
        
    elif matched_group == "CUSTOMURL":
        # Get id from api
        return steam_account.split("/")[-1]
    
    return
    
def get_steamid(account_name):
    res = requests.get("http://api.steampowered.com/ISteamUser/ResolveVanityURL/v0001/", params={"key": os.environ["STEAM_API_KEY"], "vanityurl": account_name})
    res.raise_for_status()
    
    data = json.loads(res.content)
    response = data["response"]
    if response["success"] == 1:
        # Match
        return response["steamid"]
    else:
        # Success code is 42 so no match
        return
    
@app.get("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico")
                
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        accounts = db.session.execute(db.select(models.SteamAccount).order_by(models.SteamAccount.id)).scalars()
        return render_template("index.html", accounts=accounts)
    elif request.method == "POST":
        if flask_login.current_user.is_authenticated:
            display_name = request.form["name"]
            steam_account = request.form["account"]
            
            if match := re.match(REGEX, steam_account):
                matched_group = match.lastgroup
                if steamid := parse_account(match.group(), matched_group):
                    if len(steamid) != 17:
                        flash("Wrong Steam ID")
                    elif not db.session.execute(db.select(models.SteamAccount).filter_by(steam_id=steamid)).scalar_one_or_none():
                        user = models.SteamAccount(
                            admin_account = flask_login.current_user,
                            display_name = display_name,
                            steam_id = steamid
                        )
                        db.session.add(user)
                        db.session.commit()
                    else:
                        flash("Steam ID duplicate")
            else:
                flash("Invalid Steam account")
        return redirect(url_for("index"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if flask_login.current_user.is_authenticated:
            return redirect(url_for("index"))
        else:
            return render_template("login.html")
    elif request.method == "POST":
        if flask_login.current_user.is_authenticated:
            username = request.form["username"]
            if user := db.session.execute(db.select(models.AdminAccount).filter_by(username=username)).scalar_one_or_none(): 
                if check_password_hash(user.password, request.form["password"]):
                    flask_login.login_user(user)
                    return redirect(url_for("index"))
                else: 
                    flash("Wrong credentials")       
                    return redirect(url_for("login"))            
            else:
                flash("Wrong credentials")       
                return redirect(url_for("login"))
        else:
            # hackerman?!?!???
            return redirect(url_for("index"))
        
@app.get("/self")
@flask_login.login_required
def self():
    accounts = db.session.execute(db.select(models.SteamAccount).filter_by(admin_account=flask_login.current_user)).scalars()
    return render_template("index.html", accounts=accounts)
        
@app.get("/logout")
@flask_login.login_required
def logout():
    flask_login.logout_user()
    return redirect(url_for("index"))

@app.get("/info-steam-account/<account_id>")
@flask_login.login_required
def info_steam_account(account_id):
    if steam_account := db.session.execute(db.select(models.SteamAccount).filter_by(steam_id=account_id)).scalar_one_or_none():
        return render_template("info.html", steam_account=steam_account)
    else:
        flash("Unknown account")
        return redirect(url_for("index"))

@app.post("/edit-steam-account/<account_id>")
@flask_login.login_required
def edit_steam_account(account_id):
    if steam_account := db.session.execute(db.select(models.SteamAccount).filter_by(steam_id=account_id)).scalar_one_or_none():
        new_name = request.form["new_name"]
        if new_name == steam_account.display_name:
            flash("Display name can't be the same")
            return redirect(url_for("index"))
        
        try:
            steam_account.display_name = new_name
            db.session.commit()
        except IntegrityError:
            flash("Display name already exists")
            return redirect(url_for("index"))
        return redirect(url_for("index"))
    else:
        flash("Unknown account")
        return redirect(url_for("index"))

@app.post("/delete-steam-account/<account_id>")
@flask_login.login_required
def delete_steam_account(account_id: int):
    if account := models.SteamAccount.query.filter_by(steam_id=account_id):
        if flask_login.current_user.admin_lvl == 2 or account.first().admin_account == flask_login.current_user:
            account.delete()
            db.session.commit() 
    else:
        flash("Account doesn't exist!")
        
    return redirect(url_for("index"))

@app.route("/delete-admin-account/<account_id>", methods=["GET", "POST"])
@flask_login.login_required
def delete_admin_account(account_id):
    if flask_login.current_user.admin_lvl == 2:
        if account := models.AdminAccount.query.filter_by(uuid=account_id):
            if account.first().admin_lvl > 1:
                flash("Superuser accounts can't be deleted")
            else:
                db.session.execute(
                    delete(models.SteamAccount).filter_by(admin_account=account.first())
                )
                account.delete()
                db.session.commit()              
        else:
            flash("Account doesn't exist")
        
    else:
        flash("Unauthorized")
        
    return redirect(url_for("admin"))

@app.post("/demote-admin-account/<account_id>")
@flask_login.login_required
def demote_admin_account(account_id):
    if flask_login.current_user.admin_lvl == 2:
        if account := db.session.execute(db.select(models.AdminAccount).filter_by(uuid=account_id)).scalar_one_or_none():
            if account.admin_lvl > 1:
                flash("Superuser accounts can't be demoted")
            else:
                account.admin_lvl = account.admin_lvl - 1
                db.session.commit()              
        else:
            flash("Account doesn't exist")
        
    else:
        flash("Unauthorized")
        
    return redirect(url_for("admin"))

@app.post("/promote-admin-account/<account_id>")
@flask_login.login_required
def promote_admin_account(account_id):
    if flask_login.current_user.admin_lvl == 2:
        if account := db.session.execute(db.select(models.AdminAccount).filter_by(uuid=account_id)).scalar_one_or_none():
            if account.admin_lvl > 1:
                flash("Superuser accounts can't be promoted")
            else:
                account.admin_lvl = account.admin_lvl + 1
                db.session.commit()              
        else:
            flash("Account doesn't exist")
        
    else:
        flash("Unauthorized")
        
    return redirect(url_for("admin"))

@app.route("/create-user", methods=["GET", "POST"])
@flask_login.login_required
def create_user():
    if flask_login.current_user.admin_lvl == 2:
        if request.method == "GET":
            return render_template("create_user.html")
        else:
            # assuming user creation
            _username = request.form["username"]
            _password = request.form["password"]
            _admin_lvl = request.form["admin_lvl"]
            if db.session.execute(db.select(models.AdminAccount).filter_by(username=_username)).scalar_one_or_none(): 
                flash("Username already exists!")              
            else:
                new_admin = models.AdminAccount(
                    username = _username,
                    password = generate_password_hash(_password),
                    admin_lvl = _admin_lvl
                )
                db.session.add(new_admin)
                db.session.commit()
            return redirect(url_for("admin"))
    else:
        flash("Unauthorized")
        
    return redirect(url_for("admin"))


@app.get("/admin")
@flask_login.login_required
def admin():
    if flask_login.current_user.admin_lvl == 2:
        accounts = db.session.execute(db.select(models.AdminAccount).order_by(models.AdminAccount.id)).scalars()
        return render_template("admin.html", accounts=accounts)          
    else:
        return redirect(url_for("index"))
        
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=os.getenv("PORT"), debug=True)
    atexit.register(lambda: scheduler.shutdown())