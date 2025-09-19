from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.db import get_db_connection
from flask_bcrypt import generate_password_hash, check_password_hash
import re
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, date
import pymysql
import random

# Define flat shipping rate
FLAT_SHIPPING_RATE = 5.00 # Example flat rate

# Define allowed cities
ALLOWED_CITIES = [
    'Ramallah',
    'Nablus',
    'Hebron (Al-Khalil)',
    'Bethlehem (Beit Lahm)',
    'Jericho (Ariha)',
    'Jenin',
    'Tulkarm',
    'Qalqilya',
    'East Jerusalem (Al-Quds)'
]

UPLOAD_FOLDER = 'app/static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def delete_profile_picture(picture_path):
    if picture_path:
        full_path = os.path.join('app/static', picture_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except Exception as e:
                print(f"Error deleting profile picture: {e}")

def save_profile_picture(picture_file, user_id):
    if picture_file and picture_file.filename:
        # Secure the filename
        filename = secure_filename(picture_file.filename)
        # Create a unique filename using user_id and timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f'profile_{user_id}_{timestamp}_{filename}'
        # Save the file
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        picture_file.save(file_path)
        # Return the relative path for database storage (always use forward slashes)
        return os.path.join('uploads', unique_filename).replace('\\', '/').replace('\\', '/').replace('\\', '/').replace('\\', '/').replace('\\', '/').replace('\\', '/')
    return None

main = Blueprint('main', __name__)

# retrieve user addresses
def get_user_addresses(person_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM Address WHERE person_id = %s', (person_id,))
        addresses = cursor.fetchall()
    conn.close()
    return addresses

def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[^A-Za-z0-9]', password):
        return False
    return True

############################################################################################################
# Home & Dashboard
############################################################################################################
@main.route('/', methods=['GET', 'POST'])
def home():
    if not session.get('user_id'):
        return redirect(url_for('main.login'))
    return redirect(url_for('main.dashboard'))

@main.route('/dashboard')
def dashboard():
    user = None
    if 'user_id' in session:
        user = {
            'first_name': session.get('user_first_name'),
            'role': session.get('user_role')
        }
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Get featured products - mix of different categories

        # highest price products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name,
                'highest_price' as feature_type
            FROM
                product p
            JOIN
                category c 
                ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY
                p.price DESC
            LIMIT 3
        ''')
        highest_price_products = cursor.fetchall()
        
        # lowest price products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name,
                'lowest_price' as feature_type
            FROM
                product p
            JOIN
                category c 
                ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY
                p.price ASC
            LIMIT 3
        ''')
        lowest_price_products = cursor.fetchall()
        
        # newest products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name,
                'newest' as feature_type
            FROM
                product p
            JOIN
                category c 
                ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY
                p.product_id DESC
            LIMIT 3
        ''')
        newest_products = cursor.fetchall()
        
        # most ordered products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name,
                'most_ordered' as feature_type
            FROM
                product p
            JOIN
                category c 
                ON p.category_id = c.category_id
            LEFT JOIN
                Order_Line ol 
                ON p.product_id = ol.product_id
            WHERE p.is_active = TRUE
            GROUP BY
                p.product_id
            ORDER BY
                COUNT(ol.order_line_id) DESC
            LIMIT 8
        ''')
        most_ordered_products = cursor.fetchall()
        
        # Combine all featured products
        featured_products = (
            highest_price_products[:2] +  # Take 2 highest price
            lowest_price_products[:2] +   # Take 2 lowest price
            newest_products[:2] +         # Take 2 newest
            most_ordered_products[:2]     # Take 2 most ordered
        )
        # Newest products (same as featured, but keep for clarity)
        # Newest products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name
            FROM
                Product p
            JOIN
                Category c 
                ON p.category_id = c.category_id
            WHERE p.is_active = TRUE
            ORDER BY
                p.product_id DESC
            LIMIT 12
        ''')
        newest_products = cursor.fetchall()

        # Most stock products
        cursor.execute('''
            SELECT
                p.*,
                c.category_name,
                SUM(ws.stock_quantity) as total_stock
            FROM
                Product p
            JOIN
                Category c 
                ON p.category_id = c.category_id
            JOIN
                Warehouse_Stock ws 
                ON p.product_id = ws.product_id
            JOIN
                Warehouse w ON ws.warehouse_id = w.warehouse_id
            WHERE
                p.is_active = TRUE AND w.is_active = TRUE
            GROUP BY
                p.product_id
            ORDER BY
                total_stock DESC
            LIMIT 12
        ''')
        most_stock_products = cursor.fetchall()

        # Categories
        cursor.execute('''
            SELECT
                *
            FROM
                Category
            WHERE is_active = TRUE
        ''')
        categories = cursor.fetchall()

        # User count
        cursor.execute('''
            SELECT
                COUNT(*) AS user_count
            FROM
                Person
            WHERE
                role = %s AND is_active = TRUE
        ''', ('customer',))
        user_count = cursor.fetchone()['user_count']

        # Order count
        cursor.execute('''
            SELECT
                COUNT(*) AS order_count
            FROM
                Orders
        ''')
        order_count = cursor.fetchone()['order_count']

        # Product count
        cursor.execute('''
            SELECT
                COUNT(*) AS product_count
            FROM
                Product
            WHERE is_active = TRUE
        ''')
        product_count = cursor.fetchone()['product_count']

        # Category count
        cursor.execute('''
            SELECT
                COUNT(*) AS category_count
            FROM
                Category
            WHERE is_active = TRUE
        ''')
        category_count = cursor.fetchone()['category_count']

        # Warehouse count
        cursor.execute('''
            SELECT
                COUNT(*) AS warehouse_count
            FROM
                Warehouse
            WHERE is_active = TRUE
        ''')
        warehouse_count = cursor.fetchone()['warehouse_count']

        # Prepare last 6 months labels
        today = datetime.today().replace(day=1)
        months = []
        for i in range(5, -1, -1):
            month = (today - timedelta(days=30*i))
            months.append(month.strftime('%b %Y'))

        # Helper to get the last day of a month
        def last_day_of_month(dt):
            next_month = dt.replace(day=28) + timedelta(days=4)
            return next_month - timedelta(days=next_month.day)

        # Get current total stock
        cursor.execute('''
            SELECT
                SUM(ws.stock_quantity) as total_stock
            FROM
                Warehouse_Stock ws
            JOIN
                Product p ON ws.product_id = p.product_id
            JOIN
                Warehouse w ON ws.warehouse_id = w.warehouse_id
            WHERE
                p.is_active = TRUE AND w.is_active = TRUE
        ''')
        current_total_stock = cursor.fetchone()['total_stock'] or 0

        # For each month, sum the quantity of products ordered in that month
        orders_per_month = []
        products_over_time = []
        stocks_over_time = []
        orders_qty_per_month = []
        for i in range(5, -1, -1):
            month_start = (today - timedelta(days=30*i)).replace(day=1)
            month_end = last_day_of_month(month_start)
            # Orders in this month
            cursor.execute('''
                SELECT
                    COUNT(*) as count
                FROM
                    Orders
                WHERE
                    order_date >= %s AND order_date <= %s
            ''',
                (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
            orders_per_month.append(cursor.fetchone()['count'])
            # Products up to end of this month
            cursor.execute(
                "SELECT COUNT(*) as count FROM Product WHERE created_at <= %s AND is_active = TRUE",
                (month_end.strftime('%Y-%m-%d 23:59:59'),)
            )
            products_over_time.append(cursor.fetchone()['count'])
            # Total quantity ordered in this month
            cursor.execute(
                "SELECT SUM(ol.quantity) as qty FROM Order_Line ol JOIN Orders o ON ol.order_id = o.order_id JOIN Product p ON ol.product_id = p.product_id WHERE o.order_date >= %s AND o.order_date <= %s AND p.is_active = TRUE",
                (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))
            )
            qty_row = cursor.fetchone()
            orders_qty_per_month.append(qty_row['qty'] if qty_row and qty_row['qty'] is not None else 0)
        # Simulate stocks over time (reverse accumulate)
        running_stock = current_total_stock
        for qty in reversed(orders_qty_per_month):
            stocks_over_time.insert(0, running_stock)
            running_stock += qty

        # Order status breakdown (always show all statuses)
        all_statuses = [
            ('Processing', '#ffc107'),
            ('Shipped', '#28a745'),
            ('Delivered', '#007bff'),
            ('Cancelled', '#dc3545')
        ]
        cursor.execute('''
            SELECT
                order_status,
                COUNT(*) as count
            FROM
                Orders
            GROUP BY
                order_status
        ''')
        raw_status_data = cursor.fetchall()
        status_count_map = {row['order_status']: row['count'] for row in raw_status_data}
        order_status_data = [
            {'order_status': status, 'count': status_count_map.get(status, 0)}
            for status, _ in all_statuses
        ]
        order_status_colors = [color for _, color in all_statuses]
    conn.close()
    return render_template(
        'customer_dashboard.html',
        user=user,
        categories=categories,
        featured_products=featured_products,
        newest_products=newest_products,
        most_ordered_products=most_ordered_products,
        most_stock_products=most_stock_products,
        user_count=user_count,
        order_count=order_count,
        product_count=product_count,
        category_count=category_count,
        warehouse_count=warehouse_count,
        months=months,
        orders_per_month=orders_per_month,
        products_over_time=products_over_time,
        stocks_over_time=stocks_over_time,
        order_status_data=order_status_data,
        order_status_colors=order_status_colors
    )

############################################################################################################
# Registration
############################################################################################################
@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        profile_picture = request.files.get('profile_picture')

        # Basic validation
        if not all([first_name, last_name, email, password, confirm_password]):
            flash('Please fill in all fields.', 'danger')
            return render_template('register.html')
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if not is_strong_password(password):
            flash('Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.', 'danger')
            return render_template('register.html')
        # Email format validation
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash('Invalid email format.', 'danger')
            return render_template('register.html')
        # Check if email already exists
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM Person WHERE email = %s', (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash('Email already registered. Please login or use another email.', 'danger')
                conn.close()
                return render_template('register.html')
            # Hash password
            hashed_password = generate_password_hash(password).decode('utf-8')
            cursor.execute('''
                INSERT INTO Person (first_name, last_name, email, passcode, role)
                VALUES (%s, %s, %s, %s, %s)
            ''', (first_name, last_name, email, hashed_password, 'customer'))
            user_id = cursor.lastrowid
            if profile_picture and profile_picture.filename:
                try:
                    picture_path = save_profile_picture(profile_picture, user_id)
                    cursor.execute('UPDATE Person SET profile_picture = %s WHERE person_id = %s',
                                 (picture_path, user_id))
                except Exception as e:
                    flash('Error saving profile picture. Please try again.', 'danger')
                    conn.rollback()
                    conn.close()
                    return render_template('register.html')
            conn.commit()
            flash('Registration successful! You can now login.', 'success')
        conn.close()
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/verify-email/<token>')
def verify_email(token):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM Person WHERE email_verification_token = %s', (token,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute('''
                UPDATE Person 
                SET email_verified = TRUE, 
                    email_verification_token = NULL 
                WHERE person_id = %s
            ''', (user['person_id'],))
            conn.commit()
            flash('Email verified successfully! You can now login.', 'success')
        else:
            flash('Invalid or expired verification token.', 'danger')
    
    conn.close()
    return redirect(url_for('main.home'))

############################################################################################################
# Login
############################################################################################################
@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')
            
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM Person WHERE email = %s', (email,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['passcode'], password):
                    session['user_id'] = user['person_id']
                    session['user_first_name'] = user['first_name']
                    session['user_role'] = user['role']
                    flash('Login successful!', 'success')
                    return redirect(url_for('main.dashboard'))
                else:
                    flash('Invalid email or password.', 'danger')
        except Exception as e:
            flash('An error occurred during login. Please try again.', 'danger')
            print(f"Login error: {str(e)}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass  # Ignore any errors when closing the connection
                    
    return render_template('login.html')

@main.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.home'))

############################################################################################################
# Profile
############################################################################################################
@main.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('main.home'))
    user_id = session['user_id']
    conn = get_db_connection()
    user = None
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM Person WHERE person_id = %s', (user_id,))
        user = cursor.fetchone()
    if request.method == 'POST':
        # Update profile picture
        profile_picture = request.files.get('profile_picture')
        if profile_picture and profile_picture.filename:
            with conn.cursor() as cursor:
                cursor.execute('SELECT profile_picture FROM Person WHERE person_id = %s', (user_id,))
                current_picture = cursor.fetchone()['profile_picture']
                if current_picture:
                    delete_profile_picture(current_picture)
                try:
                    picture_path = save_profile_picture(profile_picture, user_id)
                    cursor.execute('UPDATE Person SET profile_picture = %s WHERE person_id = %s', (picture_path, user_id))
                    conn.commit()
                    flash('Profile picture updated successfully!', 'success')
                except Exception as e:
                    flash('Error updating profile picture. Please try again.', 'danger')
                    conn.rollback()
        # Update name/email/password
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        update_fields = []
        update_values = []
        if first_name and first_name != user['first_name']:
            update_fields.append('first_name = %s')
            update_values.append(first_name)
        if last_name and last_name != user['last_name']:
            update_fields.append('last_name = %s')
            update_values.append(last_name)
        if email and email != user['email']:
            # Check if email already exists
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM Person WHERE email = %s AND person_id != %s', (email, user_id))
                if cursor.fetchone():
                    flash('Email already in use by another account.', 'danger')
                    conn.close()
                    return redirect(url_for('main.profile'))
            update_fields.append('email = %s')
            update_values.append(email)
        if new_password:
            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                conn.close()
                return redirect(url_for('main.profile'))
            if not is_strong_password(new_password):
                flash('Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.', 'danger')
                conn.close()
                return redirect(url_for('main.profile'))
            hashed_password = generate_password_hash(new_password).decode('utf-8')
            update_fields.append('passcode = %s')
            update_values.append(hashed_password)
        if update_fields:
            update_values.append(user_id)
            with conn.cursor() as cursor:
                cursor.execute(f'UPDATE Person SET {", ".join(update_fields)} WHERE person_id = %s', tuple(update_values))
                conn.commit()
                flash('Profile updated successfully!', 'success')
        # Refresh user info
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM Person WHERE person_id = %s', (user_id,))
            user = cursor.fetchone()
    conn.close()
    return render_template('profile.html', user=user)

############################################################################################################
# Product Browsing
############################################################################################################
@main.route('/products')
def products():
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'newest')
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Build the complete query with all filtering and sorting in SQL
        query = '''
            WITH product_stats AS (
                SELECT 
                    p.product_id,
                    p.product_name,
                    p.brand,
                    p.price,
                    p.photo,
                    p.category_id,
                    c.category_name,
                    CASE 
                        WHEN SUM(ws.stock_quantity) IS NULL THEN 0 
                        ELSE SUM(ws.stock_quantity) 
                    END AS stock_quantity,
                    COUNT(ol.order_line_id) AS order_count
                FROM 
                    Product p
                JOIN 
                    Category c ON p.category_id = c.category_id
                LEFT JOIN 
                    Warehouse_Stock ws ON p.product_id = ws.product_id
                LEFT JOIN 
                    Order_Line ol ON p.product_id = ol.product_id
                WHERE 
                    p.is_active = TRUE

        '''
        params = []

        # Add category filter
        if category_id:
            query += ' AND p.category_id = %s'
            params.append(category_id)

        # Add search filter
        if search:
            query += ' AND (p.product_name LIKE %s OR p.brand LIKE %s)'
            params.extend([f'%{search}%', f'%{search}%'])

        # Complete the CTE
        query += '''
                GROUP BY 
                    p.product_id, p.product_name, p.brand, p.price, 
                    p.photo, p.category_id, c.category_name
            )
            SELECT 
                ps.*,
                CASE 
                    WHEN %s = 'price_desc' AND ROW_NUMBER() OVER (ORDER BY ps.price DESC) <= 6 THEN 'highest_price'
                    WHEN %s = 'price_asc' AND ROW_NUMBER() OVER (ORDER BY ps.price ASC) <= 6 THEN 'lowest_price'
                    WHEN %s = 'newest' AND ROW_NUMBER() OVER (ORDER BY ps.product_id DESC) <= 6 THEN 'newest'
                    WHEN ps.order_count > 0 THEN 'most_ordered'
                    ELSE NULL
                END as feature_type
            FROM 
                product_stats ps
        '''
        params.extend([sort, sort, sort])

        # Add sorting
        if sort == 'price_asc':
            query += ' ORDER BY ps.price ASC'
        elif sort == 'price_desc':
            query += ' ORDER BY ps.price DESC'
        elif sort == 'name_asc':
            query += ' ORDER BY ps.product_name ASC'
        elif sort == 'name_desc':
            query += ' ORDER BY ps.product_name DESC'
        else:  # newest
            query += ' ORDER BY ps.product_id DESC'

        # Execute the query
        cursor.execute(query, params)
        products = cursor.fetchall()

        # Fetch categories for filter bar
        cursor.execute('SELECT * FROM Category WHERE is_active = TRUE')
        categories = cursor.fetchall()

    conn.close()
    return render_template('products.html', products=products, categories=categories, selected_category=category_id, search=search, sort=sort)

@main.route('/categories')
def categories_view():
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal and page display
        cursor.execute('SELECT * FROM Category WHERE is_active = TRUE') # Fetch all categories for modal and page content
        categories = cursor.fetchall()
    conn.close()
    return render_template('categories.html', categories=categories)

@main.route('/categories/<int:category_id>')
def category_products(category_id):
    return redirect(url_for('main.products', category=category_id))

@main.route('/products/<int:product_id>')
def product_details(product_id):
    conn = get_db_connection()
    with conn.cursor() as cursor:

        # Product details
        cursor.execute('''
            SELECT p.*, c.category_name 
            FROM Product p 
            JOIN Category c ON p.category_id = c.category_id 
            WHERE p.product_id = %s AND p.is_active = TRUE
        ''', (product_id,))
        product = cursor.fetchone()

        # Categories
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()

        # Stock quantity
        cursor.execute('SELECT SUM(ws.stock_quantity) as total_stock FROM Warehouse_Stock ws JOIN Warehouse w ON ws.warehouse_id = w.warehouse_id WHERE ws.product_id = %s AND w.is_active = TRUE', (product_id,))
        stock_row = cursor.fetchone()
        stock_quantity = stock_row['total_stock'] if stock_row and stock_row['total_stock'] is not None else 0
        
        # Fetch suppliers for this product
        cursor.execute('''
            SELECT s.supplier_id, s.supplier_name
            FROM Supplier s
            JOIN Supplier_Product sp ON s.supplier_id = sp.supplier_id
            WHERE sp.product_id = %s AND s.is_active = TRUE
            ORDER BY s.supplier_name ASC
        ''', (product_id,))
        suppliers = cursor.fetchall()
        
    conn.close()
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('main.products'))
    return render_template('product_details.html', product=product, categories=categories, stock_quantity=stock_quantity, suppliers=suppliers)

############################################################################################################
# Cart
############################################################################################################
@main.route('/cart/add/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    session['cart'] = cart
    flash('Product added to cart!', 'success')
    return redirect(request.referrer or url_for('main.products'))

@main.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    conn = get_db_connection()
    with conn.cursor() as cursor:
        product_ids = list(map(int, cart.keys()))
        if product_ids:
            format_strings = ','.join(['%s'] * len(product_ids))
            cursor.execute(f"SELECT * FROM Product WHERE product_id IN ({format_strings}) AND is_active = TRUE", tuple(product_ids))
            products = cursor.fetchall()
        else:
            products = []
    conn.close()
    cart_items = []
    total = 0
    for product in products:
        pid = str(product['product_id'])
        quantity = cart[pid]
        subtotal = product['price'] * quantity
        total += subtotal
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'subtotal': subtotal
        })
    return render_template('cart.html', cart_items=cart_items, total=total)

@main.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash('Product removed from cart.', 'success')
    from_place_order = request.form.get('from_place_order')
    if from_place_order:
        return redirect(url_for('main.place_order'))
    else:
        return redirect(url_for('main.view_cart'))

@main.route('/cart/clear', methods=['POST'])
def clear_cart():
    session.pop('cart', None)
    flash('Your cart has been cleared.', 'success')
    return redirect(url_for('main.view_cart'))

############################################################################################################
# Orders
############################################################################################################
@main.route('/orders/new', methods=['GET', 'POST'])
def place_order():
    if 'user_id' not in session:
        flash('You must be logged in to place an order.', 'danger')
        return redirect(url_for('main.home'))

    # Define available payment methods
    AVAILABLE_PAYMENT_METHODS = [
        'Credit Card',
        'Cash on Delivery'
    ]

    person_id = session['user_id']
    cart = session.get('cart', {})
    cart_items = []
    estimated_shipping_days = None
    estimated_delivery_days = None
    if cart:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            product_ids = list(map(int, cart.keys()))
            if product_ids:
                format_strings = ','.join(['%s'] * len(product_ids))
                cursor.execute(f"SELECT * FROM Product WHERE product_id IN ({format_strings})", tuple(product_ids))
                products = cursor.fetchall()
            else:
                products = []
        conn.close()
        for product in products:
            pid = str(product['product_id'])
            quantity = cart[pid]
            subtotal = product['price'] * quantity
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
    # --- Calculate estimated shipping/delivery days based on system load and last N orders ---
    conn = get_db_connection()
   
    # Calculate cart subtotal
    cart_subtotal = sum(float(item['product']['price']) * item['quantity'] for item in cart_items)
   
    with conn.cursor() as cursor:
        # Number of orders currently being processed
        cursor.execute("SELECT COUNT(*) as cnt FROM Orders WHERE order_status = 'Processing'")
        processing_count = cursor.fetchone()['cnt']
        # Number of orders currently being shipped
        cursor.execute("SELECT COUNT(*) as cnt FROM Orders WHERE order_status = 'Shipped'")
        shipped_count = cursor.fetchone()['cnt']
        # Average shipping/delivery time of last 10 delivered orders
        cursor.execute("""
            SELECT AVG(DATEDIFF(shipped_date, order_date)) as avg_ship, AVG(DATEDIFF(delivery_date, order_date)) as avg_deliver
            FROM Orders
            WHERE shipped_date IS NOT NULL AND delivery_date IS NOT NULL
            ORDER BY order_id DESC
            LIMIT 10
        """)
        row = cursor.fetchone()
        avg_ship = row['avg_ship'] or 2
        avg_deliver = row['avg_deliver'] or 4
        # Calculate dynamic days
        shipped_day = int(round(avg_ship + processing_count // 10))
        expected_delivery_day = int(round(avg_deliver + shipped_count // 10))
        # Set minimum and maximum bounds
        shipped_day = max(1, min(shipped_day, 5))
        expected_delivery_day = max(shipped_day + 1, min(expected_delivery_day, 10))
        estimated_shipping_days = shipped_day
        estimated_delivery_days = expected_delivery_day
    conn.close()
    if request.method == 'POST':
        address_id = request.form.get('address_id')
        if not address_id:
            flash('Please select an address.', 'danger')
            return redirect(url_for('main.place_order'))
        if not cart:
            flash('Your cart is empty.', 'danger')
            return redirect(url_for('main.products'))
        payment_method = request.form.get('payment_method')

        if not payment_method or payment_method not in AVAILABLE_PAYMENT_METHODS:
            flash('Invalid payment method selected.', 'danger')
            addresses = get_user_addresses(person_id)
            return render_template('place_order.html',
                                   addresses=addresses,
                                   cart_items=cart_items,
                                   estimated_shipping_days=estimated_shipping_days,
                                   estimated_delivery_days=estimated_delivery_days,
                                   shipping_cost=FLAT_SHIPPING_RATE,
                                   cart_subtotal=cart_subtotal,
                                   allowed_cities=ALLOWED_CITIES,
                                   available_payment_methods=AVAILABLE_PAYMENT_METHODS,
                                   form_data=request.form)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Lock stock rows for update to prevent race conditions
                for item in cart_items:
                    product_id = item['product']['product_id']
                    cursor.execute('SELECT SUM(stock_quantity) as total_stock FROM Warehouse_Stock ws JOIN Product p ON ws.product_id = p.product_id WHERE ws.product_id = %s AND p.is_active = TRUE FOR UPDATE', (product_id,))
                    row = cursor.fetchone()
                    total_stock = row['total_stock'] if row and row['total_stock'] is not None else 0
                    if total_stock < item['quantity']:
                        flash(f"Not enough stock for {item['product']['product_name']} (needed: {item['quantity']}, available: {total_stock})", 'danger')
                        conn.rollback()
                        return redirect(url_for('main.place_order'))
                # Place order and order lines
                cursor.execute(
                    'INSERT INTO Orders (person_id, address_id, order_date, order_status, order_type, shipping_cost) VALUES (%s, %s, NOW(), %s, %s, %s)',
                    (person_id, address_id, 'Processing', 'customer', FLAT_SHIPPING_RATE)
                )
                order_id = cursor.lastrowid
                # Assign shipped_day and expected_delivery_day based on calculated values
                cursor.execute('UPDATE Orders SET shipped_day = %s, expected_delivery_day = %s WHERE order_id = %s',
                               (shipped_day, expected_delivery_day, order_id))
                for item in cart_items:
                    cursor.execute(
                        'INSERT INTO Order_Line (order_id, product_id, quantity, order_line_states) VALUES (%s, %s, %s, %s)',
                        (order_id, item['product']['product_id'], item['quantity'], 'Processing')
                    )
                # Deduct stock from warehouses (prioritize largest stock first)
                for item in cart_items:
                    product_id = item['product']['product_id']
                    quantity_to_deduct = item['quantity']
                    cursor.execute('SELECT warehouse_id, stock_quantity FROM Warehouse_Stock ws JOIN Product p ON ws.product_id = p.product_id WHERE ws.product_id = %s AND ws.stock_quantity > 0 AND p.is_active = TRUE ORDER BY stock_quantity DESC FOR UPDATE', (product_id,))
                    warehouses = cursor.fetchall()
                    for wh in warehouses:
                        if quantity_to_deduct <= 0:
                            break
                        deduct = min(wh['stock_quantity'], quantity_to_deduct)
                        cursor.execute('UPDATE Warehouse_Stock SET stock_quantity = stock_quantity - %s WHERE warehouse_id = %s AND product_id = %s',
                                       (deduct, wh['warehouse_id'], product_id))
                        quantity_to_deduct -= deduct

                payment_states = 'Pending'
                card_last_four_digits = None
                cardholder_name = None
                expiration_date = request.form.get('expiration_date')

                if payment_method == 'Credit Card':
                    card_number = request.form.get('card_number')
                    cardholder_name = request.form.get('cardholder_name')
                    expiration_date = request.form.get('expiration_date')

                    # Basic Credit Card Validation
                    if not card_number or not re.fullmatch(r'\d{16}', card_number):
                        raise ValueError('Invalid card number. Must be 16 digits.')
                    if not cardholder_name or not re.fullmatch(r'[A-Za-z\s]+', cardholder_name):
                        raise ValueError('Invalid cardholder name. Must contain only letters and spaces.')
                    if not expiration_date or not re.fullmatch(r'(0[1-9]|1[0-2])\/\d{2}', expiration_date):
                        raise ValueError('Invalid expiration date format. Use MM/YY.')

                    # Expiration date must not be in the past and must not exceed 10 years in the future
                    from datetime import datetime
                    now = datetime.now()
                    try:
                        exp_month, exp_year = map(int, expiration_date.split('/'))
                        exp_year += 2000 if exp_year < 100 else 0
                        exp_date = datetime(exp_year, exp_month, 1)
                        # Card is valid through the end of the expiration month
                        last_valid = datetime(exp_year, exp_month, 28)  # 28 is safe for all months
                        if last_valid.replace(day=28) < now.replace(day=1):
                            raise ValueError('Credit card is expired.')
                        # Check if expiration date exceeds 10 years in the future
                        max_valid = now.replace(year=now.year + 10)
                        if exp_date > max_valid:
                            raise ValueError('Credit card expiration date cannot exceed 10 years in the future.')
                    except Exception:
                        raise ValueError('Invalid expiration date. Please use MM/YY and ensure it is not expired and not more than 10 years in the future.')

                    # Hash the full card number for security
                    hashed_card_number = generate_password_hash(card_number).decode('utf-8')
                    card_last_four_digits = card_number[-4:]  # Store only last 4 digits in plain text
                    payment_states = 'Processing'  # Assume processing for credit card

                cursor.execute(
                    'INSERT INTO Payment (order_id, payment_method, amount_payment_date, payment_states, card_last_four_digits, cardholder_name, expiration_date, hashed_card_number) VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s)',
                    (order_id, payment_method, payment_states, card_last_four_digits, cardholder_name, expiration_date, hashed_card_number if payment_method == 'Credit Card' else None)
                )
                conn.commit()

            flash('Order placed successfully!', 'success')
            session['cart'] = {}
            return redirect(url_for('main.orders'))
        except Exception as e:
            conn.rollback()
            flash(f'Error placing order: {e}', 'danger')
            return redirect(url_for('main.place_order'))
        finally:
            conn.close()
    addresses = get_user_addresses(person_id)

    # Ensure available_payment_methods is passed for GET requests and POST failures
    return render_template('place_order.html',
                          addresses=addresses,
                          cart_items=cart_items,
                          estimated_shipping_days=estimated_shipping_days,
                          estimated_delivery_days=estimated_delivery_days,
                          shipping_cost=FLAT_SHIPPING_RATE,
                          cart_subtotal=cart_subtotal,
                          allowed_cities=ALLOWED_CITIES,
                          available_payment_methods=AVAILABLE_PAYMENT_METHODS, # Ensure this is passed explicitly
                          form_data=request.form)

@main.route('/orders')
def orders():
    if 'user_id' not in session:
        flash('You must be logged in to view your orders.', 'danger')
        return redirect(url_for('main.home'))
    person_id = session['user_id']
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('''
            SELECT 
                o.*, 
                a.city, 
                a.street_address,
                (
                    SELECT 
                        CASE 
                            WHEN SUM(ol.quantity * p.price) IS NULL THEN 0 
                            ELSE SUM(ol.quantity * p.price) 
                        END
                    FROM 
                        Order_Line ol 
                    JOIN 
                        Product p 
                        ON ol.product_id = p.product_id 
                    WHERE 
                        ol.order_id = o.order_id AND p.is_active = TRUE
                ) AS items_subtotal,
                (
                    SELECT 
                        CASE 
                            WHEN SUM(ol.quantity) IS NULL THEN 0 
                            ELSE SUM(ol.quantity) 
                        END
                    FROM 
                        Order_Line ol 
                    JOIN
                        Product p
                        ON ol.product_id = p.product_id
                    WHERE 
                        ol.order_id = o.order_id AND p.is_active = TRUE
                ) AS items_count
            FROM 
                Orders o
            JOIN 
                Address a 
                ON o.address_id = a.address_id
            WHERE 
                o.person_id = %s
            ORDER BY 
                o.order_date DESC
        ''', (person_id,))
        orders = cursor.fetchall()
        today = datetime.now().date()
        for order in orders:
            # Calculate total including shipping cost
            order['total'] = float(order['items_subtotal'] or 0) + float(order['shipping_cost'] or 0)
            update_order_status_if_needed(order, cursor, today)
        conn.commit()
    conn.close()
    return render_template('orders.html', orders=orders)

@main.route('/orders/<int:order_id>')
def order_details(order_id):
    if 'user_id' not in session:
        flash('Please log in to view order details', 'danger')
        return redirect(url_for('main.login'))
    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    # Allow admin and staff to view any order, users only their own
    if session.get('user_role') in ['admin', 'staff']:
        cursor.execute('''
            SELECT 
                o.*, 
                a.street_address, 
                a.city, 
                p.first_name, 
                p.last_name, 
                p.email -- Fetch customer details
            FROM 
                Orders o 
            JOIN 
                Address a ON o.address_id = a.address_id 
            JOIN 
                Person p ON o.person_id = p.person_id -- Join with Person table
            WHERE o.order_id = %s
        ''', (order_id,))
    else:
        cursor.execute('''
            SELECT 
                o.*, 
                a.street_address, 
                a.city, 
                p.first_name, 
                p.last_name, 
                p.email -- Fetch customer details
            FROM 
                Orders o 
            JOIN 
                Address a ON o.address_id = a.address_id 
            JOIN 
                Person p ON o.person_id = p.person_id -- Join with Person table
            WHERE o.order_id = %s AND o.person_id = %s
        ''', (order_id, session['user_id']))
    order = cursor.fetchone()
    if not order:
        flash('Order not found', 'danger')
        cursor.close()
        conn.close()
        if session.get('user_role') in ['admin', 'staff']:
            return redirect(url_for('main.admin_orders'))
        else:
            return redirect(url_for('main.orders'))
    today = datetime.now().date()
    status_changed_by_date = update_order_status_if_needed(order, cursor, today)
    
    # If the order is already Shipped or Delivered (either by date update above or previously),
    # ensure all order line states match the main order status.
    if order['order_status'] in ['Shipped', 'Delivered']:
        print(f"Checking order line states for order {order['order_id']}. Main status is {order['order_status']}")
        # Check current order line states without fetching all details yet
        cursor.execute('SELECT DISTINCT order_line_states FROM Order_Line WHERE order_id = %s', (order_id,))
        distinct_line_states = [row['order_line_states'] for row in cursor.fetchall()]
        print(f"Distinct order line states found: {distinct_line_states}")

        # If any line is not in the main order status, update all lines
        if not all(state == order['order_status'] for state in distinct_line_states):
            print(f"Main order {order['order_id']} is {order['order_status']}, but not all lines match. Updating line states.")
            cursor.execute('UPDATE Order_Line SET order_line_states = %s WHERE order_id = %s',
                           (order['order_status'], order_id))
            status_changed_by_manual_check = True
        else:
            print(f"All order line states for order {order['order_id']} already match main status {order['order_status']}.")
            status_changed_by_manual_check = False
    else:
        status_changed_by_manual_check = False
    
    conn.commit()

    # Calculate order date and days since order
    order_date = order['order_date']
    if isinstance(order_date, str):
        order_date_dt = datetime.strptime(order_date, '%Y-%m-%d')
    else:
        order_date_dt = order_date
    if isinstance(order_date_dt, datetime):
        order_date_val = order_date_dt.date()
    else:
        order_date_val = order_date_dt
    shipped_day = order.get('shipped_day') or 2
    expected_delivery_day = order.get('expected_delivery_day') or 4
    expected_shipping_date = (order_date_val + timedelta(days=shipped_day)).strftime('%Y-%m-%d')
    shipped_date = order.get('shipped_date')
    if shipped_date:
        shipped_date = shipped_date.strftime('%Y-%m-%d') if hasattr(shipped_date, 'strftime') else str(shipped_date)
    expected_delivery_date = (order_date_val + timedelta(days=expected_delivery_day)).strftime('%Y-%m-%d')
    delivery_date = order.get('delivery_date')
    is_delivered = order['order_status'] == 'Delivered'
    is_shipped = order['order_status'] in ['Shipped', 'Delivered']
    # Get order items with product information
    cursor.execute('''
        SELECT ol.*, p.product_name, p.brand, p.price, p.photo 
        FROM Order_Line ol 
        JOIN Product p ON ol.product_id = p.product_id 
        WHERE ol.order_id = %s
    ''', (order_id,))
    raw_items = cursor.fetchall()
    # Structure the order items data
    order_items = []
    order_total = 0.0
    for item in raw_items:
        product = {
            'product_id': item['product_id'],
            'product_name': item['product_name'],
            'brand': item['brand'],
            'price': item['price'],
            'photo': item['photo']
        }
        # Ensure subtotal is calculated as float
        subtotal = float(item['price']) * item['quantity']
        order_total += subtotal
        order_items.append({
            'product': product,
            'quantity': item['quantity'],
            'subtotal': subtotal,
            'order_line_states': item['order_line_states']
        })
    # Add shipping cost to the total
    shipping_cost = float(order.get('shipping_cost', 0) or 0)
    order_total = order_total + shipping_cost # This addition should now be float + float

    # Get payment information
    cursor.execute('''
        SELECT * FROM Payment WHERE order_id = %s
    ''', (order_id,))
    payment = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template('order_details.html', 
                         order=order, 
                         order_items=order_items, 
                         order_total=order_total,
                         shipped_date=shipped_date,
                         expected_shipping_date=expected_shipping_date,
                         expected_delivery_date=expected_delivery_date,
                         is_delivered=is_delivered,
                         is_shipped=is_shipped,
                         payment=payment)

############################################################################################################
# Address
############################################################################################################
@main.route('/address/add', methods=['POST'])
def add_address():
    if 'user_id' not in session:
        flash('You must be logged in.', 'danger')
        return redirect(url_for('main.home'))

    person_id = session['user_id']
    city = request.form.get('city')
    street_address = request.form.get('street_address')

    if not city or not street_address:
        flash('Please fill in all address fields.', 'danger')
        return redirect(request.referrer or url_for('main.place_order'))

    if city not in ALLOWED_CITIES:
        flash('Invalid city selected.', 'danger')
        return redirect(request.referrer or url_for('main.place_order'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO Address (person_id, city, street_address) VALUES (%s, %s, %s)',
            (person_id, city, street_address)
        )
        conn.commit()
    flash('Address added successfully!', 'success')
    return redirect(request.referrer or url_for('main.place_order'))

############################################################################################################
# Admin Section 
############################################################################################################
# Admin Dashboard (admin only)
@main.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('You must be an admin to access the admin dashboard.', 'danger')
        return redirect(url_for('main.home'))
    user = {
        'first_name': session.get('user_first_name'),
        'role': session.get('user_role')
    }
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Stats
        # this will count all users that are customers 
        cursor.execute("SELECT COUNT(*) AS user_count FROM Person WHERE role = 'customer' AND is_active = TRUE")
        user_count = cursor.fetchone()['user_count']

        # this will count all users that are staff
        cursor.execute("SELECT COUNT(*) AS staff_count FROM Person WHERE role = 'staff' AND is_active = TRUE")
        staff_count = cursor.fetchone()['staff_count']

        # this will count all orders
        cursor.execute("SELECT COUNT(*) AS order_count FROM Orders")
        order_count = cursor.fetchone()['order_count']


        # Calculate total sales (including COD only when delivered) 
        # if the order is delivered, then the payment method is not cash on delivery

        #****************mahmoud check if this is correct****************************************************************
        cursor.execute('''
            SELECT IFNULL(SUM(ol.quantity * p.price), 0) AS total_sales
            FROM Order_Line ol
            JOIN Product p ON ol.product_id = p.product_id
            JOIN Orders o ON ol.order_id = o.order_id
            LEFT JOIN Payment pay ON o.order_id = pay.order_id
            WHERE (pay.payment_method != 'Cash on Delivery' OR o.order_status = 'Delivered') AND p.is_active = TRUE
        ''')

        #****************mahmoud these four queries are correct there is no need to check them *******************************************

        # this will count all products
        total_sales = float(cursor.fetchone()['total_sales'] or 0)
        cursor.execute("SELECT COUNT(*) AS product_count FROM Product WHERE is_active = TRUE")

        # this will count all categories
        product_count = cursor.fetchone()['product_count']
        cursor.execute("SELECT COUNT(*) AS category_count FROM Category WHERE is_active = TRUE")
        category_count = cursor.fetchone()['category_count']

        # this will count all warehouses
        cursor.execute("SELECT COUNT(*) AS warehouse_count FROM Warehouse WHERE is_active = TRUE")
        warehouse_count = cursor.fetchone()['warehouse_count']
        
        # Get supplier count
        cursor.execute("SELECT COUNT(*) AS supplier_count FROM Supplier WHERE is_active = TRUE")
        supplier_count = cursor.fetchone()['supplier_count']


        #**********************************************************************************************************************
    
        # this will count all products and their total quantity sold
        cursor.execute('''
            SELECT 
                p.product_id,
                p.price,
                IFNULL(SUM(ol.quantity), 0) as total_quantity_sold
            FROM 
                Product p
            LEFT JOIN 
                Order_Line ol ON p.product_id = ol.product_id
            GROUP BY 
                p.product_id, p.price
        ''')
        products_data = cursor.fetchall()
        
        total_profit = 0
        for product in products_data:
            price = float(product['price'])
            quantity_sold = int(product['total_quantity_sold'] or 0)
            
            # Calculate profit based on price ranges
            if price <= 10.00:
                profit = (price * 0.40 + 1.50) * quantity_sold
            elif price <= 50.00:
                profit = (price * 0.30 + 2.00) * quantity_sold
            elif price <= 150.00:
                profit = (price * 0.25) * quantity_sold
            elif price <= 500.00:
                profit = (price * 0.20) * quantity_sold
            elif price <= 1000.00:
                profit = (price * 0.15) * quantity_sold
            elif price <= 2500.00:
                profit = (price * 0.12) * quantity_sold
            elif price <= 5000.00:
                profit = (price * 0.10) * quantity_sold
            else:
                profit = (price * 0.08) * quantity_sold
                
            total_profit += profit
        
        # ************************************************Ameer there is no need to check this query ********************************************************************

        # this will count the total number of stock items (sum of all stock quantities)
        cursor.execute('''
            SELECT 
                IFNULL(SUM(ws.stock_quantity), 0) AS total_stock_count 
            FROM 
                Warehouse_Stock ws
            JOIN
                Warehouse w ON ws.warehouse_id = w.warehouse_id
            WHERE
                w.is_active = TRUE
        ''')
        total_stock_count = cursor.fetchone()['total_stock_count']


        # this will count the number of unique addresses used in orders (this is correct)
        cursor.execute('''
            SELECT 
                COUNT(DISTINCT address_id) AS shipped_addresses_count 
            FROM 
                Orders
        ''')
        shipped_addresses_count = cursor.fetchone()['shipped_addresses_count']
        
        #******************************************* Ameer I think this query is correct but I am not sure ********************************************************************
        # Recent orders (last 5)
        cursor.execute('''
            SELECT 
                o.order_id, 
                o.order_date, 
                o.order_status, 
                o.order_type, 
                o.person_id, 
                p.first_name, 
                p.last_name,
                (
                    SELECT 
                        SUM(ol.quantity * pr.price) 
                    FROM 
                        Order_Line ol 
                    JOIN 
                        Product pr 
                        ON ol.product_id = pr.product_id 
                    WHERE 
                        ol.order_id = o.order_id
                ) AS total
            FROM 
                Orders o
            JOIN 
                Person p 
                ON o.person_id = p.person_id
            ORDER BY 
                o.order_date DESC, 
                o.order_id DESC
            LIMIT 5
        ''')
        recent_orders = cursor.fetchall()
        
        #******************************************* this query is correct ********************************************************************

        # Recent users (last 5)
        cursor.execute('''
            SELECT 
                person_id, 
                first_name, 
                last_name, 
                email, 
                created_at 
            FROM 
                Person 
            WHERE 
                role = 'customer' 
            ORDER BY 
                created_at DESC, 
                person_id DESC 
            LIMIT 5
        ''')
        recent_users = cursor.fetchall()
        
        
        #******************************************* these queries need to be checked ********************************************************************
        # Orders per month (last 6 months)
        today = datetime.today().replace(day=1)
        months = []
        orders_per_month = []
        sales_per_month = []
        for i in range(5, -1, -1):
            month_start = (today - timedelta(days=30*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            months.append(month_start.strftime('%b %Y'))
            cursor.execute('''
                SELECT 
                    COUNT(*) as count 
                FROM 
                    Orders 
                WHERE 
                    order_date >= %s 
                    AND order_date <= %s
            ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
            orders_per_month.append(cursor.fetchone()['count'])
            cursor.execute('''
                SELECT 
                    IFNULL(SUM(ol.quantity * p.price), 0) as sales 
                FROM 
                    Orders o 
                JOIN 
                    Order_Line ol 
                    ON o.order_id = ol.order_id 
                JOIN 
                    Product p 
                    ON ol.product_id = p.product_id 
                LEFT JOIN Payment pay ON o.order_id = pay.order_id
                WHERE 
                    o.order_date >= %s 
                    AND o.order_date <= %s
                    AND (pay.payment_method != 'Cash on Delivery' OR o.order_status = 'Delivered')
            ''', (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
            sales_per_month.append(float(cursor.fetchone()['sales'] or 0))
        
        # Get daily order count for the last 30 days
        today = datetime.now().date()
        thirty_days_ago = today - timedelta(days=30)
        cursor.execute('''
            SELECT
                DATE(order_date) AS order_day,
                COUNT(*) AS order_count
            FROM
                Orders
            WHERE
                order_date >= %s
            GROUP BY
                order_day
            ORDER BY
                order_day ASC
        ''', (thirty_days_ago.strftime('%Y-%m-%d'),))
        daily_orders_data = cursor.fetchall()
        
        # Create a list of dates for the last 30 days and merge with query results
        date_list = [(thirty_days_ago + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(31)]
        daily_order_counts = {row['order_day'].strftime('%Y-%m-%d'): row['order_count'] for row in daily_orders_data}
        orders_per_day = [daily_order_counts.get(date, 0) for date in date_list]

        # Get daily user registration count for the last 30 days (using created_at column)
        cursor.execute('''
            SELECT
                DATE(created_at) AS registration_day,
                COUNT(*) AS registration_count
            FROM
                Person
            WHERE
                created_at >= %s
            GROUP BY
                registration_day
            ORDER BY
                registration_day ASC
        ''', (thirty_days_ago.strftime('%Y-%m-%d 00:00:00'),))
        daily_registrations_data = cursor.fetchall()

        # Create a list of dates for the last 30 days and merge with query results
        # Reuse date_list from above
        daily_registration_counts = {row['registration_day'].strftime('%Y-%m-%d'): row['registration_count'] for row in daily_registrations_data}
        registrations_per_day = [daily_registration_counts.get(date, 0) for date in date_list]



        #******************************************* this query is checked and its correct ********************************************************************  

        # Order status breakdown (always show all statuses)
        all_statuses = [
            ('Processing', '#ffc107'),
            ('Shipped', '#28a745'),
            ('Delivered', '#007bff'),
            ('Cancelled', '#dc3545')
        ]
        cursor.execute('''
            SELECT 
                order_status, 
                COUNT(*) as count 
            FROM 
                Orders 
            GROUP BY 
                order_status
        ''')
        raw_status_data = cursor.fetchall()
        status_count_map = {row['order_status']: row['count'] for row in raw_status_data}
        order_status_data = [
            {'order_status': status, 'count': status_count_map.get(status, 0)}
            for status, _ in all_statuses
        ]
        order_status_colors = [color for _, color in all_statuses]



        #******************************************* this query is checked and its correct ********************************************************************  
        
        # Calculate total stock value
        cursor.execute('''
            SELECT 
                IFNULL(SUM(ws.stock_quantity * p.price), 0) as total_stock_value 
            FROM 
                Warehouse_Stock ws 
            JOIN 
                Product p 
                ON ws.product_id = p.product_id
            JOIN
                Warehouse w ON ws.warehouse_id = w.warehouse_id
            WHERE
                w.is_active = TRUE
        ''')
        total_stock_value = float(cursor.fetchone()['total_stock_value'] or 0)
        

        #******************************************* No need to check this query ********************************************************************  

        # Calculate user type breakdown
        cursor.execute('''
            SELECT 
                role, 
                COUNT(*) as count 
            FROM 
                Person 
            GROUP BY 
                role
        ''')
        user_type_data = cursor.fetchall()
        
        # Fetch categories for the navigation menu
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()


        
        #******************************************* this query is checked and its correct ********************************************************************  


        # Top 5 best-selling products
        cursor.execute('''
            SELECT 
                p.product_name, 
                SUM(ol.quantity) as total_qty
            FROM 
                Order_Line ol
            JOIN 
                Product p 
                ON ol.product_id = p.product_id
            GROUP BY 
                ol.product_id
            ORDER BY 
                total_qty DESC
            LIMIT 5
        ''')
        top_products = cursor.fetchall()


        #******************************************* this query is correct ********************************************************************  
        
        # Warehouse stock breakdown
        cursor.execute('''
            SELECT 
                w.location_name, 
                SUM(ws.stock_quantity) as total_stock
            FROM 
                Warehouse_Stock ws
            JOIN 
                Warehouse w 
                ON ws.warehouse_id = w.warehouse_id
            GROUP BY 
                ws.warehouse_id
        ''')
        warehouse_stock_data = cursor.fetchall()
        

        #***************************************************************************************************************  
        # Category sales breakdown
        cursor.execute('''
            SELECT 
                c.category_name, 
                IFNULL(SUM(ol.quantity * p.price), 0) as sales 
            FROM 
                Category c
            LEFT JOIN 
                Product p 
                ON p.category_id = c.category_id
            LEFT JOIN 
                Order_Line ol 
                ON ol.product_id = p.product_id
            GROUP BY 
                c.category_id
            ORDER BY 
                sales DESC
        ''')
        category_sales_data = cursor.fetchall()
        
        conn.close()
    return render_template(
        'admin_dashboard.html',
        user=user,
        categories=categories,
        user_count=user_count,
        staff_count=staff_count,
        order_count=order_count,
        total_sales=total_sales,
        product_count=product_count,
        category_count=category_count,
        warehouse_count=warehouse_count,
        supplier_count=supplier_count,
        total_stock_count=total_stock_count,
        shipped_addresses_count=shipped_addresses_count,
        recent_orders=recent_orders,
        recent_users=recent_users,
        months=months,
        orders_per_month=orders_per_month,
        sales_per_month=sales_per_month,
        order_status_data=order_status_data,
        order_status_colors=order_status_colors,
        total_stock_value=total_stock_value,
        user_type_data=user_type_data,
        top_products=top_products,
        warehouse_stock_data=warehouse_stock_data,
        category_sales_data=category_sales_data,
        products_data=products_data,
        total_profit=total_profit,
        dates_30_days=date_list, # Pass the date list for chart labels
        orders_per_day=orders_per_day, # Pass daily order data
        registrations_per_day=registrations_per_day # Pass daily registration data
    )

# Admin Products (admin and staff)
@main.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    # Get search, category filter, and sort parameters from request
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category', type=int)
    sort = request.args.get('sort', 'product_id_desc') # Default sort by newest product ID

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal and filter dropdown
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()

        # Build the complete query with all filtering and sorting in SQL
        query = '''
            WITH product_stats AS (
                SELECT 
                    p.product_id,
                    p.product_name,
                    p.product_description,
                    p.brand,
                    p.price,
                    p.photo,
                    p.category_id,
                    c.category_name,
                    GROUP_CONCAT(s.supplier_name ORDER BY s.supplier_name SEPARATOR ', ') AS suppliers
                FROM 
                    Product p
                JOIN 
                    Category c ON p.category_id = c.category_id
                LEFT JOIN 
                    Supplier_Product sp ON p.product_id = sp.product_id
                LEFT JOIN
                    Supplier s ON sp.supplier_id = s.supplier_id
                WHERE 
                    p.is_active = TRUE
        '''
        params = []

        # Add category filter
        if category_id:
            query += ' AND p.category_id = %s'
            params.append(category_id)

        # Add search filter
        if search:
            query += ' AND (p.product_name LIKE %s OR p.brand LIKE %s)'
            params.extend([f'%{search}%', f'%{search}%'])

        # Complete the CTE
        query += '''
                GROUP BY 
                    p.product_id, p.product_name, p.product_description, p.brand, 
                    p.price, p.photo, p.category_id, c.category_name
            )
            SELECT 
                ps.*
            FROM 
                product_stats ps
        '''

        # Add sorting
        if sort == 'price_asc':
            query += ' ORDER BY ps.price ASC'
        elif sort == 'price_desc':
            query += ' ORDER BY ps.price DESC'
        elif sort == 'name_asc':
            query += ' ORDER BY ps.product_name ASC'
        elif sort == 'name_desc':
            query += ' ORDER BY ps.product_name DESC'
        elif sort == 'category_asc':
            query += ' ORDER BY ps.category_name ASC'
        elif sort == 'category_desc':
            query += ' ORDER BY ps.category_name DESC'
        else:  # Default sort by newest product_id
            query += ' ORDER BY ps.product_id DESC'

        # Execute the query
        cursor.execute(query, params)
        products = cursor.fetchall()

        # Fetch all categories again specifically for the filter dropdown
        cursor.execute('SELECT category_id, category_name FROM Category')
        all_categories = cursor.fetchall()

    conn.close()

    return render_template('admin_products.html', 
                           products=products, 
                           categories=categories, # For header
                           all_categories=all_categories, # For filter dropdown
                           search=search,
                           selected_category=category_id,
                           sort=sort)

@main.route('/admin/products/add', methods=['GET', 'POST'])
def admin_add_product():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        product_name = request.form.get('product_name')
        product_description = request.form.get('product_description')
        brand = request.form.get('brand')
        price = request.form.get('price')
        photo_filename = None
        if 'photo' in request.files:
            photo_file = request.files['photo']
            if photo_file.filename != '':
                # Secure the filename and save the file
                photo_filename = secure_filename(photo_file.filename)
                file_path = os.path.join(UPLOAD_FOLDER, photo_filename)
                photo_file.save(file_path)
                # Store the filename in the database
                photo = photo_filename # Store just the filename
            else:
                photo = None # No file uploaded
        else:
            photo = None # No file part in the request
        category_id = request.form.get('category_id')

        # Basic Validation
        if not all([product_name, brand, price, category_id]):
            flash('Please fill in all required fields (Name, Brand, Price, Category).', 'danger')
        else:
            try:
                price = float(price)
                category_id = int(category_id)

                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # Check if category_id exists (optional but good practice)
                    cursor.execute('SELECT category_id FROM Category WHERE category_id = %s', (category_id,))
                    if not cursor.fetchone():
                        flash('Invalid Category selected.', 'danger')
                    else:
                        # Insert new product
                        sql = 'INSERT INTO Product (product_name, product_description, brand, price, photo, category_id) VALUES (%s, %s, %s, %s, %s, %s)'
                        cursor.execute(sql, (product_name, product_description, brand, price, photo, category_id))
                        conn.commit()
                        flash('Product added successfully!', 'success')
                        return redirect(url_for('main.admin_products'))
                conn.close()
            except ValueError:
                flash('Invalid Price or Category ID.', 'danger')
            except Exception as e:
                flash(f'Error adding product: {e}', 'danger')

    # For GET request or POST failure, render the form
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT category_id, category_name FROM Category')
        categories = cursor.fetchall()
    conn.close()

    return render_template('admin_add_product.html', categories=categories)

@main.route('/admin/products/delete/<int:product_id>', methods=['POST'])
def admin_delete_product(product_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check for existing stock in any active warehouse for this product
            cursor.execute('SELECT SUM(ws.stock_quantity) as total_stock FROM Warehouse_Stock ws JOIN Warehouse w ON ws.warehouse_id = w.warehouse_id WHERE ws.product_id = %s AND w.is_active = TRUE', (product_id,))
            total_stock = cursor.fetchone()['total_stock'] or 0
            if total_stock > 0:
                flash(f'Cannot archive product: {total_stock} items of this product are still in stock in active warehouses. Please remove all stock first.', 'danger')
                return redirect(url_for('main.admin_products'))

            # If no dependencies, proceed with archiving the product
            cursor.execute('UPDATE Product SET is_active = FALSE WHERE product_id = %s', (product_id,))
            conn.commit()
        flash('Product has been archived.', 'success')
        return redirect(url_for('main.admin_products'))
    except Exception as e:
        flash(f'Error archiving product: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('main.admin_products'))
    finally:
        conn.close()

@main.route('/admin/products/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit_product(product_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            product_name = request.form.get('product_name')
            product_description = request.form.get('product_description')
            brand = request.form.get('brand')
            price = request.form.get('price')
            category_id = request.form.get('category_id')

            # Handle photo upload
            photo = None
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file.filename != '':
                    # Delete old photo if exists
                    cursor.execute('SELECT photo FROM Product WHERE product_id = %s', (product_id,))
                    old_photo = cursor.fetchone()
                    if old_photo and old_photo['photo']:
                        old_photo_path = os.path.join(UPLOAD_FOLDER, old_photo['photo'])
                        if os.path.exists(old_photo_path):
                            os.remove(old_photo_path)

                    # Save new photo
                    photo_filename = secure_filename(photo_file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, photo_filename)
                    photo_file.save(file_path)
                    photo = photo_filename

            try:
                price = float(price)
                category_id = int(category_id)

                # Update product
                if photo:
                    sql = '''UPDATE Product 
                            SET product_name = %s, product_description = %s, brand = %s, 
                                price = %s, category_id = %s, photo = %s 
                            WHERE product_id = %s'''
                    cursor.execute(sql, (product_name, product_description, brand, price, 
                                      category_id, photo, product_id))
                else:
                    sql = '''UPDATE Product 
                            SET product_name = %s, product_description = %s, brand = %s, 
                                price = %s, category_id = %s 
                            WHERE product_id = %s'''
                    cursor.execute(sql, (product_name, product_description, brand, price, 
                                      category_id, product_id))
                
                conn.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('main.admin_products'))
            except ValueError:
                flash('Invalid Price or Category ID.', 'danger')
            except Exception as e:
                flash(f'Error updating product: {e}', 'danger')

        # For GET request, fetch product and categories
        cursor.execute('SELECT * FROM Product WHERE product_id = %s AND is_active = TRUE', (product_id,))
        product = cursor.fetchone()
        cursor.execute('SELECT category_id, category_name FROM Category')
        categories = cursor.fetchall()
    conn.close()

    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('main.admin_products'))

    return render_template('admin_edit_product.html', product=product, categories=categories)

# Admin Categories (admin and staff)
@main.route('/admin/categories')
def admin_categories():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    search = request.args.get('search', '').strip().lower()

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories_for_header = cursor.fetchall()

        # Build the query for categories table
        query = 'SELECT * FROM Category WHERE is_active = TRUE'
        params = []

        if search:
            query += ' AND (LOWER(category_name) LIKE %s OR LOWER(category_description) LIKE %s)'
            search_param = f'%{search}%'
            params.extend([search_param, search_param])

        query += ' ORDER BY category_name ASC'

        cursor.execute(query, params)
        categories = cursor.fetchall()
    conn.close()
    return render_template('admin_categories.html', categories=categories, search=search, categories_for_header=categories_for_header)

@main.route('/admin/categories/add', methods=['GET', 'POST'])
def admin_add_category():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        category_name = request.form.get('category_name')
        category_description = request.form.get('category_description')

        if not category_name:
            flash('Category name is required.', 'danger')
        else:
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    # Fetch categories for header
                    cursor.execute('SELECT * FROM Category')
                    categories = cursor.fetchall()

                    # Check if category name already exists
                    cursor.execute('SELECT category_id FROM Category WHERE category_name = %s', (category_name,))
                    if cursor.fetchone():
                        flash('A category with this name already exists.', 'danger')
                        conn.close()
                        return render_template('admin_add_category.html', categories=categories)
                    else:
                        # Insert new category
                        cursor.execute('INSERT INTO Category (category_name, category_description) VALUES (%s, %s)',
                                     (category_name, category_description))
                        conn.commit()
                        flash('Category added successfully!', 'success')
                        return redirect(url_for('main.admin_categories'))
                conn.close()
            except Exception as e:
                flash(f'Error adding category: {e}', 'danger')

    # For GET request or POST failure, render the form
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()

    return render_template('admin_add_category.html', categories=categories)

@main.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
def admin_edit_category(category_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            category_name = request.form.get('category_name')
            category_description = request.form.get('category_description')

            if not category_name:
                flash('Category name is required.', 'danger')
            else:
                try:
                    # Check if category name already exists (excluding current category)
                    cursor.execute('SELECT category_id FROM Category WHERE category_name = %s AND category_id != %s',
                                 (category_name, category_id))
                    if cursor.fetchone():
                        flash('A category with this name already exists.', 'danger')
                    else:
                        # Update category
                        cursor.execute('''UPDATE Category 
                                        SET category_name = %s, category_description = %s 
                                        WHERE category_id = %s''',
                                     (category_name, category_description, category_id))
                        conn.commit()
                        flash('Category updated successfully!', 'success')
                        return redirect(url_for('main.admin_categories'))
                except Exception as e:
                    flash(f'Error updating category: {e}', 'danger')

        # For GET request, fetch category
        cursor.execute('SELECT * FROM Category WHERE category_id = %s', (category_id,))
        category = cursor.fetchone()
    conn.close()

    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('main.admin_categories'))

    return render_template('admin_edit_category.html', category=category)

@main.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
def admin_delete_category(category_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check for active products in this category
            cursor.execute('SELECT COUNT(*) AS active_product_count FROM Product WHERE category_id = %s AND is_active = TRUE', (category_id,))
            active_product_count = cursor.fetchone()['active_product_count']
            if active_product_count > 0:
                flash(f'Cannot archive category: This category has {active_product_count} active products. Please archive all products in this category first.', 'danger')
                return redirect(url_for('main.admin_categories'))

            # Archive all products in this category (already inactive by the above check or user action)
            cursor.execute('UPDATE Product SET is_active = FALSE WHERE category_id = %s', (category_id,))
            # Archive the category
            cursor.execute('UPDATE Category SET is_active = FALSE WHERE category_id = %s', (category_id,))
            conn.commit()
        flash('Category and its products have been archived.', 'success')
        return redirect(url_for('main.admin_categories'))
    except Exception as e:
        flash(f'Error archiving category: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('main.admin_categories'))
    finally:
        conn.close()

# Admin Users (admin and staff)
@main.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    search = request.args.get('search', '').lower()
    role_filter = request.args.get('role', '')

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()

        # Base query
        query = '''
            SELECT 
                * 
            FROM 
                Person
            WHERE
                is_active = TRUE
        '''
        params = []
        
        # Add search and role filters
        conditions = []
        if search:
            # Modified search to look within first name, last name, or combined full name (case-insensitive)
            conditions.append('''
                (
                    LOWER(first_name) LIKE %s OR 
                    LOWER(last_name) LIKE %s OR 
                    LOWER(CONCAT(first_name, \' \', last_name)) LIKE %s OR 
                    LOWER(CONCAT(last_name, \' \', first_name)) LIKE %s
                )
            ''')
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param, search_param])
        if role_filter:
            conditions.append('role = %s')
            params.append(role_filter)
        
        if conditions:
            query += ' AND ' + ' AND '.join(conditions)

        # Add ORDER BY for consistent results
        query += ' ORDER BY last_name, first_name'
        
        cursor.execute(query, params)
        users = cursor.fetchall()
    conn.close()

    return render_template('admin_users.html', users=users, categories=categories)

@main.route('/admin/users/add', methods=['GET', 'POST'])
def admin_add_user():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('You must be an admin to access this page.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role') # Get the role from the form

        # Basic validation
        if not all([first_name, last_name, email, password, confirm_password, role]):
            flash('Please fill in all fields.', 'danger')
            return render_template('admin_add_user.html')
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('admin_add_user.html')
        if not is_strong_password(password):
            flash('Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.', 'danger')
            return render_template('admin_add_user.html')
        # Email format validation
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            flash('Invalid email format.', 'danger')
            return render_template('admin_add_user.html')
        
        # Validate the selected role
        if role not in ['admin', 'staff']:
            flash('Invalid role selected.', 'danger')
            return render_template('admin_add_user.html')

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
            categories = cursor.fetchall()
            cursor.execute('SELECT * FROM Person WHERE email = %s', (email,))
            if cursor.fetchone():
                flash('Email already registered.', 'danger')
                conn.close()
                return render_template('admin_add_user.html', categories=categories)
            # Hash password before storing
            hashed_password = generate_password_hash(password).decode('utf-8')
            cursor.execute('INSERT INTO Person (first_name, last_name, email, passcode, role) VALUES (%s, %s, %s, %s, %s)',
                         (first_name, last_name, email, hashed_password, role)) # Use the selected role
            conn.commit()
        conn.close()
        flash(f'{role.capitalize()} user added successfully!', 'success') # Dynamic flash message
        return redirect(url_for('main.admin_users'))
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()
    return render_template('admin_add_user.html', categories=categories)

@main.route('/admin/users/<int:user_id>')
def admin_user_details(user_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()

        # Get user details
        cursor.execute('SELECT * FROM Person WHERE person_id = %s AND is_active = TRUE', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            flash('User not found.', 'danger')
            conn.close()
            return redirect(url_for('main.admin_users'))
        
        # Get user's addresses
        cursor.execute('''
            SELECT 
                * 
            FROM 
                Address 
            WHERE 
                person_id = %s
        ''', (user_id,))
        addresses = cursor.fetchall()
        
        # Get user's orders
        cursor.execute('''
            SELECT 
                * 
            FROM 
                Orders 
            WHERE 
                person_id = %s
            ORDER BY 
                order_date DESC
        ''', (user_id,))
        orders = cursor.fetchall()
    conn.close()

    return render_template('admin_user_details.html', user=user, addresses=addresses, orders=orders, categories=categories)

@main.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def admin_delete_user(user_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if user is admin
            cursor.execute('SELECT role FROM Person WHERE person_id = %s', (user_id,))
            user = cursor.fetchone()
            if not user:
                flash('User not found.', 'danger')
                return redirect(url_for('main.admin_users'))

            if user['role'] == 'admin':
                flash('Cannot archive admin users.', 'danger')
                return redirect(url_for('main.admin_users'))

            # Check for existing orders for this user
            cursor.execute('SELECT COUNT(*) AS order_count FROM Orders WHERE person_id = %s', (user_id,))
            order_count = cursor.fetchone()['order_count']
            if order_count > 0:
                flash(f'Cannot archive user: This user has {order_count} existing orders. Please ensure there are no dependencies before archiving.', 'danger')
                return redirect(url_for('main.admin_user_details', user_id=user_id))

            cursor.execute('UPDATE Person SET is_active = FALSE WHERE person_id = %s', (user_id,))
            conn.commit()
        flash('User has been archived.', 'success')
        return redirect(url_for('main.admin_users'))
    except Exception as e:
        flash(f'Error archiving user: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('main.admin_users'))
    finally:
        conn.close()

# Admin Orders (admin and staff)
@main.route('/admin/orders')
def admin_orders():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))
    
    # Get search parameter for customer name
    search_customer = request.args.get('customer_search', '').strip().lower()
    # Get status filter parameter
    status_filter = request.args.get('status_filter', '').strip()
    # Get order ID filter parameter
    order_id_filter = request.args.get('order_id_filter', '').strip()
    # Get order date range filter parameters
    start_date_filter = request.args.get('start_date_filter', '').strip()
    end_date_filter = request.args.get('end_date_filter', '').strip()

    # Validate order ID filter
    if order_id_filter:
        try:
            order_id_filter_int = int(order_id_filter)
            if order_id_filter_int < 0:
                flash('Order ID cannot be a negative number.', 'danger')
                return redirect(url_for('main.admin_orders'))
        except ValueError:
            flash('Invalid Order ID. Please enter a valid number.', 'danger')
            return redirect(url_for('main.admin_orders'))

    # Validate date filters
    today = date.today()

    if start_date_filter:
        try:
            start_date_dt = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
            if start_date_dt > today:
                flash('Start date cannot be in the future.', 'danger')
                return redirect(url_for('main.admin_orders'))
        except ValueError:
            flash('Invalid start date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('main.admin_orders'))

    if end_date_filter:
        try:
            end_date_dt = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
            if end_date_dt > today:
                flash('End date cannot be in the future.', 'danger')
                return redirect(url_for('main.admin_orders'))
        except ValueError:
            flash('Invalid end date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('main.admin_orders'))

    if start_date_filter and end_date_filter:
        try:
            # Re-parse dates if they were parsed previously to ensure consistent comparison
            start_date_dt = datetime.strptime(start_date_filter, '%Y-%m-%d').date()
            end_date_dt = datetime.strptime(end_date_filter, '%Y-%m-%d').date()
            if start_date_dt > end_date_dt:
                flash('Start date cannot be after end date.', 'danger')
                return redirect(url_for('main.admin_orders'))
        except ValueError: # This should ideally be caught by individual checks, but as a fallback
            flash('Invalid date format in range. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('main.admin_orders'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()

        # Build the complete query with all filtering and sorting in SQL
        query = '''
            WITH order_stats AS (
                SELECT 
                    o.order_id,
                    o.person_id,
                    o.order_date,
                    o.order_status,
                    o.shipping_cost,
                    o.address_id,
                    p.first_name,
                    p.last_name,
                    p.role,
                    CASE 
                        WHEN p.role = 'admin' THEN 'Admin Order'
                        WHEN p.role = 'staff' THEN 'Staff Order'
                        ELSE 'Typical Customer'
                    END as order_type,
                    CONCAT(p.first_name, ' ', p.last_name) as full_name,
                    (
                        SELECT 
                            CASE 
                                WHEN SUM(ol.quantity * p2.price) IS NULL THEN 0 
                                ELSE SUM(ol.quantity * p2.price) 
                            END
                        FROM 
                            Order_Line ol 
                        JOIN 
                            Product p2 ON ol.product_id = p2.product_id 
                        WHERE 
                            ol.order_id = o.order_id AND p2.is_active = TRUE
                    ) AS items_subtotal
                FROM 
                    Orders o
                JOIN 
                    Person p ON o.person_id = p.person_id
                WHERE
                    p.is_active = TRUE
        '''
        params = []

        # Add search condition for customer name
        if search_customer:
            query += ' AND (LOWER(p.first_name) LIKE %s OR LOWER(p.last_name) LIKE %s OR LOWER(CONCAT(p.first_name, \' \', p.last_name)) LIKE %s)'
            search_param = f'%{search_customer}%'
            params.extend([search_param, search_param, search_param])

        # Add status filter condition
        if status_filter:
            query += ' AND o.order_status = %s'
            params.append(status_filter)
            
        # Add order ID filter condition
        if order_id_filter:
            query += ' AND o.order_id = %s'
            params.append(order_id_filter)
            
        # Add order date range filter conditions
        if start_date_filter:
            query += ' AND o.order_date >= %s'
            params.append(start_date_filter)
        if end_date_filter:
            query += ' AND o.order_date <= %s'
            params.append(end_date_filter)

        # Complete the CTE
        query += '''
            )
            SELECT 
                os.*,
                (os.items_subtotal + os.shipping_cost) as total_amount
            FROM 
                order_stats os
            ORDER BY 
                os.order_date DESC
        '''

        # Execute the query
        cursor.execute(query, params)
        orders = cursor.fetchall()
        
        # Update order statuses if needed
        today = datetime.now().date()
        for order in orders:
            update_order_status_if_needed(order, cursor, today)
        conn.commit()

    conn.close()

    return render_template('admin_orders.html', 
                           orders=orders, 
                           categories=categories, 
                           search_customer=search_customer, 
                           status_filter=status_filter,
                           order_id_filter=order_id_filter,
                           start_date_filter=start_date_filter,
                           end_date_filter=end_date_filter)

# Admin Warehouses (admin and staff)
@main.route('/admin/warehouses')
def admin_warehouses():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    search = request.args.get('search', '').lower()

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()

        # Base query
        query = '''
            SELECT 
                * 
            FROM 
                Warehouse
            WHERE
                is_active = TRUE
        '''
        params = []
        conditions = []

        # Add search filter if a search term is provided (applies to name, street, and city)
        if search:
            conditions.append('(LOWER(location_name) LIKE %s OR LOWER(street_address) LIKE %s OR LOWER(city) LIKE %s)')
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])

        if conditions:
            query += ' AND ' + ' AND '.join(conditions)

        # Add ORDER BY for consistent results
        query += ' ORDER BY warehouse_id ASC'

        cursor.execute(query, params)
        warehouses = cursor.fetchall()
    conn.close()

    return render_template('admin_warehouses.html', 
                           warehouses=warehouses, 
                           search=search, 
                           categories=categories)

@main.route('/admin/warehouses/add', methods=['GET', 'POST'])
def admin_add_warehouse():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    if request.method == 'POST':
        location_name = request.form.get('location_name')
        street_address = request.form.get('street_address')
        city = request.form.get('city')

        if not all([location_name, street_address, city]):
            flash('Please fill in all fields.', 'danger')
            return render_template('admin_add_warehouse.html')

        if city not in ALLOWED_CITIES:
            flash('Invalid city selected.', 'danger')
            conn = get_db_connection() # Re-establish connection to fetch categories for template
            with conn.cursor() as cursor:
                cursor.execute('SELECT * FROM Category WHERE is_active = TRUE')
                categories = cursor.fetchall()
            conn.close()
            return render_template('admin_add_warehouse.html', categories=categories, allowed_cities=ALLOWED_CITIES)

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Check if location name already exists (optional but good practice)
                cursor.execute('SELECT warehouse_id FROM Warehouse WHERE location_name = %s AND is_active = TRUE', (location_name,))
                if cursor.fetchone():
                    flash('A warehouse with this location name already exists.', 'danger')
                    conn.close()
                    return render_template('admin_add_warehouse.html')

                cursor.execute('INSERT INTO Warehouse (location_name, street_address, city) VALUES (%s, %s, %s)',
                               (location_name, street_address, city))
                conn.commit()
            flash('Warehouse added successfully!', 'success')
            return redirect(url_for('main.admin_warehouses'))
        except Exception as e:
            flash(f'Error adding warehouse: {e}', 'danger')
        finally:
            conn.close()

    # For GET request or POST failure, render the form
    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category WHERE is_active = TRUE') # Fetch all categories for modal
        categories = cursor.fetchall()

    return render_template('admin_add_warehouse.html', categories=categories, allowed_cities=ALLOWED_CITIES)

@main.route('/admin/warehouses/<int:warehouse_id>')
def admin_warehouse_details(warehouse_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category WHERE is_active = TRUE') # Fetch all categories for modal
        categories = cursor.fetchall()

        # Get warehouse details
        cursor.execute('SELECT * FROM Warehouse WHERE warehouse_id = %s AND is_active = TRUE', (warehouse_id,))
        warehouse = cursor.fetchone()

        if not warehouse:
            flash('Warehouse not found or is inactive.', 'danger')
            conn.close()
            return redirect(url_for('main.admin_warehouses'))
        
        # Get products in this warehouse with their stock quantity
        cursor.execute('''
            SELECT 
                p.product_id, 
                p.product_name, 
                p.price, 
                ws.stock_quantity
            FROM 
                Warehouse_Stock ws
            JOIN 
                Product p 
                ON ws.product_id = p.product_id
            WHERE 
                ws.warehouse_id = %s AND p.is_active = TRUE
            ORDER BY 
                p.product_name
        ''', (warehouse_id,))
        products_in_warehouse = cursor.fetchall()

        # Get products NOT in this warehouse (for adding stock) - only active products
        cursor.execute('''
            SELECT 
                p.product_id, 
                p.product_name,
                p.brand
            FROM 
                Product p
            WHERE 
                p.is_active = TRUE
            ORDER BY 
                p.product_name
        ''')
        available_products = cursor.fetchall()
        
        # Get suppliers associated with products in this warehouse (only active suppliers)
        cursor.execute('''
            SELECT DISTINCT 
                s.supplier_id, 
                s.supplier_name
            FROM 
                Supplier s
            JOIN 
                Supplier_Product sp ON s.supplier_id = sp.supplier_id
            JOIN 
                Product p ON sp.product_id = p.product_id
            JOIN
                Warehouse_Stock ws ON p.product_id = ws.product_id
            WHERE 
                ws.warehouse_id = %s AND s.is_active = TRUE
            ORDER BY 
                s.supplier_name
        ''', (warehouse_id,))
        suppliers_for_warehouse = cursor.fetchall()

    conn.close()

    return render_template('admin_warehouse_details.html', 
                           warehouse=warehouse, 
                           products_in_warehouse=products_in_warehouse,
                           available_products=available_products,
                           suppliers_for_warehouse=suppliers_for_warehouse,
                           categories=categories,
                           stock_items=products_in_warehouse)

@main.route('/admin/warehouses/<int:warehouse_id>/delete', methods=['POST'])
def admin_delete_warehouse(warehouse_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check for existing stock in this warehouse
            cursor.execute('SELECT SUM(stock_quantity) as total_stock_in_warehouse FROM Warehouse_Stock WHERE warehouse_id = %s', (warehouse_id,))
            stock_in_warehouse = cursor.fetchone()['total_stock_in_warehouse'] or 0

            if stock_in_warehouse > 0:
                flash(f'Cannot archive warehouse: {stock_in_warehouse} stock items still exist in this warehouse. Please remove all stock first.', 'danger')
                return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

            # If no stock, proceed with archiving the warehouse
            cursor.execute('UPDATE Warehouse SET is_active = FALSE WHERE warehouse_id = %s', (warehouse_id,))
            conn.commit()
        flash('Warehouse has been archived.', 'success')
        return redirect(url_for('main.admin_warehouses'))
    except Exception as e:
        flash(f'Error archiving warehouse: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('main.admin_warehouses'))
    finally:
        conn.close()

@main.route('/admin/warehouses/<int:warehouse_id>/edit', methods=['GET', 'POST'])
def admin_edit_warehouse(warehouse_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()

    if request.method == 'POST':
        location_name = request.form.get('location_name')
        street_address = request.form.get('street_address')
        city = request.form.get('city')

        if not all([location_name, street_address, city]):
            flash('Please fill in all fields.', 'danger')
        else:
            try:
                with conn.cursor() as cursor:
                    # Check if location name already exists for another warehouse (optional)
                    cursor.execute('SELECT warehouse_id FROM Warehouse WHERE location_name = %s AND warehouse_id != %s', (location_name, warehouse_id))
                    if cursor.fetchone():
                        flash('A warehouse with this location name already exists.', 'danger')
                    else:
                        cursor.execute('UPDATE Warehouse SET location_name = %s, street_address = %s, city = %s WHERE warehouse_id = %s',
                                     (location_name, street_address, city, warehouse_id))
                        conn.commit()
                        flash('Warehouse updated successfully!', 'success')
                        return redirect(url_for('main.admin_warehouses'))
            except Exception as e:
                flash(f'Error updating warehouse: {e}', 'danger')

    # For GET request or POST failure, fetch warehouse data to pre-fill the form
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()

        cursor.execute('SELECT * FROM Warehouse WHERE warehouse_id = %s', (warehouse_id,))
        warehouse = cursor.fetchone()

    conn.close()

    if not warehouse:
        flash('Warehouse not found.', 'danger')
        return redirect(url_for('main.admin_warehouses'))

    return render_template('admin_edit_warehouse.html', warehouse=warehouse, categories=categories, allowed_cities=ALLOWED_CITIES)

@main.route('/admin/warehouses/<int:warehouse_id>/add_stock', methods=['POST'])
def admin_add_stock(warehouse_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    product_id = request.form.get('product_id')
    stock_quantity = request.form.get('stock_quantity')
    conn = None
    if not all([product_id, stock_quantity]):
        flash('Please select a product and enter a quantity.', 'danger')
        return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

    try:
        product_id = int(product_id)
        stock_quantity = int(stock_quantity)
        if stock_quantity < 1:
            flash('Quantity must be at least 1.', 'danger')
            return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if the product is already in stock for this warehouse
            cursor.execute('SELECT stock_quantity FROM Warehouse_Stock WHERE warehouse_id = %s AND product_id = %s', (warehouse_id, product_id))
            existing_stock = cursor.fetchone()

            if existing_stock:
                # If exists, update the quantity
                new_quantity = existing_stock['stock_quantity'] + stock_quantity
                cursor.execute('UPDATE Warehouse_Stock SET stock_quantity = %s WHERE warehouse_id = %s AND product_id = %s', (new_quantity, warehouse_id, product_id))
                flash(f'Updated stock for Product ID {product_id}. New quantity: {new_quantity}', 'success')
            else:
                # If not exists, insert new stock record
                cursor.execute('INSERT INTO Warehouse_Stock (warehouse_id, product_id, stock_quantity) VALUES (%s, %s, %s)', (warehouse_id, product_id, stock_quantity))
                flash(f'Added Product ID {product_id} to stock.', 'success')

            conn.commit()
    except ValueError:
        flash('Invalid product or quantity.', 'danger')
    except Exception as e:
        flash(f'Error managing stock: {e}', 'danger')
    finally:
        if conn:
            conn.close()
    return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

@main.route('/admin/warehouses/<int:warehouse_id>/update_stock/<int:product_id>', methods=['POST'])
def admin_update_stock(warehouse_id, product_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    stock_quantity = request.form.get('stock_quantity')

    if stock_quantity is None:
        flash('Quantity is required.', 'danger')
        return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

    try:
        stock_quantity = int(stock_quantity)
        if stock_quantity < 0:
            flash('Quantity cannot be negative.', 'danger')
            return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

        conn = get_db_connection()
        with conn.cursor() as cursor:
            if stock_quantity == 0:
                # If quantity is 0, remove the stock item
                cursor.execute('DELETE FROM Warehouse_Stock WHERE warehouse_id = %s AND product_id = %s', (warehouse_id, product_id))
                flash(f'Removed Product ID {product_id} from stock.', 'success')
            else:
                # Otherwise, update the quantity
                cursor.execute('UPDATE Warehouse_Stock SET stock_quantity = %s WHERE warehouse_id = %s AND product_id = %s', (stock_quantity, warehouse_id, product_id))
                flash(f'Updated stock for Product ID {product_id}. New quantity: {stock_quantity}', 'success')

            conn.commit()
    except ValueError:
        flash('Invalid quantity.', 'danger')
    except Exception as e:
        flash(f'Error updating stock: {e}', 'danger')
    finally:
        if conn:
            conn.close()

    return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

@main.route('/admin/warehouses/<int:warehouse_id>/remove_stock/<int:product_id>', methods=['POST'])
def admin_remove_stock(warehouse_id, product_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM Warehouse_Stock WHERE warehouse_id = %s AND product_id = %s', (warehouse_id, product_id))
            conn.commit()
        flash(f'Removed Product ID {product_id} from stock.', 'success')
    except Exception as e:
        flash(f'Error removing stock: {e}', 'danger')
        conn.rollback()
    finally:
        conn.close()

    return redirect(url_for('main.admin_warehouse_details', warehouse_id=warehouse_id))

############################################################################################################
# Utility / Context Processor
############################################################################################################
@main.app_context_processor
def inject_cart():
    cart = session.get('cart', {})
    cart_items = []
    total = 0
    if cart:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            product_ids = list(map(int, cart.keys()))
            if product_ids:
                format_strings = ','.join(['%s'] * len(product_ids))
                cursor.execute(f"SELECT * FROM Product WHERE product_id IN ({format_strings})", tuple(product_ids))
                products = cursor.fetchall()
            else:
                products = []
        conn.close()
        for product in products:
            pid = str(product['product_id'])
            quantity = cart[pid]
            subtotal = product['price'] * quantity
            total += subtotal
            cart_items.append({
                'product': product,
                'quantity': quantity,
                'subtotal': subtotal
            })
    return dict(cart_items=cart_items, total=total)

# --- Helper for order status update ---
def update_order_status_if_needed(order, cursor, today=None):
    if not order:
        return False
    if not today:
        today = datetime.now().date()
    order_date = order['order_date']
    if isinstance(order_date, str):
        order_date_dt = datetime.strptime(order_date, '%Y-%m-%d')
    else:
        order_date_dt = order_date
    order_date_val = order_date_dt.date() if isinstance(order_date_dt, datetime) else order_date_dt
    days_since_order = (today - order_date_val).days
    shipped_day = order.get('shipped_day') or 2
    expected_delivery_day = order.get('expected_delivery_day') or 4
    status_changed = False
    if order['order_status'] != 'Delivered':
        if days_since_order >= expected_delivery_day:
            print(f"Updating order {order['order_id']} to Delivered. Days since order: {days_since_order}, Expected delivery day: {expected_delivery_day}")
            cursor.execute('UPDATE Orders SET order_status = %s, delivery_date = %s WHERE order_id = %s',
                           ('Delivered', today.strftime('%Y-%m-%d'), order['order_id']))
            order['order_status'] = 'Delivered'
            order['delivery_date'] = today.strftime('%Y-%m-%d')
            # Update all order line states to Delivered
            print(f"Updating order line states for order {order['order_id']} to Delivered")
            cursor.execute('UPDATE Order_Line SET order_line_states = %s WHERE order_id = %s',
                           ('Delivered', order['order_id']))
            status_changed = True
        elif days_since_order >= shipped_day and order['order_status'] == 'Processing':
            print(f"Updating order {order['order_id']} to Shipped. Days since order: {days_since_order}, Shipped day: {shipped_day}")
            cursor.execute('UPDATE Orders SET order_status = %s, shipped_date = %s WHERE order_id = %s',
                           ('Shipped', today.strftime('%Y-%m-%d'), order['order_id']))
            order['order_status'] = 'Shipped'
            order['shipped_date'] = today.strftime('%Y-%m-%d')
            # Update all order line states to Shipped
            print(f"Updating order line states for order {order['order_id']} to Shipped")
            cursor.execute('UPDATE Order_Line SET order_line_states = %s WHERE order_id = %s',
                           ('Shipped', order['order_id']))
            status_changed = True
    return status_changed

############################################################################################################
# Admin Suppliers Section
############################################################################################################

# Admin Suppliers (admin and staff)
@main.route('/admin/suppliers')
def admin_suppliers():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    search = request.args.get('search', '').lower()
    # New filter parameters
    supplier_id_filter = request.args.get('supplier_id_filter', '').strip()
    phone_number_filter = request.args.get('phone_number_filter', '').strip()

    # Validate supplier ID filter
    if supplier_id_filter:
        try:
            supplier_id_filter_int = int(supplier_id_filter)
            if supplier_id_filter_int <= 0:
                flash('Supplier ID must be a positive number.', 'danger')
                return redirect(url_for('main.admin_suppliers'))
        except ValueError:
            flash('Invalid Supplier ID. Please enter a valid number.', 'danger')
            return redirect(url_for('main.admin_suppliers'))

    # Validate phone number filter (ensure it's not just letters)
    if phone_number_filter and any(char.isalpha() for char in phone_number_filter):
        flash('Phone number filter cannot contain any letters.', 'danger')
        return redirect(url_for('main.admin_suppliers'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()

        # Fetch all suppliers and the count of products they supply
        # Start with the base query
        base_query = '''
            SELECT
                s.*,
                COUNT(sp.product_id) AS product_count
            FROM
                Supplier s
            LEFT JOIN
                Supplier_Product sp ON s.supplier_id = sp.supplier_id
        WHERE
            s.is_active = TRUE
        '''

        conditions = []
        params = []

        if search:
            # Split the search term by spaces and join with % for flexible matching
            search_terms = search.split()
            # Construct the pattern like %term1%term2%
            flexible_search_pattern = '%' + '%'.join(search_terms) + '%'

            conditions.append('(LOWER(s.supplier_name) LIKE %s OR LOWER(s.email) LIKE %s)')
            params.extend([flexible_search_pattern, flexible_search_pattern])
            
        if supplier_id_filter:
            conditions.append('s.supplier_id = %s')
            params.append(supplier_id_filter)
            
        if phone_number_filter:
            conditions.append('s.phone_number LIKE %s')
            params.append(f'%{phone_number_filter}%')

        # Build the final query
        if conditions:
            query = base_query + ' AND ' + ' AND '.join(conditions) + ' GROUP BY s.supplier_id ORDER BY supplier_id ASC'
        else:
            query = base_query + ' GROUP BY s.supplier_id ORDER BY supplier_id ASC'

        print(f"Executing query: {query}")
        print(f"With parameters: {params}")

        cursor.execute(query, tuple(params))
        suppliers = cursor.fetchall()

    conn.close()

    return render_template('admin_suppliers.html', suppliers=suppliers, categories=categories,
                           search=search,
                           supplier_id_filter=supplier_id_filter,
                           phone_number_filter=phone_number_filter)

# Admin Add Supplier (admin and staff)
@main.route('/admin/suppliers/add', methods=['GET', 'POST'])
def admin_add_supplier():
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')

        if not supplier_name:
            flash('Supplier name is required.', 'danger')
        else:
            try:
                with conn.cursor() as cursor:
                    # Check if supplier name already exists (optional but good practice)
                    cursor.execute('SELECT supplier_id FROM Supplier WHERE supplier_name = %s', (supplier_name,))
                    if cursor.fetchone():
                        flash('A supplier with this name already exists.', 'danger')
                    else:
                        cursor.execute('INSERT INTO Supplier (supplier_name, phone_number, email) VALUES (%s, %s, %s)',
                                     (supplier_name, phone_number, email))
                        conn.commit()
                        flash('Supplier added successfully!', 'success')
                        return redirect(url_for('main.admin_suppliers'))
            except Exception as e:
                flash(f'Error adding supplier: {e}', 'danger')
            finally:
                conn.close()

    # For GET request or POST failure, render the form
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()
    conn.close()

    return render_template('admin_add_supplier.html', categories=categories)

# Admin Edit Supplier (admin and staff)
@main.route('/admin/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
def admin_edit_supplier(supplier_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = get_db_connection()
    if request.method == 'POST':
        supplier_name = request.form.get('supplier_name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')

        if not supplier_name:
            flash('Supplier name is required.', 'danger')
        else:
            try:
                with conn.cursor() as cursor:
                    # Check if supplier name already exists for another supplier (optional)
                    cursor.execute('SELECT supplier_id FROM Supplier WHERE supplier_name = %s AND supplier_id != %s', (supplier_name, supplier_id))
                    if cursor.fetchone():
                        flash('A supplier with this name already exists.', 'danger')
                    else:
                        cursor.execute('UPDATE Supplier SET supplier_name = %s, phone_number = %s, email = %s WHERE supplier_id = %s',
                                     (supplier_name, phone_number, email, supplier_id))
                        conn.commit()
                        flash('Supplier updated successfully!', 'success')
                        return redirect(url_for('main.admin_suppliers'))
            except Exception as e:
                flash(f'Error updating supplier: {e}', 'danger')
            finally:
                conn.close()

    # For GET request or POST failure, fetch supplier data to pre-fill the form
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category') # Fetch all categories for modal
        categories = cursor.fetchall()
        
        # Fetch supplier details
        cursor.execute('SELECT * FROM Supplier WHERE supplier_id = %s', (supplier_id,))
        supplier = cursor.fetchone()

        # Fetch products supplied by this supplier
        cursor.execute('''
            SELECT 
                p.product_id, 
                p.product_name, 
                p.brand
            FROM 
                Product p
            JOIN 
                Supplier_Product sp 
                ON p.product_id = sp.product_id
            WHERE 
                sp.supplier_id = %s
            ORDER BY
                p.product_name ASC
        ''', (supplier_id,))
        supplied_products = cursor.fetchall()

        # Fetch all products to allow linking new ones
        cursor.execute('''
            SELECT 
                product_id, 
                product_name, 
                brand
            FROM 
                Product
            ORDER BY
                product_name ASC
        ''')
        all_products = cursor.fetchall()

    conn.close()

    if not supplier:
        flash('Supplier not found.', 'danger')
        return redirect(url_for('main.admin_suppliers'))

    return render_template('admin_edit_supplier.html', 
                           supplier=supplier, 
                           categories=categories,
                           supplied_products=supplied_products,
                           all_products=all_products)

# Admin Delete Supplier (admin only - added extra check)
@main.route('/admin/suppliers/delete/<int:supplier_id>', methods=['POST'])
def admin_delete_supplier(supplier_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check for associated products
            cursor.execute('SELECT COUNT(*) AS product_count FROM Supplier_Product WHERE supplier_id = %s', (supplier_id,))
            product_count = cursor.fetchone()['product_count']
            if product_count > 0:
                flash(f'Cannot archive supplier: This supplier is associated with {product_count} products. Please unlink all products first.', 'danger')
                return redirect(url_for('main.admin_edit_supplier', supplier_id=supplier_id))

            cursor.execute('UPDATE Supplier SET is_active = FALSE WHERE supplier_id = %s', (supplier_id,))
            conn.commit()
        flash('Supplier has been archived.', 'success')
        return redirect(url_for('main.admin_suppliers'))
    except Exception as e:
        flash(f'Error archiving supplier: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('main.admin_suppliers'))
    finally:
        conn.close()

# Admin Add Product to Supplier (admin and staff)
@main.route('/admin/suppliers/<int:supplier_id>/add_product', methods=['POST'])
def admin_add_product_to_supplier(supplier_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    product_id = request.form.get('product_id')
    conn = None
    if not product_id:
        flash('Please select a product.', 'danger')
        return redirect(url_for('main.admin_edit_supplier', supplier_id=supplier_id))

    try:
        product_id = int(product_id)
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check if the link already exists
            cursor.execute('SELECT COUNT(*) as cnt FROM Supplier_Product WHERE supplier_id = %s AND product_id = %s', (supplier_id, product_id))
            if cursor.fetchone()['cnt'] > 0:
                flash('This product is already linked to this supplier.', 'warning')
            else:
                cursor.execute('INSERT INTO Supplier_Product (supplier_id, product_id) VALUES (%s, %s)', (supplier_id, product_id))
                conn.commit()
                flash('Product linked to supplier successfully!', 'success')
    except ValueError:
        flash('Invalid product ID.', 'danger')
    except Exception as e:
        flash(f'Error linking product: {e}', 'danger')
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    return redirect(url_for('main.admin_edit_supplier', supplier_id=supplier_id))

# Admin Remove Product from Supplier (admin and staff)
@main.route('/admin/suppliers/<int:supplier_id>/remove_product/<int:product_id>', methods=['POST'])
def admin_remove_product_from_supplier(supplier_id, product_id):
    if 'user_id' not in session or session.get('user_role') not in ['admin', 'staff']:
        flash('You must be an admin or staff to access this page.', 'danger')
        return redirect(url_for('main.home'))

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute('DELETE FROM Supplier_Product WHERE supplier_id = %s AND product_id = %s', (supplier_id, product_id))
            conn.commit()
            flash('Product unlinked from supplier successfully!', 'success')
    except Exception as e:
        flash(f'Error unlinking product: {e}', 'danger')
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    return redirect(url_for('main.admin_edit_supplier', supplier_id=supplier_id))

# Admin Archives (admin only)
@main.route('/admin/archives')
def admin_archives():
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('You must be an admin to access this page.', 'danger')
        return redirect(url_for('main.home'))

    search = request.args.get('search', '').lower()

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # Fetch categories for header/modal
        cursor.execute('SELECT * FROM Category')
        categories = cursor.fetchall()

        # Fetch archived users
        user_query = 'SELECT * FROM Person WHERE is_active = FALSE'
        user_params = []
        if search:
            user_query += ' AND (LOWER(first_name) LIKE %s OR LOWER(last_name) LIKE %s OR LOWER(email) LIKE %s)'
            search_param = f'%{search}%'
            user_params.extend([search_param, search_param, search_param])
        cursor.execute(user_query, user_params)
        archived_users = cursor.fetchall()

        # Fetch archived products with category names
        product_query = '''
            SELECT p.*, c.category_name 
            FROM Product p 
            JOIN Category c ON p.category_id = c.category_id 
            WHERE p.is_active = FALSE
        '''
        product_params = []
        if search:
            product_query += ' AND (LOWER(p.product_name) LIKE %s OR LOWER(p.brand) LIKE %s OR LOWER(c.category_name) LIKE %s)'
            search_param = f'%{search}%'
            product_params.extend([search_param, search_param, search_param])
        cursor.execute(product_query, product_params)
        archived_products = cursor.fetchall()

        # Fetch archived categories
        category_query = 'SELECT * FROM Category WHERE is_active = FALSE'
        category_params = []
        if search:
            category_query += ' AND (LOWER(category_name) LIKE %s OR LOWER(category_description) LIKE %s)'
            search_param = f'%{search}%'
            category_params.extend([search_param, search_param])
        cursor.execute(category_query, category_params)
        archived_categories = cursor.fetchall()

        # Fetch archived suppliers
        supplier_query = 'SELECT * FROM Supplier WHERE is_active = FALSE'
        supplier_params = []
        if search:
            supplier_query += ' AND (LOWER(supplier_name) LIKE %s OR LOWER(email) LIKE %s)'
            search_param = f'%{search}%'
            supplier_params.extend([search_param, search_param])
        cursor.execute(supplier_query, supplier_params)
        archived_suppliers = cursor.fetchall()

        # Fetch archived warehouses
        warehouse_query = 'SELECT * FROM Warehouse WHERE is_active = FALSE'
        warehouse_params = []
        if search:
            warehouse_query += ' AND (LOWER(location_name) LIKE %s OR LOWER(street_address) LIKE %s OR LOWER(city) LIKE %s)'
            search_param = f'%{search}%'
            warehouse_params.extend([search_param, search_param, search_param])
        cursor.execute(warehouse_query, warehouse_params)
        archived_warehouses = cursor.fetchall()

    conn.close()

    return render_template('admin_archives.html',
                         archived_users=archived_users,
                         archived_products=archived_products,
                         archived_categories=archived_categories,
                         archived_suppliers=archived_suppliers,
                         archived_warehouses=archived_warehouses,
                         categories=categories,
                         search=search)

# Restore functions
@main.route('/admin/users/<int:user_id>/restore', methods=['POST'])
def admin_restore_user(user_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE Person SET is_active = TRUE WHERE person_id = %s', (user_id,))
        conn.commit()
    conn.close()
    flash('User has been restored.', 'success')
    return redirect(url_for('main.admin_archives'))

@main.route('/admin/products/<int:product_id>/restore', methods=['POST'])
def admin_restore_product(product_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE Product SET is_active = TRUE WHERE product_id = %s', (product_id,))
        conn.commit()
    conn.close()
    flash('Product has been restored.', 'success')
    return redirect(url_for('main.admin_archives'))

@main.route('/admin/categories/<int:category_id>/restore', methods=['POST'])
def admin_restore_category(category_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE Category SET is_active = TRUE WHERE category_id = %s', (category_id,))
        cursor.execute('UPDATE Product SET is_active = TRUE WHERE category_id = %s', (category_id,))
        conn.commit()
    conn.close()
    flash('Category and its products have been restored.', 'success')
    return redirect(url_for('main.admin_archives'))

@main.route('/admin/suppliers/<int:supplier_id>/restore', methods=['POST'])
def admin_restore_supplier(supplier_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE Supplier SET is_active = TRUE WHERE supplier_id = %s', (supplier_id,))
        conn.commit()
    conn.close()
    flash('Supplier has been restored.', 'success')
    return redirect(url_for('main.admin_archives'))

@main.route('/admin/warehouses/<int:warehouse_id>/restore', methods=['POST'])
def admin_restore_warehouse(warehouse_id):
    if 'user_id' not in session or session.get('user_role') != 'admin':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('main.login'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute('UPDATE Warehouse SET is_active = TRUE WHERE warehouse_id = %s', (warehouse_id,))
        conn.commit()
    conn.close()
    flash('Warehouse has been restored.', 'success')
    return redirect(url_for('main.admin_archives'))

