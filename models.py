from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from flask_login import UserMixin
from uuid import uuid4

from database import db

class SteamAccount(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    added_by: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    steam_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    watching_since: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())
    banned_since: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    vac_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    game_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    times_banned: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self):
        return f"<SteamAccount {self.steam_id}>"
    
class AdminAccount(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uuid: Mapped[str] = mapped_column(String, default=str(uuid4()), unique=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    admin_lvl: Mapped[int] = mapped_column(Integer, default=0)
    
    def __repr__(self):
        return f"<AdminAccount {self.username}>"