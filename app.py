from flask import Flask, render_template, request, redirect, url_for, flash, jsonify # type: ignore
import mysql.connector # type: ignore
import configparser
from datetime import datetime, timedelta
import logging
from decimal import Decimal
from datetime import datetime, timedelta




app = Flask(__name__)
app.secret_key = 'your_secret_key'  # For flash messages


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

@app.route('/place_order/<int:customer_id>', methods=['GET', 'POST'])
def place_order(customer_id):
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        if request.method == 'GET':
            fetch_query = "SELECT Product_ID, Product_Name, Category, Price FROM Product"
            cursor.execute(fetch_query)
            products = cursor.fetchall()

            return render_template('place_order.html', products=products, customer_id=customer_id)

        elif request.method == 'POST':
            product_id = request.form.get('product_id')
            quantity = request.form.get('quantity')

            if not product_id or not quantity:
                flash("Missing required form fields. Please try again.")
                return redirect(url_for('place_order', customer_id=customer_id))

            try:
                quantity = int(quantity)
            except ValueError:
                flash("Quantity must be a valid number. Please try again.")
                return redirect(url_for('place_order', customer_id=customer_id))

            inventory_query = """
                SELECT p.Product_ID, p.Product_Name, i.Quantity, p.Price 
                FROM Product p 
                JOIN Inventory i ON p.Product_ID = i.Product_ID 
                WHERE p.Product_ID = %s
            """
            cursor.execute(inventory_query, (product_id,))
            product = cursor.fetchone()

            if not product:
                flash(f"Product with ID '{product_id}' not found.")
                return redirect(url_for('place_order', customer_id=customer_id))

            available_quantity = product['Quantity']

            if available_quantity < quantity:
                flash(f"Only {available_quantity} units available. Please reduce the quantity.")
                return redirect(url_for('place_order', customer_id=customer_id))

            total_amount = quantity * product['Price']
            return render_template('payment.html', 
                                   customer_id=customer_id, 
                                   product_id=product_id, 
                                   product_name=product['Product_Name'], 
                                   quantity=quantity, 
                                   total_amount=total_amount)

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}")
        return redirect(url_for('place_order', customer_id=customer_id))

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/process_payment', methods=['POST'])
def process_payment():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        customer_id = request.form['customer_id']
        product_id = request.form['product_id']
        quantity = int(request.form['quantity'])
        total_amount = float(request.form['total_amount'])
        payment_method = request.form['payment_method']
        print('Trying')
        sale_query = """
            INSERT INTO Sales (Customer_ID, Product_ID, Quantity, TotalAmount, SaleDate)
            VALUES (%s, %s, %s, %s, CURDATE())
        """
        cursor.execute(sale_query, (customer_id, product_id, quantity, total_amount))
        conn.commit()

        sale_id = cursor.lastrowid

        payment_query = """
            INSERT INTO Payments (Sale_ID, Product_ID, TotalAmount, Payment_Method, PaymentDate)
            VALUES (%s, %s, %s, %s, CURDATE())
        """
        cursor.execute(payment_query, (sale_id, product_id, total_amount, payment_method))
        conn.commit()

        inventory_update_query = """
            UPDATE Inventory
            SET Quantity = Quantity - %s
            WHERE Product_ID = %s
        """
        cursor.execute(inventory_update_query, (quantity, product_id))
        conn.commit()
        print('Trying')


        sales_query = """
            SELECT s.Sale_ID, s.Customer_ID, s.Product_ID, s.Quantity, s.TotalAmount, s.SaleDate,
                   p.Payment_Method, p.PaymentDate, pr.Product_Name
            FROM Sales s
            JOIN Payments p ON s.Sale_ID = p.Sale_ID
            JOIN Product pr ON pr.Product_ID = s.Product_ID
            WHERE s.Sale_ID = %s
        """
        cursor.execute(sales_query, (sale_id,))
        sale_details = cursor.fetchone()

        flash("Payment successfully processed!")
        return render_template('sales.html', sale_details=sale_details)

    except mysql.connector.Error as err:
        flash(f"Database Error: {err}")
        return redirect(url_for('place_order', customer_id=customer_id))

    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/sales', methods=['GET'])
