from extensions import db
from datetime import datetime


class GeneratedUsername(db.Model):
    __tablename__ = "generated_usernames"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Input parameters from user
    keyword = db.Column(db.String(256), nullable=False)       # kata kunci / tema
    style = db.Column(db.String(64), nullable=False)          # e.g. gaming, professional, cute
    total = db.Column(db.Integer, default=5)                  # jumlah username yang diminta

    # AI output — list of username strings stored as JSON
    usernames = db.Column(db.Text, nullable=False)            # JSON array of strings

    # Extra metadata from AI
    description = db.Column(db.Text, nullable=True)           # penjelasan singkat dari AI

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json

        usernames = []
        if self.usernames:
            try:
                usernames = json.loads(self.usernames)
                if not isinstance(usernames, list):
                    usernames = []
            except (json.JSONDecodeError, ValueError):
                usernames = []

        return {
            "id": self.id,
            "user_id": self.user_id,
            "keyword": self.keyword,
            "style": self.style,
            "total": self.total,
            "usernames": usernames,
            "description": self.description or "",
            "created_at": self.created_at.isoformat(),
        }
