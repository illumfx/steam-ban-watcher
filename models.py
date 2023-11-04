from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from database import db

class SteamAccount(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    steam_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    watching_since: Mapped[datetime] = mapped_column(DateTime, default=datetime.now())
    banned_since: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    vac_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    game_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    times_banned: Mapped[int] = mapped_column(Integer, default=0)