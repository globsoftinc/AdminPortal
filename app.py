from flask import Flask, render_template, request ,session,redirect,jsonify,make_response
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os
from flask_cors import CORS

load_dotenv()



usr_name = os.getenv("MONGO_USERNAME")
usr_password = os.getenv("MONGO_PASSWORD")
mongo_uri = os.getenv("MONGO_URI")

client = MongoClient(mongo_uri)

app = Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY")

# Add CORS (install: pip install flask-cors)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Allow all origins for public API
        "methods": ["GET"],
        "max_age": 300  # Cache preflight for 5 minutes
    }
})

# Simple in-memory cache
_status_cache = {"data": None, "timestamp": None}


def no_cache(f):
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route("/api/system-status", methods=['GET'])
def get_system_status():
    """Public endpoint with 5-minute cache"""
    global _status_cache
    
    # Check if cache is valid (less than 5 minutes old)
    if (_status_cache["data"] and _status_cache["timestamp"] and 
        datetime.now() - _status_cache["timestamp"] < timedelta(minutes=5)):
        response = jsonify(_status_cache["data"])
        response.headers['Cache-Control'] = 'public, max-age=300'
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    
    # Cache expired or empty - fetch from database
    db = client["globsoft_db"]
    collection = db["system_status"]
    status = collection.find_one(sort=[("updated_at", -1)])
    
    if not status:
        data = {"status": "running", "message": "All Systems Operational"}
    else:
        data = {
            "status": status.get("status", "running"),
            "message": status.get("message", "All Systems Operational"),
            "updated_at": status.get("updated_at").isoformat() if status.get("updated_at") else None
        }
    
    # Update cache
    _status_cache["data"] = data
    _status_cache["timestamp"] = datetime.now()
    
    response = jsonify(data)
    response.headers['Cache-Control'] = 'public, max-age=300'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route("/system-status", methods=['GET', 'POST'])
@no_cache
def manage_system_status():
    """Admin page - clears cache on update"""
    global _status_cache
    
    if 'user' in session and session['user'] == usr_name:
        db = client["globsoft_db"]
        collection = db["system_status"]
        
        if request.method == 'POST':
            status = request.form.get("status")
            message = request.form.get("message")
            
            status_data = {
                "status": status,
                "message": message,
                "updated_by": session['user'],
                "updated_at": datetime.now()
            }
            
            collection.insert_one(status_data)
            
            # Clear cache so next request fetches new data
            _status_cache = {"data": None, "timestamp": None}
            
            from flask import flash
            flash('System status updated successfully!', 'success')
            return redirect('/system-status')
        
        current_status = collection.find_one(sort=[("updated_at", -1)])
        history = list(collection.find().sort("updated_at", -1).limit(20))
        
        return render_template('system_status.html', 
                             current_status=current_status,
                             history=history)
    else:
        return redirect("/")

@app.route("/",methods=['GET','POST'])
@no_cache
def dashboard():
    if ('user' in session and session['user']== usr_name):
        return render_template('dashboard.html')
    if request.method=="POST":
        username = request.form.get("uname")
        password = request.form.get("password")
        if(username==usr_name and password==usr_password):
            session['user']=username
            return render_template('dashboard.html')
    return render_template('login.html')

@app.route("/logout", methods=['POST'])
@no_cache
def logout():
    session.pop('user', None)
    return redirect("/")

@app.route("/customer", methods=['GET', 'POST'])
@no_cache
def customer():
    if 'user' in session and session['user'] == usr_name:
        db = client["customer_db"]
        collection = db["customers"]
        
        # Fetch all customers
        customers = list(collection.find())
        
        return render_template('customer.html', customers=customers)
    else:
        return redirect("/")


@app.route("/customer/add", methods=['POST'])
@no_cache
def add_customer():
    if 'user' in session and session['user'] == usr_name:
        db = client["customer_db"]
        collection = db["customers"]
        
        customer_name = request.form.get("customer_name")
        customer_location = request.form.get("customer_location")
        customer_phone = request.form.get("customer_phone")
        customer_remark = request.form.get("customer_remark", "")
        
        # Check if customer with same phone already exists
        existing_customer = collection.find_one({"phone": customer_phone})
        
        if existing_customer:
            # Customer already exists - return with error message
            from flask import flash
            flash(f'Customer with phone number {customer_phone} already exists!', 'error')
            return redirect('/customer')
        
        customer_data = {
            "name": customer_name,
            "location": customer_location,
            "phone": customer_phone,
            "remark": customer_remark,
            "status_call": False,
            "status_sms": False,
            "status_whatsapp": False,
            "status_email": False,
            "user": session['user'],
            "date_added": datetime.now()
        }
        
        collection.insert_one(customer_data)
        from flask import flash
        flash('Customer added successfully!', 'success')
        
        return redirect('/customer')
    else:
        return redirect("/")


