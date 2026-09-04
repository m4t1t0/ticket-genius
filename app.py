"""Application entrypoint - uses the real factory from entrypoints.bootstrap."""

from entrypoints.bootstrap import create_app

# For flask run --app app:create_app
app = create_app()


if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
