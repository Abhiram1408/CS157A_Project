from flask import Flask, request, render_template, jsonify, redirect, url_for
import mysql.connector
import configparser
from datetime import datetime, timedelta
from decimal import Decimal

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

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')

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

@app.route('/show_inventory', methods=['POST'])
def show_inventory():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query to get all records from the Inventory table
        cursor.execute("SELECT * FROM Inventory")
        inventory_records = cursor.fetchall()

        # Render the inventory details
        return render_template('inventory_details.html', inventory=inventory_records)
    
    except mysql.connector.Error as err:
        return f"Database Error: {err}"
    
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()


# Route to view vendor orders
@app.route('/view_vendor_orders', methods=['POST'])
def view_vendor_orders():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query to get all records from the VendorOrders table
        cursor.execute("SELECT * FROM VendorOrders")
        vendor_orders = cursor.fetchall()

        # Render the vendor orders
        return render_template('vendor_orders_details.html', vendor_orders=vendor_orders)

    except mysql.connector.Error as err:
        return f"Database Error: {err}"

    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()


# Route to update the delivery status of a vendor order
@app.route('/update_delivery_status', methods=['POST'])
def update_delivery_status():
    vendor_order_id = request.form['vendor_order_id']
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Check the current delivery status of the order
        cursor.execute("SELECT Delivery_Status FROM VendorOrders WHERE VendorOrder_ID = %s", (vendor_order_id,))
        order = cursor.fetchone()

        if order:
            if order['Delivery_Status'] == 'Ordered':
                # Update the delivery status to "Delivered" and set the delivery date to today's date
                update_query = """
                    UPDATE VendorOrders
                    SET Delivery_Status = 'Delivered', DeliveryDate = NOW()
                    WHERE VendorOrder_ID = %s
                """
                cursor.execute(update_query, (vendor_order_id,))
                conn.commit()

                return f"Order {vendor_order_id} status updated to 'Delivered'."
            else:
                return f"Order {vendor_order_id} is already {order['Delivery_Status']}."
        else:
            return f"Vendor Order ID {vendor_order_id} not found."

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
        # Query to fetch the best-selling product based on total quantity sold
        cursor.execute("""
            SELECT p.Product_Name, SUM(s.Quantity) AS total_quantity
            FROM Product p
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY p.Product_Name
            ORDER BY total_quantity DESC
            LIMIT 1;
        """)

        # Fetch the result
        best_selling_product = cursor.fetchone()

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
    
@app.route('/analytics/most_profitable_vendor')
def most_profitable_vendor():
    conn = None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected to the database to find mpv")

        # Query to fetch the most profitable vendor
        cursor.execute("""
            SELECT v.Vendor_Name, 
                   SUM(s.Quantity * p.Price) AS total_profit
            FROM Vendor v
            JOIN Product p ON v.Vendor_ID = p.Vendor_ID
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY v.Vendor_Name
            ORDER BY total_profit DESC
            LIMIT 1;
        """)

        # Fetch the result
        most_profitable_vendor = cursor.fetchone()
        print("Query Result:", most_profitable_vendor)
        most_profitable_vendor['total_profit'] = float(most_profitable_vendor['total_profit'])

        if most_profitable_vendor:
            return jsonify({'most_profitable_vendor': most_profitable_vendor})
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

@app.route('/analytics/least_profitable_vendor')
def least_profitable_vendor():
    conn = None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query to fetch the least profitable vendor
        cursor.execute("""
            SELECT v.Vendor_Name, 
                   SUM(s.Quantity * p.Price) AS total_profit
            FROM Vendor v
            JOIN Product p ON v.Vendor_ID = p.Vendor_ID
            JOIN Sales s ON p.Product_ID = s.Product_ID
            GROUP BY v.Vendor_Name
            ORDER BY total_profit ASC
            LIMIT 1;
        """)

        # Fetch the result
        least_profitable_vendor = cursor.fetchone()
        least_profitable_vendor['total_profit'] = float(least_profitable_vendor['total_profit'])

        if least_profitable_vendor:
            return jsonify({'least_profitable_vendor': least_profitable_vendor})
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

