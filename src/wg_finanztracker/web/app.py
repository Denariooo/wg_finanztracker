from flask import Flask, abort, render_template

from wg_finanztracker.persistence.database import get_members, get_receipt, get_receipts

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


@app.route("/receipts/<int:receipt_id>")
def receipt_detail(receipt_id: int):
    receipt = get_receipt(receipt_id)

    if receipt is None:
        abort(404)

    return render_template(
        "receipt_detail.html",
        receipt=receipt,
    )


if __name__ == "__main__":
    app.run(debug=True)
