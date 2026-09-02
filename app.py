from dotenv import load_dotenv
from flask import Flask


def create_app():
    """Application factory."""
    load_dotenv()
    # TODO: Replace with actual entrypoints when implemented
    # from entrypoints.api import register_routes
    # from entrypoints.bootstrap import bootstrap

    app = Flask(__name__)

    # message_bus = bootstrap()
    # app.register_blueprint(register_routes(message_bus))

    @app.route("/")
    def index():
        return {
            "name": "Ticket Genius",
            "description": "Ticketing platform aggregating events from Ticketmaster and enabling ticket purchases",
            "version": "0.1.0",
            "status": "development",
        }

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


# For flask run --app app:create_app
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
