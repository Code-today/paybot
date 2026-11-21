from flask import Flask
from pages import user, admin
import api

app = Flask(__name__)
app.register_blueprint(user.bp)
app.register_blueprint(api.bp)
app.register_blueprint(admin.bp)

if __name__ == "__main__":
    app.run(port=5000)
