from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necessary for flash messages; set to a secure random key in production

# Database connection function
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            database='ecomDB',
            user='root',
            password=''
        )
        if conn.is_connected():
            print("Database connected successfully.")
        return conn
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

# Route to check if the database connection works
@app.route('/check_connection', methods=['GET'])
def check_connection():
    conn = get_db_connection()
    if conn:
        conn.close()  # Close connection after checking
        return jsonify({"message": "Connection successful"})
    else:
        return jsonify({"message": "Connection failed"}), 500

# Login required decorator
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash("You must be logged in to access this page", category="danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__  # Ensure the original function name is preserved
    return wrapper

def get_user_status(user):
    if not user:
        return None
    user_id = user.get('id')  # Ensure the user object has an 'id'
    
    conn = get_db_connection()
    if conn is None:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT status FROM sellers WHERE user_id = %s"
        cursor.execute(query, (user_id,))
        result = cursor.fetchone()
        return result['status'] if result else None
    except Error as e:
        print(f"Error fetching user status: {e}")
        return None
    finally:
        if conn:
            conn.close()

@app.route('/')
def home():
    return render_template('home.html')


# Update login route to check seller status
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            flash("Database connection error")
            return redirect(url_for('login'))
        
        try:
            email = request.form.get('email')
            password = request.form.get('password')

            # Validate required fields
            if not email or not password:
                flash("Both email and password are required")
                return redirect(url_for('login'))

            cursor = conn.cursor()

            # Fetch the user data
            query = "SELECT id, password, role FROM users WHERE email = %s"
            cursor.execute(query, (email,))
            user = cursor.fetchone()

            if user:
                # Check if the password matches
                if user[1] == password:  # For security, use hashed passwords in real apps
                    session['user_id'] = user[0]  # Store user ID in session
                    session['role'] = user[2]  # Store role in session

                    # Check if the user is an approved seller
                    cursor.execute("SELECT status FROM sellers WHERE user_id = %s", (user[0],))
                    seller_status = cursor.fetchone()
                    if seller_status and seller_status[0] == 'approved':
                        session['is_seller'] = True
                    else:
                        session['is_seller'] = False

                    # Redirect based on user role
                    if session['role'] == 'admin':
                        return redirect(url_for('admin_page'))
                    elif session['role'] == 'superadmin':
                        return redirect(url_for('super_page'))
                    elif session['role'] == 'user':
                        return redirect(url_for('user_page'))
                    else:
                        flash("Unknown role encountered", category="danger")
                        return redirect(url_for('login'))
                else:
                    flash("Invalid email or password", category="danger")
                    return redirect(url_for('login'))
            else:
                flash("Invalid email or password", category="danger")
                return redirect(url_for('login'))

        except Error as e:
            print(f"Login error: {e}")
            flash("An internal database error occurred", category="danger")
            return redirect(url_for('login'))
        finally:
            if conn:
                conn.close()  # Ensure connection is closed

    return render_template('login.html')



@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        conn = get_db_connection()
        if conn is None:
            flash("Failed to connect to the database")
            return redirect(url_for('signup'))

        try:
            email = request.form.get('email')
            password = request.form.get('password')
            role = 'user'  # Default role is 'user'

            # Validate required fields
            if not email or not password:
                flash("Email and password are required")
                return redirect(url_for('signup'))

            cursor = conn.cursor()

            # Insert the user into the 'users' table
            query = "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)"
            cursor.execute(query, (email, password, role))  # Store plain text password
            conn.commit()
            flash("User registered successfully!")  # Success message
            return redirect(url_for('login'))  # Redirect to login after successful signup

        except Error as e:
            print(f"Error while inserting user data: {e}")
            flash("Failed to register user", category="danger")
            return redirect(url_for('signup'))
        finally:
            if conn:
                conn.close()  # Ensure connection is closed

    return render_template('signup.html')

from flask import session  # Ensure you have session imported

from flask import session  # Ensure you have session imported

@app.route('/seller_registration', methods=['GET', 'POST'])
def seller_registration():
    # Ensure the user is logged in
    if 'user_id' not in session:
        flash("You need to be logged in to apply as a seller.")
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    # Establish a database connection
    conn = get_db_connection()
    if conn is None:
        flash("Failed to connect to the database", "danger")
        return redirect(url_for('home'))

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if the user is already registered as a seller
        cursor.execute("SELECT * FROM sellers WHERE user_id = %s", (user_id,))
        existing_seller = cursor.fetchone()

        if existing_seller:
            flash("You are already registered as a seller.")
            return redirect(url_for('user_page'))

        if request.method == 'POST':
            first_name = request.form['firstName']
            last_name = request.form['lastName']
            email = request.form['email']
            phone_number = request.form['phoneNumber']
            address = request.form['address']
            postal_code = request.form['postalCode']
            business_name = request.form['businessName']
            description = request.form['description']


            # Insert the new seller record
            cursor.execute("""
                INSERT INTO sellers (user_id, first_name, last_name, email, phone_number, address, postal_code, business_name, description, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
            """, (user_id, first_name, last_name, email, phone_number, address, postal_code, business_name, description))
            
            # Update the `is_seller` flag in the `users` table
            cursor.execute("UPDATE users SET is_seller = TRUE WHERE id = %s", (user_id,))
            
            conn.commit()
            
            flash("Your application as a seller has been submitted successfully.")
            return redirect(url_for('user_page'))
        
    except Error as e:
        conn.rollback()
        flash("There was an error processing your application. Please try again.")
        print("Error:", e)
    
    finally:
        cursor.close()
        conn.close()

    return render_template('seller_registration.html')


@app.route('/notifications')
@login_required
def notifications():
    user_id = session.get('user_id')
    conn = get_db_connection()
    if conn is None:
        flash("Database connection error", category="danger")
        return redirect(url_for('home'))

    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC"
        cursor.execute(query, (user_id,))
        notifications = cursor.fetchall()
        
        # Mark all notifications as read
        update_query = "UPDATE notifications SET is_read = TRUE WHERE user_id = %s"
        cursor.execute(update_query, (user_id,))
        conn.commit()

        return render_template('notifications.html', notifications=notifications)

    except Error as e:
        print(f"Error fetching notifications: {e}")
        flash("Failed to fetch notifications.", category="danger")
        return redirect(url_for('home'))
    
    finally:
        if conn:
            conn.close()


def create_notification(user_id, message):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database for notification.")
        return False

    try:
        cursor = conn.cursor()
        query = "INSERT INTO notifications (user_id, message) VALUES (%s, %s)"
        cursor.execute(query, (user_id, message))
        conn.commit()
        return True  # Notification created successfully
    except Error as e:
        print(f"Error creating notification: {e}")
        return False
    finally:
        if conn:
            conn.close()

@app.route('/admin_page', methods=['GET'])
@login_required
def admin_page():
    if session.get('role') != 'admin':
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))
    return render_template('admin_page.html')

