from flask import Flask
from app.config import DevelopmentConfig, TestingConfig, ProductionConfig
from app.extensions import db, migrate

CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def create_app(config_name: str):
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])

    if config_name != "testing" and not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set")
    if config_name == "production" and not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL must be set in production")

    db.init_app(app)
    migrate.init_app(app, db)

    from app import models  # noqa: F401
    from app.routes import api
    app.register_blueprint(api)

    return app