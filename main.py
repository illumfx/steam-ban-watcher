import requests
import re
import os
import time
import atexit
from flask import Flask, render_template, send_from_directory
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler

REGEX = r'(?P<CUSTOMPROFILE>https?://steamcommunity.com/id/[A-Za-z_0-9]+)|(?P<CUSTOMURL>/id/[A-Za-z_0-9]+)|(?P<PROFILE>https?://steamcommunity.com/profiles/[0-9]+)|(?P<STEAMID2>STEAM_[10]:[10]:[0-9]+)|(?P<STEAMID3>\[U:[10]:[0-9]+\])|(?P<steam_account>[^/][0-9]{8,})'
UNSUPPORTED_GROUPS = ["STEAMID2", "STEAMID3"]

def background_task():
    print(time.strftime("%A, %d. %B %Y %I:%M:%S %p"))
    
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=background_task, trigger="interval", seconds=10)
scheduler.start()

app = Flask(__name__)

def get_bans(account_url):  
    res = requests.get(account_url)
    soup = BeautifulSoup(res.content, "html.parser")
    page = soup.find(id="responsive_page_template_content")
    
    if bans := page.find("div", class_="profile_ban_status"):

        for line in bans.prettify().splitlines():
            if line.endswith("on record"):
                # Account has been banned
                
                return line
            
def get_request_url(steam_account: str, matched_group: str):
    if matched_group in UNSUPPORTED_GROUPS:
        return False
    
    if matched_group == "CUSTOMURL":
        return "https://steamcommunity.com/" + steam_account
    elif matched_group == "steam_account":
        return "https://steamcommunity.com/profiles/" + steam_account
    else:
        return steam_account
    
@app.route("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static"), "favicon.ico", mimetype="image/vnd.microsoft.icon")
                
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ban/<steam_account>")
def ban_route(steam_account: str):
    if match := re.match(REGEX, steam_account):
        matched_group = match.lastgroup
        
        if url := get_request_url(steam_account, matched_group):  
            if bans := get_bans(url):
                return f"{bans} | {matched_group}"
            else:
                return f"No bans found for {steam_account}"
        else:
            return f"❌ Unsupported group '{matched_group}' found."
    else:
        return "🚫 Wrong Steam ID"
      
    
if __name__ == "__main__":
    #get_bans("76561198125638897") # MoreKombat (Gameban)
    #get_bans("76561199125501660") # Thorben (VAC)
    
    app.run(host="0.0.0.0", port=6546, debug=True)
    atexit.register(lambda: scheduler.shutdown())