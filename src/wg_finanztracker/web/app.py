import tempfile
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request

from wg_finanztracker.ocr.service import ReceiptOcrService
from wg_finanztracker.ocr.tesseract_service import TesseractOcrService
from wg_finanztracker.persistence.database import (
    delete_member,
    delete_receipt,
    get_member,
    get_members,
    get_receipt,
    get_receipts,
)

app = Flask(
    __name__,
    template_folder="../resources/templates",
    static_folder="../resources/static",
)

# Handyfotos sind groß, sollen den Webprozess aber
# nicht mit unbegrenzten Uploads belasten.
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ocr_service: ReceiptOcrService = TesseractOcrService()


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
        receipt_id=receipt_id,
    )


@app.post("/members/<int:member_id>/delete")
def delete_member_route(member_id: int):
    if get_member(member_id) is None:
        abort(404)

    delete_member(member_id)

    return redirect("/members")


@app.post("/receipts/<int:receipt_id>/delete")
def delete_receipt_route(receipt_id: int):
    if get_receipt(receipt_id) is None:
        abort(404)

    delete_receipt(receipt_id)

    return redirect("/receipts")


@app.route(
    "/receipts/upload",
    methods=["GET", "POST"],
)
def upload_receipt():
    if request.method == "GET":
        return render_template("receipt_upload.html")

    uploaded_file = request.files.get("receipt")

    if uploaded_file is None or uploaded_file.filename == "":
        return render_template(
            "receipt_upload.html",
            error="Bitte einen Kassenbon auswählen.",
        )

    suffix = Path(uploaded_file.filename).suffix.lower()

    if suffix not in {
        ".jpg",
        ".jpeg",
        ".png",
    }:
        return render_template(
            "receipt_upload.html",
            error="Nur JPG- und PNG-Dateien " "werden unterstützt.",
        )

    with tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
    ) as temporary_file:
        temporary_path = Path(temporary_file.name)

    try:
        # Unter Windows darf die Upload-Datei erst
        # nach dem Schließen des temporären Handles
        # erneut zum Schreiben geöffnet werden.
        uploaded_file.save(temporary_path)

        result = ocr_service.recognize(temporary_path)

    except (
        RuntimeError,
        ValueError,
        OSError,
    ) as error:
        return render_template(
            "receipt_upload.html",
            error=str(error),
        )

    finally:
        temporary_path.unlink(missing_ok=True)

    return render_template(
        "receipt_upload.html",
        result=result,
    )


if __name__ == "__main__":
    app.run(debug=True)