@app.route('/view-user', methods=['GET'])
@login_required
def view_user():
    if session.get('role') != 'admin':  # Restrict access to admin
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))
    # Fetch users from the database or render the user viewing template
    return render_template('view_user.html')  # Replace with your template

@app.route('/view-seller', methods=['GET'])
@login_required
def view_seller():
    if session.get('role') != 'admin':  # Restrict access to admin
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))
    # Fetch sellers from the database or render the seller viewing template
    return render_template('view_seller.html')  # Replace with your template

@app.route('/admin_logout')
def admin_logout():
    session.clear()  # Clear the session on logout
    flash("Logged out successfully!", category="success")  # Flash message on successful logout
    return redirect(url_for('login'))  # Redirect to the login page after logout


@app.route('/super_page', methods=['GET'])
@login_required
def super_page():
    if session.get('role') != 'superadmin':
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))
    return render_template('super_page.html')

@app.route('/user_page', methods=['GET'])
@login_required
def user_page():
    if session.get('role') != 'user':
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))
    
    # Get is_seller status from the session (default to False if not set)
    is_seller = session.get('is_seller', False)
    
    return render_template('user_page.html', is_seller=is_seller)


@app.route('/logout')
def logout():
    session.clear()  # Clear the session on logout
    flash("Logged out successfully!", category="success")
    return redirect(url_for('login'))

@app.route('/viewseller_application')
def viewseller_application():
    conn = get_db_connection()
    if conn is None:
        flash("Failed to connect to the database", "danger")
        return redirect(url_for('home'))

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sellers")
        sellers = cursor.fetchall()
        return render_template('viewseller_application.html', sellers=sellers)
    finally:
        if conn:
            conn.close()


@app.route('/approve_seller/<int:id>', methods=['POST'])
def approve_seller(id):
    if session.get('role') != 'admin':
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))

    conn = get_db_connection()
    if conn is None:
        flash("Failed to connect to the database", "danger")
        return redirect(url_for('viewseller_application'))

    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE sellers SET status = 'approved' WHERE id = %s", (id,))
        conn.commit()
        # Create a notification for the user (optional)
        flash("Seller approved successfully!", category="success")
        return redirect(url_for('viewseller_application'))
    except Exception as e:
        flash(f"Error: {e}", category="danger")
        return redirect(url_for('viewseller_application'))
    finally:
        if conn:
            conn.close()



@app.route('/decline_seller/<int:id>', methods=['POST'])
def decline_seller(id):
    if session.get('role') != 'admin':
        flash("Access restricted", category="danger")
        return redirect(url_for('home'))

    conn = get_db_connection()
    if conn is None:
        flash("Failed to connect to the database", "danger")
        return redirect(url_for('viewseller_application'))

    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE sellers SET status = 'declined' WHERE id = %s", (id,))
        conn.commit()
        flash("Seller declined successfully!", category="danger")
        return redirect(url_for('viewseller_application'))
    except Exception as e:
        flash(f"Error: {e}", category="danger")
        return redirect(url_for('viewseller_application'))
    finally:
        if conn:
            conn.close()

# Helper Function for Creating Notifications
def create_notification(user_id, message):
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to the database for notification.")
        return False

    try:
        cursor = conn.cursor()
        query = "INSERT INTO notifications (user_id, message) VALUES (%s, %s)"
        cursor.execute(query, (user_id, message))
        conn.commit()
        return True
    except Error as e:
        print(f"Error creating notification: {e}")
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    app.run(debug=True)  # Optional: Set debug=True for helpful error messages