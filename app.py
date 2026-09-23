from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    session
)

import os
import sys
import webbrowser
import threading
import subprocess
import shutil
import webview
import sqlite3
import json
import atexit
from datetime import datetime


# =========================================================
# FLASK
# =========================================================

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR
)

app.secret_key = os.urandom(32)
# Hər dəfə EVOPOS serveri yenidən başladıqda əvvəlki login sessiyaları
# avtomatik etibarsız olur və yenidən PIN tələb edilir.


DATABASE = "database.db"


# =========================================================
# İSTİFADƏÇİLƏR
# =========================================================

USERS = {
    "0555": {
        "name": "İlkin",
        "role": "Administrator"
    },

    "5002": {
        "name": "Nihad",
        "role": "Ofisiant"
    },

    "0808": {
        "name": "Əli",
        "role": "Ofisiant"
    }
}


# =========================================================
# DATABASE
# =========================================================

def get_db():
    database_path = os.path.join(BASE_DIR, "database.db")

    connection = sqlite3.connect(database_path)

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# DATABASE INIT
# =========================================================

def init_database():

    connection = get_db()

    cursor = connection.cursor()


    # -----------------------------------------------------
    # ORDERS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            table_number INTEGER NOT NULL,

            total REAL DEFAULT 0,

            status TEXT DEFAULT 'Yeni',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)


    # -----------------------------------------------------
    # ORDER ITEMS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            order_id INTEGER NOT NULL,

            product_name TEXT NOT NULL,

            price REAL NOT NULL,

            quantity INTEGER NOT NULL,

            FOREIGN KEY(order_id)
            REFERENCES orders(id)

        )
    """)


    # -----------------------------------------------------
    # PRODUCTS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            price REAL NOT NULL,

            category TEXT NOT NULL

        )
    """)


    # =====================================================
    # ORDERS SÜTUNLARINI YOXLAYIRIQ
    # =====================================================

    columns = cursor.execute(
        "PRAGMA table_info(orders)"
    ).fetchall()


    column_names = [
        column["name"]
        for column in columns
    ]


    if "payment_method" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN payment_method TEXT
        """)


    if "paid_amount" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN paid_amount REAL DEFAULT 0
        """)


    if "change_amount" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN change_amount REAL DEFAULT 0
        """)


    if "paid_at" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN paid_at TEXT
        """)

    # =====================================================
    # MƏTBƏX STATUSU
    # =====================================================

    if "kitchen_status" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN kitchen_status TEXT DEFAULT 'Yeni'
        """)

        cursor.execute("""
            UPDATE orders
            SET kitchen_status =
                CASE
                    WHEN status = 'Tamamlandı' THEN 'Tamamlandı'
                    ELSE 'Yeni'
                END
        """)

    # =====================================================
    # OFİSİANT
    # =====================================================

    if "waiter_name" not in column_names:

        cursor.execute("""
            ALTER TABLE orders
            ADD COLUMN waiter_name TEXT
        """)


    # =====================================================
    # GÜNLÜK NÖVBƏ / HESABAT
    # =====================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_shifts (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            work_date TEXT NOT NULL,

            opened_at TEXT NOT NULL,

            closed_at TEXT,

            status TEXT DEFAULT 'Açıq',

            report_json TEXT

        )
    """)

    today = datetime.now().strftime("%Y-%m-%d")

    open_shift = cursor.execute("""
        SELECT id
        FROM daily_shifts
        WHERE work_date = ?
        AND status = 'Açıq'
        ORDER BY id DESC
        LIMIT 1
    """, (today,)).fetchone()

    if not open_shift:

        cursor.execute("""
            INSERT INTO daily_shifts
            (
                work_date,
                opened_at,
                status
            )
            VALUES (?, ?, ?)
        """, (
            today,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Açıq"
        ))


    # =====================================================
    # DEFAULT MƏHSULLAR
    # =====================================================

    product_count = cursor.execute(
        "SELECT COUNT(*) AS count FROM products"
    ).fetchone()["count"]


    if product_count == 0:

        default_products = [

            (
                "Hamburger",
                8.00,
                "Yeməklər"
            ),

            (
                "Pizza",
                12.00,
                "Yeməklər"
            ),

            (
                "Qril toyuq",
                10.00,
                "Yeməklər"
            ),

            (
                "Dönər",
                3.00,
                "Yeməklər"
            ),

            (
                "Əri kartof",
                4.00,
                "Yeməklər"
            ),

            (
                "Coca-Cola",
                2.00,
                "İçkilər"
            ),

            (
                "Dondurma",
                4.00,
                "Desertlər"
            ),

            (
                "Cheesecake",
                6.00,
                "Desertlər"
            )

        ]


        cursor.executemany(
            """
            INSERT INTO products
            (name, price, category)

            VALUES (?, ?, ?)
            """,
            default_products
        )


    connection.commit()

    connection.close()


