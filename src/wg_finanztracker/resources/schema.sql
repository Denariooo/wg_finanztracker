CREATE TABLE members
(
    id   serial PRIMARY KEY,
    name varchar(255) NOT NULL,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE receipts
(
    id            serial PRIMARY KEY,
    store         varchar(255) NOT NULL,
    purchase_date date         NOT NULL,
    price_cents   int          NOT NULL CHECK ( price_cents >= 0),
    paid_by       int          NOT NULL,
    FOREIGN KEY (paid_by) REFERENCES members (id)
);

CREATE TABLE items
(
    id          serial PRIMARY KEY,
    receipt_id  int          NOT NULL,
    name        varchar(255) NOT NULL,
    price_cents int          NOT NULL CHECK ( price_cents >= 0),
    FOREIGN KEY (receipt_id) REFERENCES receipts (id) ON DELETE CASCADE
);

CREATE TABLE item_assignments
(
    item_id   int NOT NULL,
    member_id int NOT NULL,
    PRIMARY KEY (item_id, member_id),
    FOREIGN KEY (item_id) REFERENCES items (id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members (id)
);

CREATE TABLE payments (
    id serial PRIMARY KEY,
    from_member int NOT NULL REFERENCES members(id),
    to_member int NOT NULL REFERENCES members(id),
    amount_cents int NOT NULL CHECK (amount_cents > 0),
    payment_date date NOT NULL,
    CHECK (from_member <> to_member)
);