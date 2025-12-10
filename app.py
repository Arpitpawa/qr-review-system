try:
    import openai
except:
    openai = None

from config import AI_ENABLED, OPENAI_API_KEY
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, request, redirect, session, jsonify
import json, os
from datetime import datetime
import qrcode
import uuid
import random
from collections import Counter
from PIL import Image

app = Flask(__name__)
app.secret_key = "supersecretkey"
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

DATA_DIR = "data"

# ===================== UTILS =====================
def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
    with open(path, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(os.path.join(DATA_DIR, filename), "w") as f:
        json.dump(data, f, indent=4)

# ===================== ✅ PUBLIC HOME =====================
@app.route("/")
def home():
    # ✅ ALWAYS show home page first (NO auto redirect)
    return render_template("public/index.html")


# ===================== ✅ LOGIN =====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        users = load_json("users.json")

        for user in users:
            if user["email"] == email and user["password"] == password:
                session["user"] = user

                # ✅ DO NOT redirect to dashboard
                return redirect("/")   # always go to home

        return render_template("auth/login.html", error="Invalid credentials")

    return render_template("auth/login.html")


# ===================== ✅ SIGNUP =====================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        users = load_json("users.json")

        for u in users:
            if u["email"] == email:
                return render_template("auth/signup.html", error="Email already registered")

        new_user = {
            "id": str(uuid.uuid4())[:8],
            "name": name,
            "email": email,
            "password": password,
            "role": "owner",
            "created_at": str(datetime.now())
        }

        users.append(new_user)
        save_json("users.json", users)

        session["user"] = new_user
        return redirect("/")


    return render_template("auth/signup.html")

# ===================== ✅ LOGOUT =====================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ===================== ✅ ADD BUSINESS =====================
@app.route("/add-business", methods=["GET", "POST"])
def add_business():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        data = load_json("businesses.json")
        business_id = str(uuid.uuid4())[:8]

        owner_email = session["user"]["email"]

        new_business = {
            "id": business_id,
            "name": request.form["name"],
            "owner_email": owner_email,
            "google_review": request.form["google_review"],
            "status": request.form["status"],
            "category": request.form["category"]
        }

        data.append(new_business)
        save_json("businesses.json", data)

        qr_dir = os.path.join("static", "qr_codes")
        os.makedirs(qr_dir, exist_ok=True)

        qr_link = request.host_url.rstrip("/") + f"/r/{business_id}"

        # ✅ QR WITH LOGO
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
        qr.add_data(qr_link)
        qr.make()
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        logo_path = "static/logo.png"
        if os.path.exists(logo_path):
            logo = Image.open(logo_path)
            size = 90
            logo = logo.resize((size, size))
            pos = ((qr_img.size[0]-size)//2, (qr_img.size[1]-size)//2)
            qr_img.paste(logo, pos, mask=logo)

        qr_img.save(os.path.join(qr_dir, f"{business_id}.png"))

        return redirect("/businesses")

    return render_template("admin/add-business.html")

# ===================== ✅ BUSINESS LIST =====================
@app.route("/businesses")
def businesses():
    if "user" not in session:
        return redirect("/login")

    data = load_json("businesses.json")

    if session["user"]["role"] == "owner":
        data = [b for b in data if b["owner_email"] == session["user"]["email"]]

    return render_template("admin/businesses.html", businesses=data)

# ===================== ✅ DELETE BUSINESS =====================
@app.route("/delete-business/<bid>")
def delete_business(bid):
    if "user" not in session:
        return redirect("/login")

    data = load_json("businesses.json")
    data = [b for b in data if b["id"] != bid]
    save_json("businesses.json", data)

    qr_path = f"static/qr_codes/{bid}.png"
    if os.path.exists(qr_path):
        os.remove(qr_path)

    return redirect("/businesses")

# ===================== ✅ ADMIN DASHBOARD =====================
@app.route("/admin/dashboard")
def admin_dashboard():
    if "user" not in session or session["user"]["role"] != "admin":
        return redirect("/login")

    businesses = load_json("businesses.json")
    scans = load_json("scans.json")

    return render_template(
        "admin/dashboard.html",
        total_business=len(businesses),
        total_scans=len(scans),
        user=session["user"]
    )

# ===================== ✅ OWNER DASHBOARD =====================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/login")

    businesses = load_json("businesses.json")
    user_businesses = [b for b in businesses if b["owner_email"] == session["user"]["email"]]

    return render_template(
        "owner/dashboard.html",
        businesses=user_businesses,
        user=session["user"]
    )

# ===================== ✅ PUBLIC QR REVIEW PAGE =====================
@app.route("/r/<business_id>")
def review_page(business_id):
    businesses = load_json("businesses.json")
    business = next((b for b in businesses if b["id"] == business_id), None)

    if not business:
        return "Invalid QR"

    scans = load_json("scans.json")
    scans.append({
        "business_id": business_id,
        "time": str(datetime.now())
    })
    save_json("scans.json", scans)

    reviews_data = load_json("reviews.json")
    category = business.get("category", "general")
    category_reviews = reviews_data.get(category, reviews_data["general"])
    random_review = random.choice(category_reviews)

    return render_template(
        "public/review.html",
        business=business,
        review_text=random_review
    )

# ===================== ✅ GOOGLE REVIEW REDIRECT =====================
@app.route("/redirect-review")
def redirect_review():
    business_id = request.args.get("bid")
    businesses = load_json("businesses.json")
    business = next((b for b in businesses if b["id"] == business_id), None)
    return redirect(business["google_review"])

# ===================== ✅ LIVE SCAN API =====================
@app.route("/api/scans/<bid>")
def get_scans(bid):
    scans = load_json("scans.json")
    count = len([s for s in scans if s["business_id"] == bid])
    return jsonify({"count": count})

# ===================== ✅ ADMIN ANALYTICS =====================
@app.route("/analytics")
def analytics():
    if "user" not in session or session["user"]["role"] != "admin":
        return redirect("/login")

    businesses = load_json("businesses.json")
    scans = load_json("scans.json")

    return render_template("admin/analytics.html", businesses=businesses, scans=scans)

@app.route("/api/analytics/<bid>")
def analytics_api(bid):
    scans = load_json("scans.json")
    business_scans = [s for s in scans if s["business_id"] == bid]

    day_counts = Counter()
    for s in business_scans:
        day = s["time"].split(" ")[0]
        day_counts[day] += 1

    return {"labels": list(day_counts.keys()), "values": list(day_counts.values())}

# ===================== ✅ OWNER ANALYTICS =====================
@app.route("/owner/analytics")
def owner_analytics():
    if "user" not in session:
        return redirect("/login")

    businesses = load_json("businesses.json")
    scans = load_json("scans.json")

    owner_email = session["user"]["email"]
    owner_businesses = [b for b in businesses if b["owner_email"] == owner_email]

    stats = []
    for b in owner_businesses:
        count = len([s for s in scans if s["business_id"] == b["id"]])
        stats.append({"name": b["name"], "count": count})

    return render_template("owner/analytics.html", stats=stats)

# ===================== ✅ OWNER SCAN HISTORY =====================
@app.route("/owner/scan-history/<bid>")
def scan_history(bid):
    if "user" not in session:
        return redirect("/login")

    scans = load_json("scans.json")
    business_scans = [s for s in scans if s["business_id"] == bid]

    return render_template("owner/scan-history.html", scans=business_scans)

# ===================== ✅ RUN =====================
if __name__ == "__main__":
    app.run(debug=True)