# =========================================================
# LOGIN CHECK
# =========================================================

@app.before_request
def check_login():

    allowed_paths = [
        "/login",
        "/static/"
    ]


    if request.path.startswith("/static/"):

        return


    if request.path == "/login":

        return


    if "user" not in session:

        if request.path.startswith("/api/"):

            return jsonify({
                "success": False,
                "message": "Giriş tələb olunur."
            }), 401


        return redirect("/login")


    user = session["user"]


    # =====================================================
    # OFİSİANT İCAZƏLƏRİ
    # =====================================================

    if user["role"] == "Ofisiant":

        # Menyu səhifəsi administrator üçündür

        if request.path == "/menu":

            return redirect("/")


        # Hesabat administrator üçündür

        if request.path == "/reports":

            return redirect("/")


        # Menyu dəyişdirmə əməliyyatları

        if request.path.startswith("/api/menu"):

            if request.method in [
                "POST",
                "PUT",
                "DELETE"
            ]:

                return jsonify({
                    "success": False,
                    "message":
                        "Bu əməliyyat üçün Administrator icazəsi lazımdır."
                }), 403


        # Hesabat API və günlük hesabat səhifələri

        if (
            request.path.startswith("/api/reports")
            or request.path.startswith("/daily-report")
        ):

            return jsonify({
                "success": False,
                "message":
                    "Bu bölmə yalnız Administrator üçündür."
            }), 403


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":

        if "user" in session:

            return redirect("/")

        return render_template("login.html")


    data = request.get_json(silent=True)


    if data:

        pin = str(
            data.get("pin", "")
        ).strip()

    else:

        pin = str(
            request.form.get("pin", "")
        ).strip()


    if pin not in USERS:

        return jsonify({
            "success": False,
            "message": "PIN kod yanlışdır."
        }), 401


    session["user"] = USERS[pin]

    session.permanent = False


    return jsonify({
        "success": True,
        "user": USERS[pin]
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================================================
# CURRENT USER
# =========================================================

@app.route("/api/current-user")
def current_user():

    if "user" not in session:

        return jsonify({
            "success": False
        }), 401


    return jsonify({
        "success": True,
        "user": session["user"]
    })


# =========================================================
# ƏSAS SƏHİFƏ
# =========================================================

@app.route("/")
def index():

    return render_template("index.html")


# =========================================================
# ORDER PAGE
# =========================================================

@app.route("/order/<int:table_number>")
def order_page(table_number):

    return render_template(
        "order.html",
        table_number=table_number
    )


# =========================================================
# MENU PAGE
# =========================================================

@app.route("/menu")
def menu_page():

    return render_template("menu.html")


# =========================================================
# ORDERS PAGE
# =========================================================

@app.route("/orders")
def orders_page():

    return render_template("orders.html")


# =========================================================
# KITCHEN PAGE
# =========================================================

@app.route("/kitchen")
def kitchen_page():

    return render_template("kitchen.html")


# =========================================================
# ORDER VIEW
# =========================================================

@app.route("/order-view/<int:order_id>")
def order_view_page(order_id):

    return render_template(
        "order_view.html",
        order_id=order_id
    )


# =========================================================
# REPORTS PAGE
# =========================================================

@app.route("/reports")
def reports_page():

    return render_template("reports.html")


# =========================================================
# RECEIPT
# =========================================================

@app.route("/receipt/<int:order_id>")
def receipt_page(order_id):

    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return "Sifariş tapılmadı.", 404


    items = cursor.execute(
        """
        SELECT *
        FROM order_items
        WHERE order_id = ?

        ORDER BY id ASC
        """,
        (order_id,)
    ).fetchall()


    connection.close()


    return render_template(
        "receipt.html",
        order=order,
        items=items
    )


# =========================================================
# MENU API
# =========================================================

@app.route("/api/menu", methods=["GET"])
def get_menu():

    connection = get_db()

    cursor = connection.cursor()


    products = cursor.execute(
        """
        SELECT
            id,
            name,
            price,
            category
        FROM products
        ORDER BY id ASC
        """
    ).fetchall()


    connection.close()


    return jsonify([
        {
            "id": product["id"],
            "name": product["name"],
            "price": product["price"],
            "category": product["category"]
        }

        for product in products
    ])


# =========================================================
# ADD PRODUCT
# =========================================================

@app.route("/api/menu", methods=["POST"])
def add_menu_product():

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message": "Məlumat göndərilməyib."
        }), 400


    name = str(
        data.get("name", "")
    ).strip()


    category = str(
        data.get("category", "")
    ).strip()


    try:

        price = float(
            data.get("price", 0)
        )

    except:

        price = 0


    if not name:

        return jsonify({
            "success": False,
            "message": "Məhsul adı boş ola bilməz."
        }), 400


    if price <= 0:

        return jsonify({
            "success": False,
            "message": "Qiymət düzgün deyil."
        }), 400


    if not category:

        return jsonify({
            "success": False,
            "message": "Kateqoriya seçilməyib."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    cursor.execute(
        """
        INSERT INTO products
        (name, price, category)

        VALUES (?, ?, ?)
        """,
        (
            name,
            price,
            category
        )
    )


    product_id = cursor.lastrowid


    connection.commit()

    connection.close()


    return jsonify({

        "success": True,

        "message":
            "Məhsul əlavə edildi.",

        "product_id":
            product_id

    })


# =========================================================
# UPDATE PRODUCT
# =========================================================

@app.route("/api/menu/<int:product_id>", methods=["PUT"])
def update_menu_product(product_id):

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message": "Məlumat göndərilməyib."
        }), 400


    name = str(
        data.get("name", "")
    ).strip()


    category = str(
        data.get("category", "")
    ).strip()


    try:

        price = float(
            data.get("price", 0)
        )

    except:

        price = 0


    if not name:

        return jsonify({
            "success": False,
            "message": "Məhsul adı boş ola bilməz."
        }), 400


    if price <= 0:

        return jsonify({
            "success": False,
            "message": "Qiymət düzgün deyil."
        }), 400


    if not category:

        return jsonify({
            "success": False,
            "message": "Kateqoriya seçilməyib."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    product = cursor.execute(
        """
        SELECT id
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if not product:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Məhsul tapılmadı."
        }), 404


    cursor.execute(
        """
        UPDATE products

        SET
            name = ?,
            price = ?,
            category = ?

        WHERE id = ?
        """,
        (
            name,
            price,
            category,
            product_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({
        "success": True,
        "message": "Məhsul yeniləndi."
    })


# =========================================================
# DELETE PRODUCT
# =========================================================

@app.route("/api/menu/<int:product_id>", methods=["DELETE"])
def delete_menu_product(product_id):

    connection = get_db()

    cursor = connection.cursor()


    product = cursor.execute(
        """
        SELECT id
        FROM products
        WHERE id = ?
        """,
        (product_id,)
    ).fetchone()


    if not product:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Məhsul tapılmadı."
        }), 404


    cursor.execute(
        """
        DELETE FROM products
        WHERE id = ?
        """,
        (product_id,)
    )


    connection.commit()

    connection.close()


    return jsonify({
        "success": True,
        "message": "Məhsul silindi."
    })


# =========================================================
# CREATE ORDER
# =========================================================

@app.route("/api/order", methods=["POST"])
def create_order():

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message": "Sifariş məlumatı göndərilməyib."
        }), 400


    table_number = data.get("table_number")

    items = data.get("items", [])


    if not table_number:

        return jsonify({
            "success": False,
            "message": "Masa nömrəsi yoxdur."
        }), 400


    if not isinstance(items, list) or not items:

        return jsonify({
            "success": False,
            "message": "Sifarişdə məhsul yoxdur."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    total = 0


    for item in items:

        try:

            price = float(
                item.get("price", 0)
            )

            quantity = int(
                item.get("quantity", 0)
            )

        except:

            connection.close()

            return jsonify({
                "success": False,
                "message": "Məhsul məlumatı düzgün deyil."
            }), 400


        if quantity <= 0:

            continue


        total += price * quantity


    if total <= 0:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Sifariş məbləği 0 ola bilməz."
        }), 400


    created_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    cursor.execute(
        """
                INSERT INTO orders
        (
            table_number,
            total,
            status,
            kitchen_status,
            created_at,
            waiter_name
        )

        VALUES (?, ?, ?, ?, ?, ?)
        """,
                (
            table_number,
            total,
            "Yeni",
            "Yeni",
            created_at,
            session.get("user", {}).get("name", "Naməlum")
        )
    )


    order_id = cursor.lastrowid


    for item in items:

        try:

            price = float(
                item.get("price", 0)
            )

            quantity = int(
                item.get("quantity", 0)
            )

        except:

            continue


        if quantity <= 0:

            continue


        product_name = str(
            item.get(
                "name",
                "Məhsul"
            )
        )


        cursor.execute(
            """
            INSERT INTO order_items
            (
                order_id,
                product_name,
                price,
                quantity
            )

            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                product_name,
                price,
                quantity
            )
        )


    connection.commit()

    connection.close()


    return jsonify({

        "success": True,

        "message":
            "Sifariş yaradıldı.",

        "order_id":
            order_id,

        "total":
            total

    })


# =========================================================
# GET ORDER
# =========================================================

@app.route("/api/order/<int:order_id>")
def get_order(order_id):

    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Sifariş tapılmadı."
        }), 404


    items = cursor.execute(
        """
        SELECT
            id,
            order_id,
            product_name,
            price,
            quantity
        FROM order_items
        WHERE order_id = ?
        ORDER BY id ASC
        """,
        (order_id,)
    ).fetchall()


    connection.close()


    return jsonify({

        "success": True,

        "order": dict(order),

        "items": [
            dict(item)
            for item in items
        ]

    })