@app.route("/customer/edit/<customer_id>", methods=['GET', 'POST'])
@no_cache
def edit_customer(customer_id):
    if 'user' in session and session['user'] == usr_name:
        db = client["customer_db"]
        collection = db["customers"]
        
        if request.method == 'POST':
            customer_name = request.form.get("customer_name")
            customer_location = request.form.get("customer_location")
            customer_phone = request.form.get("customer_phone")
            customer_remark = request.form.get("customer_remark", "")
            
            updated_data = {
                "name": customer_name,
                "location": customer_location,
                "phone": customer_phone,
                "remark": customer_remark,
                "date_updated": datetime.now()
            }
            
            collection.update_one(
                {"_id": ObjectId(customer_id)},
                {"$set": updated_data}
            )
            
            return redirect('/customer')
        else:
            # GET request - show edit form
            customer = collection.find_one({"_id": ObjectId(customer_id)})
            return render_template('edit_customer.html', customer=customer)
    else:
        return redirect("/")


@app.route("/customer/delete", methods=['POST'])
@no_cache
def delete_customer():
    if 'user' in session and session['user'] == usr_name:
        db = client["customer_db"]
        collection = db["customers"]
        
        customer_id = request.form.get("customer_id")
        
        collection.delete_one({"_id": ObjectId(customer_id)})
        
        return redirect('/customer')
    else:
        return redirect("/")


@app.route("/customer/status", methods=['POST'])
@no_cache
def update_customer_status():
    if 'user' in session and session['user'] == usr_name:
        db = client["customer_db"]
        collection = db["customers"]
        
        customer_id = request.form.get("customer_id")
        status_type = request.form.get("status_type")
        is_checked = request.form.get("is_checked") == 'true'
        
        # Update the specific status field in customer document
        status_field = f"status_{status_type}"
        
        collection.update_one(
            {"_id": ObjectId(customer_id)},
            {"$set": {status_field: is_checked, "date_updated": datetime.now()}}
        )
        
        return redirect('/customer')
    else:
        return redirect("/")

@app.route("/sanourl", methods=['GET', 'POST', 'DELETE'])
@no_cache
def sanourl():
    if 'user' in session and session['user'] == usr_name:
        db = client["sanourl_db"]
        collection = db["urls"]
        
        # Handle DELETE request for multiple URLs
        if request.method == 'DELETE':
            data = request.get_json()
            url_ids = data.get('ids', [])
            if url_ids:
                from bson.objectid import ObjectId
                result = collection.delete_many({
                    '_id': {'$in': [ObjectId(id) for id in url_ids]}
                })
                return jsonify({'success': True, 'deleted': result.deleted_count})
            return jsonify({'success': False, 'message': 'No IDs provided'})
        
        # Fetch all URLs
        urls = list(collection.find())
        total_urls = len(urls)
        
        return render_template('sanourl.html', urls=urls, total_urls=total_urls)
    else:
        return redirect("/")

@app.route("/newsletter", methods=['GET', 'POST', 'DELETE'])
@no_cache
def newsletter():
    if 'user' in session and session['user'] == usr_name:
        db = client["emails_db"]
        collection = db["emails"]
        
        # Handle DELETE request for multiple emails
        if request.method == 'DELETE':
            data = request.get_json()
            email_ids = data.get('ids', [])
            if email_ids:
                try:
                    result = collection.delete_many({
                        '_id': {'$in': [ObjectId(id) for id in email_ids]}
                    })
                    return jsonify({'success': True, 'deleted': result.deleted_count})
                except Exception as e:
                    return jsonify({'success': False, 'message': str(e)}), 400
            return jsonify({'success': False, 'message': 'No IDs provided'}), 400
        
        # Fetch all emails
        emails = list(collection.find())
        total_emails = len(emails)
        
        return render_template('newsletter.html', emails=emails, total_emails=total_emails)
    else:

        return redirect("/")
