import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "admin.login"
login_manager.login_message = "Inicia sesión para entrar al panel."

@event.listens_for(Engine, "connect")
def _sqlite_concurrencia(conexion, _registro):
    """SQLite: el servidor web lee mientras el Autopilot escribe (WAL) y espera bloqueos breves."""
    if isinstance(conexion, sqlite3.Connection):
        cur = conexion.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=10000")
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.close()
