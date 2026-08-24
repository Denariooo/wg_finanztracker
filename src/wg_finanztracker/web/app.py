import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request

from wg_finanztracker.domain.cost_sharing import (
    calculate_debts,
    calculate_shares,
    calculate_total_debts,
)
from wg_finanztracker.domain.models import Item, Receipt
from wg_finanztracker.ocr.service import ReceiptOcrService
from wg_finanztracker.ocr.tesseract_service import TesseractOcrService
from wg_finanztracker.persistence.database import (
    add_receipt,
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
    receipt_entries = get_receipts()

    purchases = [receipt for _, receipt in receipt_entries]

    total_debts = calculate_total_debts(purchases)

    members_by_id = {}

    for receipt in purchases:
        members_by_id[receipt.paid_by.id] = receipt.paid_by

        for item in receipt.items:
            for member in item.assigned_to:
                members_by_id[member.id] = member

    recent_receipts = sorted(
        receipt_entries,
        key=lambda entry: entry[1].purchase_date,
        reverse=True,
    )[:5]

    return render_template(
        "index.html",
        total_debts=total_debts,
        members_by_id=members_by_id,
        recent_receipts=recent_receipts,
    )


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

    shares = calculate_shares(receipt)
    debts = calculate_debts(receipt)

    members_by_id = {
        receipt.paid_by.id: receipt.paid_by,
    }

    for item in receipt.items:
        for member in item.assigned_to:
            members_by_id[member.id] = member

    return render_template(
        "receipt_detail.html",
        receipt=receipt,
        receipt_id=receipt_id,
        shares=shares,
        debts=debts,
        members_by_id=members_by_id,
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
        return render_template("receipt_upload.html", members=get_members())

    uploaded_file = request.files.get("receipt")

    if uploaded_file is None or uploaded_file.filename == "":
        return render_template(
            "receipt_upload.html",
            error="Bitte einen Kassenbon auswählen.",
            members=get_members(),
        )

    suffix = Path(uploaded_file.filename).suffix.lower()

    if suffix not in {
        ".jpg",
        ".jpeg",
        ".png",
    }:
        return render_template(
            "receipt_upload.html",
            error="Nur JPG- und PNG-Dateien werden unterstützt.",
            members=get_members(),
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
            "receipt_upload.html", error=str(error), members=get_members()
        )

    finally:
        temporary_path.unlink(missing_ok=True)

    return render_template("receipt_upload.html", result=result, members=get_members())


@app.post("/receipts/create")
def create_receipt():
    members = get_members()

    members_by_id = {member.id: member for member in members}

    store = request.form.get(
        "store",
        "",
    ).strip()

    purchase_date_value = request.form.get(
        "purchase_date",
        "",
    ).strip()

    price_value = request.form.get(
        "price",
        "",
    ).strip()

    paid_by_value = request.form.get(
        "paid_by",
        "",
    ).strip()

    item_indexes = request.form.getlist("item_index")

    try:
        if not store:
            raise ValueError("Bitte einen Händler angeben.")

        if not purchase_date_value:
            raise ValueError("Bitte ein Datum angeben.")

        try:
            purchase_date = date.fromisoformat(purchase_date_value)
        except ValueError as error:
            raise ValueError("Das angegebene Datum ist ungültig.") from error

        if not price_value:
            raise ValueError("Bitte einen Gesamtbetrag angeben.")

        price_cents = parse_price_cents(price_value)

        if not paid_by_value:
            raise ValueError("Bitte auswählen, wer den Einkauf bezahlt hat.")

        try:
            paid_by_id = int(paid_by_value)
        except ValueError as error:
            raise ValueError("Ungültiges Mitglied.") from error

        paid_by = members_by_id.get(paid_by_id)

        if paid_by is None:
            raise ValueError("Das ausgewählte Mitglied existiert nicht.")

        if not item_indexes:
            raise ValueError("Der Kassenbon muss mindestens einen Artikel enthalten.")

        items: list[Item] = []

        for index in item_indexes:
            name = request.form.get(
                f"item_name_{index}",
                "",
            ).strip()

            item_price_value = request.form.get(
                f"item_price_{index}",
                "",
            ).strip()

            member_values = request.form.getlist(f"item_members_{index}")

            if not name:
                raise ValueError("Jeder Artikel benötigt einen Namen.")

            if not item_price_value:
                raise ValueError(f"Für den Artikel '{name}' fehlt der Preis.")

            item_price_cents = parse_price_cents(item_price_value)

            if not member_values:
                raise ValueError(
                    f"Der Artikel '{name}' muss mindestens "
                    "einem Mitglied zugeordnet werden."
                )

            assigned_members = []

            for member_value in member_values:
                try:
                    member_id = int(member_value)
                except ValueError as error:
                    raise ValueError("Ungültige Mitgliederzuordnung.") from error

                member = members_by_id.get(member_id)

                if member is None:
                    raise ValueError("Ein ausgewähltes Mitglied existiert nicht.")

                assigned_members.append(member)

            items.append(
                Item(
                    name=name,
                    price_cents=item_price_cents,
                    assigned_to=assigned_members,
                )
            )

        receipt = Receipt(
            store=store,
            purchase_date=purchase_date,
            price_cents=price_cents,
            paid_by=paid_by,
            items=items,
        )

        receipt_id = add_receipt(receipt)

    except ValueError as error:
        return render_template(
            "receipt_upload.html",
            error=str(error),
            members=members,
        )

    return redirect(f"/receipts/{receipt_id}")


def parse_price_cents(value: str) -> int:
    normalized = value.strip().replace(",", ".")

    try:
        amount = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("Ungültiger Preis.") from error

    if amount < 0:
        raise ValueError("Ein Preis darf nicht negativ sein.")

    # Es sollen höchstens zwei Nachkommastellen
    # angegeben werden.
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Ein Preis darf höchstens zwei Nachkommastellen haben.")

    return int(amount * 100)


if __name__ == "__main__":
    app.run(debug=True)