# =========================================================
# UPDATE EXISTING ORDER
# =========================================================

@app.route(
    "/api/order/<int:order_id>/update",
    methods=["PUT"]
)
def update_order(order_id):

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message": "Məlumat göndərilməyib."
        }), 400


    items = data.get("items", [])


    if not isinstance(items, list) or not items:

        return jsonify({
            "success": False,
            "message": "Sifarişdə məhsul yoxdur."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Sifariş tapılmadı."
        }), 404


    total = 0


    clean_items = []


    for item in items:

        try:

            name = str(
                item.get("name", "")
            ).strip()

            price = float(
                item.get("price", 0)
            )

            quantity = int(
                item.get("quantity", 0)
            )

        except:

            continue


        if not name:

            continue


        if price < 0:

            continue


        if quantity <= 0:

            continue


        total += price * quantity


        clean_items.append(
            (
                name,
                price,
                quantity
            )
        )


    if not clean_items:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Sifarişdə məhsul yoxdur."
        }), 400


    # =====================================================
    # TAMAMLANMIŞ KÖHNƏ SİFARİŞ
    # =====================================================
    # Brauzerdə köhnə sifariş ID-si qalıbsa belə,
    # tamamlanmış sifarişi dəyişmirik.
    # Onun əvəzinə həmin masa üçün YENİ sifariş yaradırıq.

    if order["status"] == "Tamamlandı":

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute(
            """
            INSERT INTO orders
            (
                table_number,
                total,
                status,
                kitchen_status,
                created_at,
                waiter_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order["table_number"],
                total,
                "Yeni",
                "Yeni",
                created_at,
                session.get("user", {}).get("name", "Naməlum")
            )
        )

        new_order_id = cursor.lastrowid

        for name, price, quantity in clean_items:

            cursor.execute(
                """
                INSERT INTO order_items
                (
                    order_id,
                    product_name,
                    price,
                    quantity
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    new_order_id,
                    name,
                    price,
                    quantity
                )
            )

        connection.commit()
        connection.close()

        return jsonify({
            "success": True,
            "message": "Yeni sifariş yaradıldı.",
            "order_id": new_order_id,
            "total": total,
            "new_order": True
        })


    # Köhnə məhsulları sil

    cursor.execute(
        """
        DELETE FROM order_items
        WHERE order_id = ?
        """,
        (order_id,)
    )


    # Yeni məhsulları yaz

    for name, price, quantity in clean_items:

        cursor.execute(
            """
            INSERT INTO order_items
            (
                order_id,
                product_name,
                price,
                quantity
            )

            VALUES (?, ?, ?, ?)
            """,
            (
                order_id,
                name,
                price,
                quantity
            )
        )


    cursor.execute(
        """
               UPDATE orders

        SET total = ?

        WHERE id = ?
        """,
        (
            total,
            order_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({

        "success": True,

        "message":
            "Sifariş yeniləndi.",

        "order_id":
            order_id,

        "total":
            total

    })


# =========================================================
# DELETE / CANCEL ORDER
# =========================================================

@app.route(
    "/api/order/<int:order_id>/delete",
    methods=["DELETE"]
)
def delete_order(order_id):

    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message": "Sifariş tapılmadı."
        }), 404


    if order["status"] == "Tamamlandı":

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Tamamlanmış sifariş ləğv edilə bilməz."
        }), 400


    # Sifarişi silmirik.
    # Günlük hesabat üçün ləğv tarixçəsini saxlayırıq.
    cursor.execute(
        """
        UPDATE orders
        SET
            status = 'Ləğv edildi',
            kitchen_status = 'Tamamlandı'
        WHERE id = ?
        """,
        (order_id,)
    )


    connection.commit()

    connection.close()


    return jsonify({
        "success": True,
        "message": "Sifariş ləğv edildi."
    })


