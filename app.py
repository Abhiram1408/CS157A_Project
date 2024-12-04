from flask import Flask, request, render_template, redirect, url_for
import mysql.connector
import configparser

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

@app.route('/place_order/<int:customer_id>', )
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

@app.route('/submit_order', methods=['POST', 'GET'])
def submit_order():
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        product_name = request.form['product_name']
        quantity = int(request.form['quantity'])
    elif request.method == 'GET':
        customer_id = request.args.get('customer_id')
        product_name = request.args.get('product_name')
        quantity = int(request.args.get('quantity'))
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        fetch_product_query = "SELECT Product_ID,Price FROM Product WHERE Product_Name = %s"
        cursor.execute(fetch_product_query, (product_name,))
        product = cursor.fetchone()

        if product:
            product_id, price = product

            fetch_inventory_query = "SELECT Quantity FROM Inventory WHERE Product_ID = %s"
            cursor.execute(fetch_inventory_query, (product_id,))
            inventory = cursor.fetchone()

            if inventory:
                available_quantity = inventory[0]
                if available_quantity < quantity:
                    # If insufficient inventory, display options to the user
                    return render_template(
                        'insufficient_inventory.html',
                        product_name=product_name,
                        available_quantity=available_quantity,
                        requested_quantity=quantity,
                        customer_id=customer_id,
                        product_id=product_id
                    )
                
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


@app.route('/update_order', methods=['POST'])
def update_order():
    action = request.form['action']
    product_name = request.form['product_name']
    customer_id = request.form['customer_id']

    if action == 'cancel_order':
        return "Thank You!"

    elif action == 'new_order':
        return redirect(f'/place_order/{customer_id}')

    elif action == 'change_quantity':
        customer_id = request.form['customer_id']
        product_id = request.form['product_id']
        new_quantity = int(request.form['new_quantity'])
        print("Request Method:", request.method)
        print("Customer ID:", request.args.get('customer_id'))
        print("Product Name:", request.args.get('product_name'))
        print("Quantity:", request.args.get('quantity'))

        # Redirect to the submit_order method with new quantity
        return redirect(url_for('submit_order', customer_id=customer_id, product_name=product_name, quantity=new_quantity))

# Route to display analytics page
@app.route('/analytics')
def analytics():
    return render_template('analytics.html')



# Route to fetch total sales per vendor
@app.route('/analytics/vendor_sales')
def vendor_sales():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for total sales by vendor
        cursor.execute("""
            SELECT v.Vendor_Name, SUM(s.TotalAmount) AS total_sales
            FROM Vendor v
            JOIN Product p ON v.Vendor_ID = p.Vendor_ID
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY v.Vendor_Name;
        """)

        vendor_sales = cursor.fetchall()
        return jsonify({'vendor_sales': vendor_sales})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()


# Route to fetch most profitable vendor
@app.route('/analytics/most_profitable_vendor')
def most_profitable_vendor():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for most profitable vendor
        cursor.execute("""
            SELECT v.Vendor_Name, SUM(s.TotalAmount) AS total_sales
            FROM Vendor v
            JOIN Product p ON v.Vendor_ID = p.Vendor_ID
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY v.Vendor_Name
            ORDER BY total_sales DESC
            LIMIT 1;
        """)

        most_profitable = cursor.fetchone()
        return jsonify({'most_profitable_vendor': most_profitable})

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()


# Route to fetch least profitable vendor
@app.route('/analytics/least_profitable_vendor')
def least_profitable_vendor():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for least profitable vendor
        cursor.execute("""
            SELECT v.Vendor_Name, SUM(s.TotalAmount) AS total_sales
            FROM Vendor v
            JOIN Product p ON v.Vendor_ID = p.Vendor_ID
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY v.Vendor_Name
            ORDER BY total_sales ASC
            LIMIT 1;
        """)

        least_profitable = cursor.fetchone()
        return jsonify({'least_profitable_vendor': least_profitable})

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Year-over-Year Sales Change
@app.route('/analytics/yoy_sales_change')
def yoy_sales_change():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for Year-over-Year Sales Change
        cursor.execute("""
            SELECT YEAR(SaleDate) AS year, SUM(TotalAmount) AS total_sales
            FROM Sales
            GROUP BY year
            HAVING COUNT(DISTINCT YEAR(SaleDate)) > 1
        """)

        yoy_change = cursor.fetchall()
        return render_template('analytics.html', yoy_change=yoy_change)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Top 5 Products by Sales
@app.route('/analytics/top_5_products_by_sales')
def top_5_products_by_sales():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for the top 5 products by sales
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.TotalAmount) AS total_sales
            FROM Product p
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY p.Product_Name
            ORDER BY total_sales DESC
            LIMIT 5;
        """)

        top_5_products = cursor.fetchall()
        return render_template('analytics.html', top_5_products=top_5_products)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Top Selling Product by Quantity
@app.route('/analytics/top_selling_product_by_quantity')
def top_selling_product_by_quantity():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for the top-selling product by quantity
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.Quantity) AS total_quantity
            FROM Product p
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY p.Product_Name
            ORDER BY total_quantity DESC
            LIMIT 1;
        """)

        top_selling_product = cursor.fetchone()
        return render_template('analytics.html', top_selling_product=top_selling_product)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Sales by Customer Type
@app.route('/analytics/sales_by_customer_type')
def sales_by_customer_type():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for sales by customer type (email domain in this case)
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN c.Email LIKE '%@gmail.com' THEN 'Gmail'
                    WHEN c.Email LIKE '%@yahoo.com' THEN 'Yahoo'
                    ELSE 'Other'
                END AS customer_type,
                SUM(s.TotalAmount) AS total_sales
            FROM Customers c
            JOIN Sales s ON c.Customer_ID = s.Customer_ID
            GROUP BY customer_type;
        """)

        customer_sales = cursor.fetchall()
        return render_template('analytics.html', customer_sales=customer_sales)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Products Below Inventory Threshold
@app.route('/analytics/products_below_inventory_threshold')
def products_below_inventory_threshold():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query for products below the inventory threshold
        cursor.execute("""
            SELECT p.Product_Name, i.Quantity, i.Threshold
            FROM Product p
            JOIN Inventory i ON p.Product_ID = i.Product_ID
            WHERE i.Quantity <= i.Threshold;
        """)

        products_below_threshold = cursor.fetchall()
        return render_template('analytics.html', products_below_threshold=products_below_threshold)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Route to fetch Products Not Sold in the Last 3 Months
@app.route('/analytics/products_not_sold_3_months')
def products_not_sold_3_months():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Calculate the date 3 months ago from today
        three_months_ago = datetime.now() - timedelta(days=90)

        # Query to fetch products not sold in the last 3 months
        cursor.execute("""
            SELECT p.Product_Name, p.Price * 0.9 AS Discounted_Price
            FROM Product p
            LEFT JOIN Sales s ON p.Product_ID = s.Product_ID AND s.SaleDate > %s
            WHERE s.Sale_ID IS NULL;
        """, (three_months_ago,))

        products = cursor.fetchall()
        return render_template('analytics.html', products_not_sold=products)

    except mysql.connector.Error as err:
        logging.error(f"Database Error: {err}")
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