def sales():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        sales_query = """
        SELECT c.Customer_Name, pr.Product_Name, pr.Price, s.Quantity, s.TotalAmount, p.Payment_Method
        FROM Sales s
        JOIN Customers c ON s.Customer_ID = c.Customer_ID
        JOIN Product pr ON s.Product_ID = pr.Product_ID
        JOIN Payments p ON s.Sale_ID = p.Sale_ID
        """
        cursor.execute(sales_query)
        sales = cursor.fetchall()
        return jsonify(sales)
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
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
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT DATE_FORMAT(SaleDate, '%Y-%m') AS month, SUM(TotalAmount) AS total_sales
            FROM Sales
            WHERE SaleDate >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
            GROUP BY DATE_FORMAT(SaleDate, '%Y-%m')
            ORDER BY month ASC
        """
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Create a dictionary with all months in the last year
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        all_months = {(start_date + timedelta(days=30*i)).strftime('%Y-%m'): 0 for i in range(12)}
        
        # Fill in the actual sales data
        for row in results:
            all_months[row['month']] = float(row['total_sales'])
        
        # Convert to the required format
        sales_data = {"sales": all_months}
        
        return jsonify(sales_data)
    except mysql.connector.Error as err:
        app.logger.error(f"Database error: {err}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        app.logger.error(f"Error fetching sales trend: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
            
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

@app.route('/inventory')
def inventory():
    return render_template('inventory.html')
# Route to view vendor orders
# @app.route('/view_vendor_orders', methods=['POST'])
# def view_vendor_orders():
#     conn = None
#     try:
#         conn = mysql.connector.connect(**db_config)
#         cursor = conn.cursor(dictionary=True)

#         # Query to get all records from the VendorOrders table
#         cursor.execute("SELECT * FROM VendorOrders")
#         vendor_orders = cursor.fetchall()

#         # Render the vendor orders
#         return render_template('vendor_orders_details.html', vendor_orders=vendor_orders)

#     except mysql.connector.Error as err:
#         return f"Database Error: {err}"

#     finally:
#         if conn is not None and conn.is_connected():
#             cursor.close()
#             conn.close()

@app.route('/show_inventory', methods=['POST'])
def show_inventory():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Query to get all records from the Inventory table
        cursor.execute("""
            SELECT Product.Product_Name, Inventory.Quantity, Inventory.Threshold
            FROM Product
            JOIN Inventory ON Product.Product_ID = Inventory.Product_ID;
        """)
        inventory_records = cursor.fetchall()

        # Render the inventory details
        return render_template('inventory_details.html', inventory=inventory_records)
    
    except mysql.connector.Error as err:
        return f"Database Error: {err}"
    
    finally:
        if conn is not None and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/vendor_sales', methods=['GET'])
def vendor_sales():
    try:
        # Connect to your database
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor()

        # Your SQL query
        query = """
        SELECT 
            EXTRACT(MONTH FROM Sale_Date) AS Month,
            EXTRACT(YEAR FROM Sale_Date) AS Year,
            Vendor_ID,
            SUM(Price * Quantity) AS Total_Sales
        FROM Sales
        JOIN Products ON Sales.Product_ID = Products.Product_ID
        GROUP BY EXTRACT(MONTH FROM Sale_Date), EXTRACT(YEAR FROM Sale_Date), Vendor_ID
        ORDER BY Year, Month, Vendor_ID;
        """

        # Execute the query
        cur.execute(query)
        rows = cur.fetchall()
        print('Query execution', rows)

        # Format the result into a dictionary
        sales_data = {}
        for row in rows:
            year = int(row[1])
            month = int(row[0])
            vendor_id = row[2]
            total_sales = float(row[3])

            if vendor_id not in sales_data:
                sales_data[vendor_id] = {'months': [], 'sales': []}
            
            sales_data[vendor_id]['months'].append(f'{month}-{year}')
            sales_data[vendor_id]['sales'].append(total_sales)

        # Close the database connection
        cur.close()
        conn.close()

        return jsonify(sales_data)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

@app.route('/view_vendor_orders', methods=['POST'])
def view_vendor_orders():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT vo.*, v.Vendor_Name, p.Product_Name
        FROM VendorOrders vo
        JOIN Vendor v ON vo.Vendor_ID = v.Vendor_ID
        JOIN Product p ON vo.Product_ID = p.Product_ID
        WHERE vo.Delivery_Status = 'Pending'
        """
        cursor.execute(query)
        vendor_orders = cursor.fetchall()
        
        return render_template('vendor_orders.html', vendor_orders=vendor_orders)
    except mysql.connector.Error as err:
        flash(f"Database Error: {err}")
        return redirect(url_for('inventory'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/update_delivery_status', methods=['POST'])
def update_delivery_status():
    vendor_order_id = request.form['vendor_order_id']
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        update_query = """
        UPDATE VendorOrders
        SET Delivery_Status = 'Delivered', DeliveryDate = CURDATE()
        WHERE VendorOrder_ID = %s AND Delivery_Status = 'Pending'
        """
        cursor.execute(update_query, (vendor_order_id,))
        conn.commit()
        
        if cursor.rowcount > 0:
            flash("Delivery status updated successfully!")
        else:
            flash("No pending order found with the given ID.")
        
        return redirect(url_for('inventory'))
    except mysql.connector.Error as err:
        flash(f"Database Error: {err}")
        return redirect(url_for('inventory'))
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()



# # Route to update the delivery status of a vendor order
# @app.route('/update_delivery_status', methods=['POST'])
# def update_delivery_status():
#     vendor_order_id = request.form['vendor_order_id']
#     conn = None
#     try:
#         conn = mysql.connector.connect(**db_config)
#         cursor = conn.cursor(dictionary=True)

#         # Check the current delivery status of the order
#         cursor.execute("SELECT Delivery_Status FROM VendorOrders WHERE VendorOrder_ID = %s", (vendor_order_id,))
#         order = cursor.fetchone()

#         if order:
#             if order['Delivery_Status'] == 'Ordered':
#                 # Update the delivery status to "Delivered" and set the delivery date to today's date
#                 update_query = """
#                     UPDATE VendorOrders
#                     SET Delivery_Status = 'Delivered', DeliveryDate = NOW()
#                     WHERE VendorOrder_ID = %s
#                 """
#                 cursor.execute(update_query, (vendor_order_id,))
#                 conn.commit()

#                 return f"Order {vendor_order_id} status updated to 'Delivered'."
#             else:
#                 return f"Order {vendor_order_id} is already {order['Delivery_Status']}."
#         else:
#             return f"Vendor Order ID {vendor_order_id} not found."

#     except mysql.connector.Error as err:
#         return f"Database Error: {err}"

#     finally:
#         if conn is not None and conn.is_connected():
#             cursor.close()
#             conn.close()

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
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT EXTRACT(YEAR FROM SaleDate) AS Year, EXTRACT(MONTH FROM SaleDate) AS Month,
            SUM(Sales.TotalAmount) - SUM(VendorProducts.Price * Sales.Quantity) AS Profit
            FROM Sales
            JOIN Product ON Sales.Product_ID = Product.Product_ID
            JOIN VendorProducts ON Product.Product_ID = VendorProducts.Product_ID
            GROUP BY Year, Month
            ORDER BY Year, Month;
        """)
        query_result = cursor.fetchall()
        monthly_profits = [
            {
                'month': f"{['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][int(row['Month']) - 1]} {int(row['Year'])}",
                'profit': float(row['Profit'])
            }
            for row in query_result
        ]
        return jsonify({'monthly_profits': monthly_profits})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/analytics/top_sold_products')
def top_sold_products():
    conn = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT Product.Product_Name, SUM(Sales.Quantity) AS Total_Quantity
            FROM Sales
            JOIN Product ON Sales.Product_ID = Product.Product_ID
            GROUP BY Product.Product_Name
            ORDER BY Total_Quantity DESC
            LIMIT 5;
        """)
        top_products = cursor.fetchall()
        for product in top_products:
            product['Total_Quantity'] = int(product['Total_Quantity'])
        return jsonify({'top_sold_products': top_products})
    except mysql.connector.Error as err:
        return jsonify({'error': str(err)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()

# Error handler for 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404
if __name__ == '__main__':
    app.run(debug=True)