# =========================================================
# PAYMENT
# =========================================================

@app.route(
    "/api/order/<int:order_id>/payment",
    methods=["POST"]
)
def payment_order(order_id):

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message":
                "Ödəniş məlumatı göndərilməyib."
        }), 400


    payment_method = str(
        data.get(
            "payment_method",
            ""
        )
    ).strip()


    if payment_method not in [
        "Nağd",
        "Kart"
    ]:

        return jsonify({
            "success": False,
            "message":
                "Ödəniş üsulu düzgün deyil."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT *
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Sifariş tapılmadı."
        }), 404


    if order["status"] == "Tamamlandı":

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Bu sifariş artıq tamamlanıb."
        }), 400


    total = float(
        order["total"] or 0
    )


    try:

        paid_amount = float(
            data.get(
                "paid_amount",
                0
            )
        )

    except:

        paid_amount = 0


    if payment_method == "Kart":

        paid_amount = total


    if payment_method == "Nağd":

        if paid_amount < total:

            connection.close()

            return jsonify({
                "success": False,
                "message":
                    "Verilən məbləğ sifariş məbləğindən azdır."
            }), 400


    change_amount = max(
        paid_amount - total,
        0
    )


    paid_at = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


    cursor.execute(
        """
        UPDATE orders

        SET
            status = ?,
            payment_method = ?,
            paid_amount = ?,
            change_amount = ?,
            paid_at = ?

        WHERE id = ?
        """,
        (
            "Tamamlandı",
            payment_method,
            paid_amount,
            change_amount,
            paid_at,
            order_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({

        "success": True,

        "message":
            "Ödəniş tamamlandı.",

        "order_id":
            order_id,

        "total":
            total,

        "payment_method":
            payment_method,

        "paid_amount":
            paid_amount,

        "change_amount":
            change_amount,

        "paid_at":
            paid_at

    })


# =========================================================
# ALL ORDERS
# =========================================================

@app.route("/api/orders")
def get_orders():

    connection = get_db()

    cursor = connection.cursor()

    # Sifarişlər yalnız cari açıq günə aid göstərilir.
    # Gün bağlandıqdan sonra ilk sifariş sorğusunda yeni gün açılır.
    shift = get_open_shift(connection)

    if not shift:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        work_date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO daily_shifts
            (work_date, opened_at, status)
            VALUES (?, ?, 'Açıq')
        """, (work_date, now))

        connection.commit()

        shift = cursor.execute("""
            SELECT *
            FROM daily_shifts
            WHERE id = ?
        """, (cursor.lastrowid,)).fetchone()

    orders = cursor.execute(
        """
        SELECT
            id,
            table_number,
            total,
            status,
            created_at,
            payment_method,
            paid_amount,
            change_amount,
            paid_at,
            waiter_name

        FROM orders
        WHERE created_at >= ?

        ORDER BY id DESC
        """,
        (shift["opened_at"],)
    ).fetchall()


    connection.close()


    return jsonify([

        {
            "id":
                order["id"],

            "table_number":
                order["table_number"],

            "total":
                order["total"] or 0,

            "status":
                order["status"],

            "created_at":
                order["created_at"],

            "payment_method":
                order["payment_method"],

            "paid_amount":
                order["paid_amount"] or 0,

            "change_amount":
                order["change_amount"] or 0,

            "paid_at":
                order["paid_at"],

            "waiter_name":
                order["waiter_name"]

        }

        for order in orders

    ])


# =========================================================
# TABLES
# =========================================================

@app.route("/api/tables")
def get_tables():

    connection = get_db()

    cursor = connection.cursor()


    tables = []


    for table_number in range(1, 13):

        active_order = cursor.execute(
            """
            SELECT
                id,
                table_number,
                total,
                status,
                created_at

            FROM orders

            WHERE table_number = ?

            AND status NOT IN ('Tamamlandı', 'Ləğv edildi')

            ORDER BY id DESC

            LIMIT 1
            """,
            (table_number,)
        ).fetchone()


        if active_order:

            tables.append({

                "table_number":
                    table_number,

                "status":
                    "Məşğuldur",

                "order_id":
                    active_order["id"],

                "total":
                    active_order["total"] or 0,

                "created_at":
                    active_order["created_at"]

            })

        else:

            tables.append({

                "table_number":
                    table_number,

                "status":
                    "Boşdur",

                "order_id":
                    None,

                "total":
                    0,

                "created_at":
                    None

            })


    connection.close()


    return jsonify(tables)


# =========================================================
# KITCHEN ORDERS
# =========================================================

@app.route("/api/kitchen/orders")
def kitchen_orders():

    connection = get_db()

    cursor = connection.cursor()

    # Mətbəx də yalnız cari açıq günün sifarişlərini göstərir.
    shift = get_open_shift(connection)

    if not shift:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        work_date = datetime.now().strftime("%Y-%m-%d")

        cursor.execute("""
            INSERT INTO daily_shifts
            (work_date, opened_at, status)
            VALUES (?, ?, 'Açıq')
        """, (work_date, now))

        connection.commit()

        shift = cursor.execute("""
            SELECT *
            FROM daily_shifts
            WHERE id = ?
        """, (cursor.lastrowid,)).fetchone()

    orders = cursor.execute(
        """
        SELECT *

        FROM orders

        WHERE kitchen_status != 'Tamamlandı'
        AND status != 'Ləğv edildi'
        AND created_at >= ?

        ORDER BY id ASC
        """,
        (shift["opened_at"],)
    ).fetchall()


    result = []


    for order in orders:

        items = cursor.execute(
            """
            SELECT
                id,
                order_id,
                product_name,
                price,
                quantity

            FROM order_items

            WHERE order_id = ?

            ORDER BY id ASC
            """,
            (order["id"],)
        ).fetchall()


        result.append({

            "id":
                order["id"],

            "table_number":
                order["table_number"],

            "total":
                order["total"] or 0,

                        "status":
                order["kitchen_status"],

            "payment_status":
                order["status"],

            "created_at":
                order["created_at"],

            "items": [

                {

                    "id":
                        item["id"],

                    "product_name":
                        item["product_name"],

                    "name":
                        item["product_name"],

                    "price":
                        item["price"],

                    "quantity":
                        item["quantity"]

                }

                for item in items

            ]

        })


    connection.close()


    return jsonify(result)


# =========================================================
# KITCHEN STATUS
# =========================================================

@app.route(
    "/api/kitchen/order/<int:order_id>/status",
    methods=["PUT"]
)
def update_kitchen_status(order_id):

    data = request.get_json(silent=True)


    if not data:

        return jsonify({
            "success": False,
            "message":
                "Status məlumatı göndərilməyib."
        }), 400


    new_status = str(
        data.get(
            "status",
            ""
        )
    ).strip()


    allowed_statuses = [

        "Yeni",

        "Hazırlanır",

        "Hazırdır",

        "Tamamlandı"

    ]


    if new_status not in allowed_statuses:

        return jsonify({
            "success": False,
            "message":
                "Status düzgün deyil."
        }), 400


    connection = get_db()

    cursor = connection.cursor()


    order = cursor.execute(
        """
        SELECT id
        FROM orders
        WHERE id = ?
        """,
        (order_id,)
    ).fetchone()


    if not order:

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Sifariş tapılmadı."
        }), 404


    cursor.execute(
        """
        UPDATE orders

        SET kitchen_status = ?

        WHERE id = ?
        """,
        (
            new_status,
            order_id
        )
    )


    connection.commit()

    connection.close()


    return jsonify({
        "success": True,
        "message":
            "Status dəyişdirildi."
    })



# =========================================================
# DAILY REPORT HELPERS
# =========================================================

def get_open_shift(connection):
    cursor = connection.cursor()

    return cursor.execute("""
        SELECT *
        FROM daily_shifts
        WHERE status = 'Açıq'
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()


def build_daily_report(connection, opened_at, closed_at=None):
    cursor = connection.cursor()

    end_time = closed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    completed = cursor.execute("""
        SELECT
            COUNT(*) AS order_count,
            COALESCE(SUM(total), 0) AS sales,
            COALESCE(SUM(
                CASE WHEN payment_method = 'Nağd'
                THEN total ELSE 0 END
            ), 0) AS cash_sales,
            COALESCE(SUM(
                CASE WHEN payment_method = 'Kart'
                THEN total ELSE 0 END
            ), 0) AS card_sales
        FROM orders
        WHERE status = 'Tamamlandı'
        AND created_at >= ?
        AND created_at <= ?
    """, (opened_at, end_time)).fetchone()

    cancelled = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM orders
        WHERE status = 'Ləğv edildi'
        AND created_at >= ?
        AND created_at <= ?
    """, (opened_at, end_time)).fetchone()

    unpaid = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM orders
        WHERE status != 'Tamamlandı'
        AND status != 'Ləğv edildi'
        AND created_at >= ?
        AND created_at <= ?
    """, (opened_at, end_time)).fetchone()

    products = cursor.execute("""
        SELECT
            oi.product_name,
            SUM(oi.quantity) AS quantity,
            SUM(oi.price * oi.quantity) AS amount
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.status = 'Tamamlandı'
        AND o.created_at >= ?
        AND o.created_at <= ?
        GROUP BY oi.product_name
        ORDER BY quantity DESC, oi.product_name ASC
    """, (opened_at, end_time)).fetchall()

    waiters = cursor.execute("""
        SELECT
            COALESCE(o.waiter_name, 'Naməlum') AS waiter_name,
            COUNT(DISTINCT o.id) AS order_count,
            COUNT(DISTINCT o.table_number) AS table_count,
            COALESCE(SUM(o.total), 0) AS sales,
            COALESCE(SUM(oi.quantity), 0) AS item_count
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        WHERE o.status = 'Tamamlandı'
        AND o.created_at >= ?
        AND o.created_at <= ?
        GROUP BY COALESCE(o.waiter_name, 'Naməlum')
        ORDER BY sales DESC, waiter_name ASC
    """, (opened_at, end_time)).fetchall()

    tables = cursor.execute("""
        SELECT
            o.table_number,
            COALESCE(o.waiter_name, 'Naməlum') AS waiter_name,
            COUNT(DISTINCT o.id) AS order_count,
            COALESCE(SUM(o.total), 0) AS sales
        FROM orders o
        WHERE o.status = 'Tamamlandı'
        AND o.created_at >= ?
        AND o.created_at <= ?
        GROUP BY o.table_number, COALESCE(o.waiter_name, 'Naməlum')
        ORDER BY o.table_number ASC, waiter_name ASC
    """, (opened_at, end_time)).fetchall()

    payment_counts = cursor.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN payment_method = 'Nağd' THEN 1 ELSE 0 END), 0) AS cash_count,
            COALESCE(SUM(CASE WHEN payment_method = 'Kart' THEN 1 ELSE 0 END), 0) AS card_count
        FROM orders
        WHERE status = 'Tamamlandı'
        AND created_at >= ?
        AND created_at <= ?
    """, (opened_at, end_time)).fetchone()

    total_sales = float(completed["sales"] or 0)
    order_count = int(completed["order_count"] or 0)

    return {
        "opened_at": opened_at,
        "closed_at": closed_at,
        "total_sales": total_sales,
        "cash_sales": float(completed["cash_sales"] or 0),
        "card_sales": float(completed["card_sales"] or 0),
        "total_orders": order_count,
        "cancelled_orders": int(cancelled["count"] or 0),
        "unpaid_orders": int(unpaid["count"] or 0),
        "average_order": (total_sales / order_count) if order_count else 0,
        "cash_count": int(payment_counts["cash_count"] or 0),
        "card_count": int(payment_counts["card_count"] or 0),
        "products": [
            {
                "name": row["product_name"],
                "quantity": int(row["quantity"] or 0),
                "amount": float(row["amount"] or 0)
            }
            for row in products
        ],
        "waiters": [
            {
                "name": row["waiter_name"],
                "orders": int(row["order_count"] or 0),
                "tables": int(row["table_count"] or 0),
                "items": int(row["item_count"] or 0),
                "sales": float(row["sales"] or 0)
            }
            for row in waiters
        ],
        "tables": [
            {
                "table": int(row["table_number"]),
                "waiter": row["waiter_name"],
                "orders": int(row["order_count"] or 0),
                "sales": float(row["sales"] or 0)
            }
            for row in tables
        ]
    }


# =========================================================
# REPORTS API
# =========================================================

@app.route("/api/reports")
def reports_api():

    connection = get_db()

    try:
        shift = get_open_shift(connection)

        if not shift:
            # Gün bağlanıbsa yeni istifadə sessiyası üçün
            # yeni növbə açılır.
            cursor = connection.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            work_date = datetime.now().strftime("%Y-%m-%d")

            cursor.execute("""
                INSERT INTO daily_shifts
                (work_date, opened_at, status)
                VALUES (?, ?, 'Açıq')
            """, (work_date, now))

            connection.commit()

            shift = cursor.execute("""
                SELECT *
                FROM daily_shifts
                WHERE id = ?
            """, (cursor.lastrowid,)).fetchone()

        report = build_daily_report(
            connection,
            shift["opened_at"]
        )

        # Ümumi tarixçə üçün köhnə sahələri də saxlayırıq.
        cursor = connection.cursor()

        total_sales = cursor.execute("""
            SELECT COALESCE(SUM(total), 0) AS value
            FROM orders
            WHERE status = 'Tamamlandı'
        """).fetchone()["value"]

        recent_orders = cursor.execute("""
            SELECT
                id,
                table_number,
                total,
                status,
                created_at,
                payment_method,
                paid_amount,
                change_amount,
                paid_at,
                waiter_name
            FROM orders
            ORDER BY id DESC
            LIMIT 10
        """).fetchall()

        report["shift_id"] = shift["id"]
        report["work_date"] = shift["work_date"]
        report["total_sales_all_time"] = float(total_sales or 0)
        report["shift_status"] = shift["status"]
        report["recent"] = [
            {
                "id": row["id"],
                "table_number": row["table_number"],
                "total": row["total"] or 0,
                "status": row["status"],
                "created_at": row["created_at"],
                "payment_method": row["payment_method"],
                "paid_amount": row["paid_amount"] or 0,
                "change_amount": row["change_amount"] or 0,
                "paid_at": row["paid_at"],
                "waiter_name": row["waiter_name"]
            }
            for row in recent_orders
        ]

        # Köhnə reports.html sahələri
        report["today_sales"] = report["total_sales"]
        report["today_cash_sales"] = report["cash_sales"]
        report["today_card_sales"] = report["card_sales"]
        report["completed_orders"] = report["total_orders"]
        report["active_orders"] = report["unpaid_orders"]
        report["cancelled_or_unpaid"] = report["cancelled_orders"]

        connection.close()

        return jsonify({
            "success": True,
            **report
        })

    except Exception as error:
        connection.close()

        return jsonify({
            "success": False,
            "message": "Hesabat məlumatları alınmadı.",
            "error": str(error)
        }), 500


# =========================================================
# DAILY REPORT PRINT
# =========================================================

@app.route("/daily-report/<int:shift_id>")
def daily_report_page(shift_id):

    connection = get_db()
    cursor = connection.cursor()

    shift = cursor.execute("""
        SELECT *
        FROM daily_shifts
        WHERE id = ?
    """, (shift_id,)).fetchone()

    if not shift:
        connection.close()
        return "Günlük hesabat tapılmadı.", 404

    closed_at = shift["closed_at"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = build_daily_report(
        connection,
        shift["opened_at"],
        closed_at
    )

    report["shift_id"] = shift["id"]
    report["work_date"] = shift["work_date"]
    report["shift_status"] = shift["status"]

    connection.close()

    return render_template(
        "daily_report.html",
        report=report
    )


# =========================================================
# CLOSE DAY
# =========================================================

@app.route("/api/reports/close-day", methods=["POST"])
def close_day():

    user = session.get("user", {})

    if user.get("role") != "Administrator":
        return jsonify({
            "success": False,
            "message": "Günü yalnız Administrator bağlaya bilər."
        }), 403

    connection = get_db()
    cursor = connection.cursor()

    shift = get_open_shift(connection)

    if not shift:
        connection.close()
        return jsonify({
            "success": False,
            "message": "Açıq gün tapılmadı."
        }), 400

    # Gün bağlananda əvvəlki gündən qalan və ya cari gündə açıq qalan
    # bütün aktiv sifarişləri yeni günə daşımırıq. Onları tarixçədə
    # qorumaq üçün "Ləğv edildi" kimi bağlayırıq.
    # Beləliklə yeni gün başlayanda aktiv sifariş və məşğul masa qalmır.
    active_rows = cursor.execute("""
        SELECT id
        FROM orders
        WHERE status NOT IN ('Tamamlandı', 'Ləğv edildi')
    """).fetchall()

    closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if active_rows:
        cursor.execute("""
            UPDATE orders
            SET
                status = 'Ləğv edildi',
                kitchen_status = 'Tamamlandı'
            WHERE status NOT IN ('Tamamlandı', 'Ləğv edildi')
        """)

    report = build_daily_report(
        connection,
        shift["opened_at"],
        closed_at
    )

    cursor.execute("""
        UPDATE daily_shifts
        SET
            closed_at = ?,
            status = 'Bağlı',
            report_json = ?
        WHERE id = ?
    """, (
        closed_at,
        json.dumps(report, ensure_ascii=False),
        shift["id"]
    ))

    connection.commit()

    connection.close()

    return jsonify({
        "success": True,
        "message": "Gün uğurla bağlandı.",
        "shift_id": shift["id"],
        "report": report
    })


# =========================================================
# REPORT HISTORY
# =========================================================

@app.route("/api/reports/history")
def report_history():

    connection = get_db()
    cursor = connection.cursor()

    rows = cursor.execute("""
        SELECT
            id,
            work_date,
            opened_at,
            closed_at,
            status
        FROM daily_shifts
        ORDER BY id DESC
        LIMIT 30
    """).fetchall()

    connection.close()

    return jsonify([
        {
            "id": row["id"],
            "work_date": row["work_date"],
            "opened_at": row["opened_at"],
            "closed_at": row["closed_at"],
            "status": row["status"]
        }
        for row in rows
    ])


# =========================================================
# DATABASE INIT
# =========================================================

init_database()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    # =====================================================
    # EVOPOS DAXİLİ PƏNCƏRƏ
    # =====================================================
    # Flask server arxa planda işləyir.
    # İstifadəçiyə Chrome/Edge açılmır.
    # EVOPOS öz proqram pəncərəsində açılır.

    def run_flask():
        app.run(
            host="127.0.0.1",
            port=5000,
            debug=False,
            use_reloader=False
        )


    flask_thread = threading.Thread(
        target=run_flask,
        daemon=True
    )

    flask_thread.start()


    # Serverin işə düşməsi üçün qısa gözləmə
    import time
    time.sleep(1.0)


    webview.create_window(
        "EVOPOS",
        "http://127.0.0.1:5000",
        maximized=True,
        min_size=(1000, 700)
    )


    webview.start()