@app.route('/analytics/sale_items')
def sale_items():
    conn = None
    try:
        # Establish a connection to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Get the current date
        current_date = datetime.now()

        # Calculate the date 3 months ago
        three_months_ago = current_date - timedelta(days=90)

        # Query to fetch products not sold in the last 3 months
        cursor.execute("""
            SELECT p.Product_ID, p.Product_Name, p.Price,
                   ROUND(p.Price * 0.80, 2) AS Discounted_Price
            FROM Product p
            LEFT JOIN Sales s ON p.Product_ID = s.Product_ID
            WHERE (s.SaleDate IS NULL OR s.SaleDate < %s)
        """, (three_months_ago,))

        sale_items = cursor.fetchall()
        print("Query Result:", sale_items)

        for item in sale_items:
            item['Price'] = float(item['Price'])
            item['Discounted_Price'] = float(item['Discounted_Price'])

        if sale_items:
            return jsonify({'sale_items': sale_items})
        else:
            return jsonify({'error': 'No sale items found'}), 404

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        # Ensure that the database connection is closed
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/payment_methods')
def payment_methods():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected to the database to find payment methods")

        # Query to fetch payment method counts
        cursor.execute("""
            SELECT Payments.Payment_Method,COUNT(Payments.T_ID) AS Payment_Count
            FROM Payments
            GROUP BY Payments.Payment_Method
            ORDER BY Payment_Count DESC;

        """)

        payment_data = cursor.fetchall()
        print("Query Result:", payment_data)


        if payment_data:
            return jsonify({'payment_methods': payment_data})
        else:
            return jsonify({'error': 'No payment data available'}), 404

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/category_sales')
def category_sales():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected to the database to find category wise sales")

        cursor.execute("""
            SELECT Product.Category, SUM(Sales.TotalAmount) AS Total_Sales
            FROM Sales
            JOIN Product ON Sales.Product_ID = Product.Product_ID
            GROUP BY Product.Category
            ORDER BY Total_Sales DESC;
        """)

        category_sales = cursor.fetchall()
        print("Query Result:", category_sales)


        if category_sales:
            return jsonify({'category_sales': category_sales})
        else:
            return jsonify({'error': 'No data available'}), 404

    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500

    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/monthly_profits')
def monthly_profits():
    conn = None
    try:
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected to the database to find monthly profit")

        # Execute the query
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM SaleDate) AS Year,
                   EXTRACT(MONTH FROM SaleDate) AS Month,
                   SUM(Sales.TotalAmount) - SUM(VendorProducts.Price * Sales.Quantity) AS Profit
            FROM Sales
            JOIN Product ON Sales.Product_ID = Product.Product_ID
            JOIN VendorProducts ON Product.Product_ID = VendorProducts.Product_ID
            GROUP BY Year, Month
            ORDER BY Year, Month;
        """)

        # Fetch the query results
        query_result = cursor.fetchall()
        print("Query Result:", query_result)

        # Format the results for the frontend
        monthly_profits = [
            {
                'month': f"{['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][row['Month'] - 1]} {int(row['Year'])}",
                'profit': float(row['Profit']) if isinstance(row['Profit'], Decimal) else row['Profit']
            }
            for row in query_result
        ]

        # Return the response in the required format
        if monthly_profits:
            return jsonify({'monthly_profits': monthly_profits})
        else:
            return jsonify({'monthly_profits': []}), 404

    except mysql.connector.Error as err:
        # Handle database connection errors
        print(f"Database error: {err}")
        return jsonify({'error': str(err)}), 500

    finally:
        # Ensure the connection is closed
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/top_sold_products')
def top_sold_products():
    conn = None
    try:
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        print("Connected to the database to find top sold products")

        # Execute the SQL query
        cursor.execute("""
            SELECT 
                Product.Product_Name,
                SUM(Sales.Quantity) AS Total_Quantity
            FROM Sales
            JOIN Product ON Sales.Product_ID = Product.Product_ID
            GROUP BY Product.Product_Name
            ORDER BY Total_Quantity DESC
            LIMIT 5;
        """)

        # Fetch the results
        top_products = cursor.fetchall()
        print("Query Result:", top_products)

        for product in top_products:
            if isinstance(product['Total_Quantity'], Decimal):
                product['Total_Quantity'] = int(product['Total_Quantity'])
            
        # Return the result as JSON
        if top_products:
            return jsonify({'top_sold_products': top_products})
        else:
            return jsonify({'error': 'No data available'}), 404

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return jsonify({'error': str(err)}), 500

    finally:
        # Close the connection
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()



# Error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
if __name__ == '__main__':
    app.run(debug=True)
