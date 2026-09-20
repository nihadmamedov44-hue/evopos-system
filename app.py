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
import sqlite3
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

app.secret_key = "evopos-secret-key-2026"


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


        # Hesabat API

        if request.path == "/api/reports":

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

    session.permanent = True


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
            created_at
        )

        VALUES (?, ?, ?, ?)
        """,
        (
            table_number,
            total,
            "Yeni",
            created_at
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


    if order["status"] == "Tamamlandı":

        connection.close()

        return jsonify({
            "success": False,
            "message":
                "Tamamlanmış sifariş dəyişdirilə bilməz."
        }), 400


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
                "Tamamlanmış sifariş silinə bilməz."
        }), 400


    cursor.execute(
        """
        DELETE FROM order_items
        WHERE order_id = ?
        """,
        (order_id,)
    )


    cursor.execute(
        """
        DELETE FROM orders
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
            paid_at

        FROM orders

        ORDER BY id DESC
        """
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
                order["paid_at"]

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

            AND status != 'Tamamlandı'

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


    orders = cursor.execute(
        """
        SELECT *

        FROM orders

        WHERE status != 'Tamamlandı'

        ORDER BY id ASC
        """
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

        SET status = ?

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
# REPORTS API
# =========================================================

@app.route("/api/reports")
def reports_api():

    connection = get_db()

    cursor = connection.cursor()


    try:

        # =================================================
        # ÜMUMİ SATIŞ
        # =================================================

        total_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Tamamlandı'
                            THEN total
                            ELSE 0
                        END
                    ),
                    0
                ) AS total_sales

            FROM orders
            """
        ).fetchone()


        total_sales = float(
            total_sales_row["total_sales"] or 0
        )


        # =================================================
        # BU GÜNÜN SATIŞI
        # =================================================

        today_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN status = 'Tamamlandı'
                            THEN total
                            ELSE 0
                        END
                    ),
                    0
                ) AS today_sales

            FROM orders

            WHERE date(created_at) = date('now', 'localtime')
            """
        ).fetchone()


        today_sales = float(
            today_sales_row["today_sales"] or 0
        )


        # =================================================
        # ÜMUMİ SİFARİŞ
        # =================================================

        total_orders_row = cursor.execute(
            """
            SELECT COUNT(*) AS total_orders
            FROM orders
            """
        ).fetchone()


        total_orders = int(
            total_orders_row["total_orders"] or 0
        )


        # =================================================
        # AKTİV SİFARİŞ
        # =================================================

        active_orders_row = cursor.execute(
            """
            SELECT COUNT(*) AS active_orders

            FROM orders

            WHERE status != 'Tamamlandı'
            """
        ).fetchone()


        active_orders = int(
            active_orders_row["active_orders"] or 0
        )


        # =================================================
        # TAMAMLANAN SİFARİŞ
        # =================================================

        completed_orders_row = cursor.execute(
            """
            SELECT COUNT(*) AS completed_orders

            FROM orders

            WHERE status = 'Tamamlandı'
            """
        ).fetchone()


        completed_orders = int(
            completed_orders_row["completed_orders"] or 0
        )


        # =================================================
        # BU GÜN TAMAMLANAN
        # =================================================

        today_completed_row = cursor.execute(
            """
            SELECT COUNT(*) AS today_completed

            FROM orders

            WHERE status = 'Tamamlandı'

            AND date(created_at)
                = date('now', 'localtime')
            """
        ).fetchone()


        today_completed = int(
            today_completed_row["today_completed"] or 0
        )


        # =================================================
        # NAĞD SATIŞ
        # =================================================

        cash_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(total),
                    0
                ) AS cash_sales

            FROM orders

            WHERE status = 'Tamamlandı'

            AND payment_method = 'Nağd'
            """
        ).fetchone()


        cash_sales = float(
            cash_sales_row["cash_sales"] or 0
        )


        # =================================================
        # KART SATIŞ
        # =================================================

        card_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(total),
                    0
                ) AS card_sales

            FROM orders

            WHERE status = 'Tamamlandı'

            AND payment_method = 'Kart'
            """
        ).fetchone()


        card_sales = float(
            card_sales_row["card_sales"] or 0
        )


        # =================================================
        # BU GÜN NAĞD
        # =================================================

        today_cash_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(total),
                    0
                ) AS today_cash_sales

            FROM orders

            WHERE status = 'Tamamlandı'

            AND payment_method = 'Nağd'

            AND date(created_at)
                = date('now', 'localtime')
            """
        ).fetchone()


        today_cash_sales = float(
            today_cash_sales_row["today_cash_sales"] or 0
        )


        # =================================================
        # BU GÜN KART
        # =================================================

        today_card_sales_row = cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(total),
                    0
                ) AS today_card_sales

            FROM orders

            WHERE status = 'Tamamlandı'

            AND payment_method = 'Kart'

            AND date(created_at)
                = date('now', 'localtime')
            """
        ).fetchone()


        today_card_sales = float(
            today_card_sales_row["today_card_sales"] or 0
        )


        # =================================================
        # SON ÖDƏNİŞLƏR
        # =================================================

        recent_orders = cursor.execute(
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

                paid_at

            FROM orders

            ORDER BY id DESC

            LIMIT 10
            """
        ).fetchall()


        recent = [

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
                    order["paid_at"]

            }

            for order in recent_orders

        ]


        connection.close()


        return jsonify({

            "success": True,

            "total_sales":
                total_sales,

            "today_sales":
                today_sales,

            "total_orders":
                total_orders,

            "active_orders":
                active_orders,

            "completed_orders":
                completed_orders,

            "today_completed":
                today_completed,

            "cash_sales":
                cash_sales,

            "card_sales":
                card_sales,

            "today_cash_sales":
                today_cash_sales,

            "today_card_sales":
                today_card_sales,

            "recent":
                recent,

            # reports.html müxtəlif adlardan
            # istifadə edərsə uyğunluq üçün

            "orders":
                recent,

            "recent_orders":
                recent

        })


    except Exception as error:

        connection.close()

        print(
            "REPORTS API ERROR:",
            repr(error)
        )


        return jsonify({

            "success": False,

            "message":
                "Hesabat məlumatları alınmadı.",

            "error":
                str(error)

        }), 500


# =========================================================
# DATABASE INIT
# =========================================================

init_database()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    def open_evopos():

        url = "http://127.0.0.1:5000"

        # Adi sayt kimi aç
        webbrowser.open(url)

        # Chrome proqram pəncərəsi
        chrome_paths = [
            shutil.which("chrome"),
            os.path.expandvars(
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
            ),
            os.path.expandvars(
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe"
            )
        ]

        chrome = None

        for path in chrome_paths:

            if path and os.path.exists(path):
                chrome = path
                break

        if chrome:

            subprocess.Popen([
                chrome,
                "--app=" + url,
                "--start-maximized"
            ])

    threading.Timer(
        2.0,
        open_evopos
    ).start()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )