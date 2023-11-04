import requests
import re
import os
import time
import secrets
import atexit
import json
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, send_from_directory, request, flash, redirect, url_for
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

import models
from database import db

#load_dotenv()

REGEX = r'(?P<CUSTOMPROFILE>https?://steamcommunity.com/id/[A-Za-z_0-9]+)|(?P<CUSTOMURL>/id/[A-Za-z_0-9]+)|(?P<PROFILE>https?://steamcommunity.com/profiles/[0-9]+)|(?P<STEAMID2>STEAM_[10]:[10]:[0-9]+)|(?P<STEAMID3>\[U:[10]:[0-9]+\])|(?P<steam_account>[^/][0-9]{8,})'
UNSUPPORTED_GROUPS = ["STEAMID2", "STEAMID3"]

def background_task():
    print(time.strftime("%A, %d. %B %Y %I:%M:%S %p"))
    with app.app_context():
        if accounts := db.session.execute(db.select(models.SteamAccount).order_by(models.SteamAccount.id)).scalars():
            for account in accounts:
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
                
                db.session.commit()
                    
            
    
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=background_task, trigger="interval", seconds=60)
scheduler.start()

print(os.environ)
if os.environ.get("MANAGE_TOKEN"):
    print(f"Using provided token `{os.environ["MANAGE_TOKEN"]}`")
else:
    os.environ["MANAGE_TOKEN"] = secrets.token_hex(16)
    print(f"Using generated token `{os.environ["MANAGE_TOKEN"]}`")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24).hex()
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
#app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
db.init_app(app)

with app.app_context():
    db.create_all()

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
        # https://steamcommunity.com/id/illumfx/
        return get_steamid(steam_account.split("/")[-1])
        
    elif matched_group == "CUSTOMURL":
        # Get id from api
        return steam_account.split("/")[-1]
    
    # if matched_group == "CUSTOMURL":
    #     print(get_steamid(steam_account))
    #     return "https://steamcommunity.com/" + steam_account
    # elif matched_group == "steam_account":
    #     print(get_steamid(steam_account))
    #     return "https://steamcommunity.com/profiles/" + steam_account
    # else:
    #     return steam_account
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
    
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")
                
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        accounts = db.session.execute(db.select(models.SteamAccount).order_by(models.SteamAccount.id)).scalars()
        return render_template("index.html", accounts=accounts)
    elif request.method == "POST":
        display_name = request.form["name"]
        steam_account = request.form["account"]
        token = request.form["token"]
        
        if match := re.match(REGEX, steam_account):
            matched_group = match.lastgroup
            if steamid := parse_account(match.group(), matched_group):
                if len(steamid) != 17:
                    flash("Wrong Steam ID")
                elif not db.session.execute(db.select(models.SteamAccount).filter_by(steam_id=steamid)).scalar_one_or_none():
                    user = models.SteamAccount(
                        display_name = display_name,
                        steam_id = steamid
                    )
                    db.session.add(user)
                    db.session.commit()
                else:
                    flash("Steam ID duplicate")
        return redirect(url_for("index"))
      
    
if __name__ == "__main__":
    #get_bans("76561198125638897") # MoreKombat (Gameban)
    #get_bans("76561199125501660") # Thorben (VAC)
    
    app.run(host="0.0.0.0", port=6546, debug=True)
    atexit.register(lambda: scheduler.shutdown())