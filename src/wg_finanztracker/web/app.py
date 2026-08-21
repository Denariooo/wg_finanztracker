from flask import Flask, render_template

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
    return render_template("members.html")


@app.route("/receipts")
def receipts():
    return render_template("receipts.html")


if __name__ == "__main__":
    app.run(debug=True)
