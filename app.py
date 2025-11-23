from flask import Flask, render_template, request ,session,redirect
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from dotenv import load_dotenv
import os

load_dotenv()



usr_name = os.getenv("MONGO_USERNAME")
usr_password = os.getenv("MONGO_PASSWORD")
mongo_uri = os.getenv("MONGO_URI")

client = MongoClient(mongo_uri)

app = Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY")

@app.route("/",methods=['GET','POST'])
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
def logout():
    session.pop('user', None)
    return redirect("/")

@app.route("/customer", methods=['GET', 'POST'])
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