INSERT INTO members (name, active)
VALUES ('Deniz', true),
       ('Max', true),
       ('Lisa', true);

INSERT INTO receipts (store, purchase_date, price_cents, paid_by)
VALUES ('REWE', '2026-08-18', 1097, 1),
       ('Lidl', '2026-08-19', 825, 2);

INSERT INTO items (receipt_id, name, price_cents)
VALUES (1, 'Milch', 149),
       (1, 'Pizza', 699),
       (1, 'Cola', 249),
       (2, 'Nudeln', 199),
       (2, 'Tomatensauce', 179),
       (2, 'Käse', 447);

INSERT INTO item_assignments (item_id, member_id)
VALUES (1, 1),
       (2, 1),
       (2, 2),
       (3, 2),
       (4, 1),
       (4, 2),
       (4, 3),
       (5, 2),
       (5, 3),
       (6, 3);