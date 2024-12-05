from flask import Flask, request, render_template, jsonify
import mysql.connector
import configparser
from datetime import datetime, timedelta
import logging

app = Flask(__name__)

config = configparser.ConfigParser()
config.read("local.conf")

db_config = {
    "host": config.get("database", "host"),
    "user": config.get("database", "user"),
    "password": config.get("database", "password"),
    "database": config.get("database", "database")
}

@app.route('/')
def main_page():
    return render_template('main.html')

# Route to display the Add Customers form
@app.route('/add_customer_form')
def add_customer_form():
    return render_template('form.html')

@app.route('/')
def home():
    return render_template('form.html')

@app.route('/add_customer', methods=['POST'])
def add_customer():
    # Fetch form data
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    address = request.form['address']

    conn = None
    try:
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        check_query = "SELECT Customer_ID FROM Customers WHERE Customer_Name = %s AND Phone = %s AND Email = %s AND Address = %s"
        cursor.execute(check_query, (name, phone, email, address))
        result = cursor.fetchone()

        if result:
            customer_id = result[0]
            return f"Welcome Back! Please place your order. <br><a href='/place_order/{customer_id}'>Place Your Order</a>"

        else:
            query = "INSERT INTO Customers (Customer_Name, Phone, Email, Address) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (name, phone, email, address))
            conn.commit()

            customer_id = cursor.lastrowid
            return f"Customer details have been added successfully! <br><a href='/place_order/{customer_id}'>Place Your Order</a>"
    except mysql.connector.Error as err:
        return f"Error: {err}"
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/place_order/<int:customer_id>')
def place_order(customer_id):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Fetch products
        fetch_query = "SELECT Product_ID, Product_Name, Category, Price FROM Product"
        cursor.execute(fetch_query)
        products = cursor.fetchall()

        return render_template('place_order.html', customer_id=customer_id, products=products)
    except mysql.connector.Error as err:
        return f"Database Error: {err}"
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/submit_order', methods=['POST'])
def submit_order():
    customer_id = request.form['customer_id']
    product_name = request.form['product_name']
    quantity = int(request.form['quantity'])

    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        fetch_product_query = "SELECT Product_ID,Price FROM Product WHERE Product_Name = %s"
        cursor.execute(fetch_product_query, (product_name,))
        product = cursor.fetchone()

        if product:
            product_id, price = product
            total_amount = quantity * price

            # Insert sale into Sales table
            insert_query = """
                INSERT INTO Sales (Customer_ID, Product_ID, Quantity, TotalAmount, SaleDate)
                VALUES (%s, %s, %s, %s, NOW())
            """
            cursor.execute(insert_query, (customer_id, product_id, quantity, total_amount))
            conn.commit()

        # Fetch the newly inserted sale
        sale_id = cursor.lastrowid
        fetch_query = "SELECT * FROM Sales WHERE Sale_ID = %s"
        cursor.execute(fetch_query, (sale_id,))
        sale = cursor.fetchone()

        return render_template('order_summary.html', sale=sale)
    except mysql.connector.Error as err:
        return f"Database Error: {err}"
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

# Route to display analytics page
@app.route('/analytics')
def analytics():
    return render_template('analytics.html')



# Route to fetch total sales per vendor
@app.route('/analytics/best_selling_product')
def best_selling_product():
    conn = None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print('LASYA')
        # Query to fetch the best-selling product based on total quantity sold
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.Quantity) AS total_quantity
            FROM Product p
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY p.Product_Name
            ORDER BY total_quantity DESC
            LIMIT 1;
        """)
        print('LASYA')

        # Fetch the result
        best_selling_product = cursor.fetchone()
        print('LASYA')

        if best_selling_product:
            return jsonify({'best_selling_product': best_selling_product})
        else:
            return jsonify({'error': 'No sales data available'}), 404

    except mysql.connector.Error as err:
        # Handle MySQL connection or query errors
        return jsonify({'error': str(err)}), 500

    finally:
        # Ensure that the database connection is closed
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/worst_selling_product')
def worst_selling_product():
    conn = None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query to fetch the worst-selling product based on total quantity sold
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.Quantity) AS total_quantity
            FROM Product p
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY p.Product_Name
            ORDER BY total_quantity ASC
            LIMIT 1;
        """)

        # Fetch the result
        worst_selling_product = cursor.fetchone()

        if worst_selling_product:
            return jsonify({'worst_selling_product': worst_selling_product})
        else:
            return jsonify({'error': 'No sales data available'}), 404

    except mysql.connector.Error as err:
        # Handle MySQL connection or query errors
        return jsonify({'error': str(err)}), 500

    finally:
        # Ensure that the database connection is closed
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()


@app.route('/analytics/sales_trend')
def sales_trend():
    try:
        # Sales trend data
        sales_data = {
            "sales": {
                "november_2024": 50000,
                "october_2024": 45000,
                "november_2023": 40000
            }
        }
        return jsonify(sales_data)
    except Exception as e:
        app.logger.error(f"Error fetching sales trend: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


# Error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
if __name__ == '__main__':
    app.run(debug=True)
