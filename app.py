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



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
