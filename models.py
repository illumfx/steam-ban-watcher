from sqlalchemy import Integer, String, Date
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from database import db

class SteamAccount(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    displayname: Mapped[str] = mapped_column(String, nullable=False)
    steam_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    watching_since: Mapped[str] = mapped_column(Date, default=datetime.now())