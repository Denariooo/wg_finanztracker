from flask import Flask, render_template

from wg_finanztracker.persistence.database import get_members, get_receipts

app = Flask(
    __name__,
    template_folder="../resources/templates",
    static_folder="../resources/static",
)


@app.route("/")
@app.route("/index")
def index():
    return render_template("index.html")


@app.route("/members")
def members():
    return render_template("members.html", members=get_members())


@app.route("/receipts")
def receipts():
    return render_template("receipts.html", receipts=get_receipts())


if __name__ == "__main__":
    app.run(debug=True)
