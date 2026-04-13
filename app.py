from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# ── Security: secret key from environment ONLY ────────────────────
# Before going live:
#   export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY environment variable must be set in production.")
    import secrets
    app.secret_key = secrets.token_hex(32)   # dev-only ephemeral key

# ── Database ──────────────────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///bakery.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Mail (Gmail SMTP) ─────────────────────────────────────────────
app.config["MAIL_SERVER"]         = os.environ.get("MAIL_SERVER",   "smtp.gmail.com")
app.config["MAIL_PORT"]           = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"]        = True
app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = (
    "SwirlNSprinkle Bakery",
    os.environ.get("MAIL_USERNAME"),
)

# ── Admin ─────────────────────────────────────────────────────────
ADMIN_PASSWORD     = os.environ.get("ADMIN_PASSWORD")
ADMIN_MAX_ATTEMPTS = 5        # lockout after N bad tries
ADMIN_LOCKOUT_SECS = 15 * 60  # 15-minute window

# ── Pickup time slots ─────────────────────────────────────────────
PICKUP_SLOTS = [
    "9:00 am – 9:30 am",
    "9:30 am – 10:00 am",
    "10:00 am – 10:30 am",
    "10:30 am – 11:00 am",
    "11:00 am – 11:30 am",
    "11:30 am – 12:00 pm",
    "12:00 pm – 12:30 pm",
    "12:30 pm – 1:00 pm",
    "1:00 pm – 1:30 pm",
    "1:30 pm – 2:00 pm",
]

# ── Promo codes { CODE: (description, discount_type, value) } ─────
PROMO_CODES = {
    "SWEET7": ("Buy 6 get 1 free — 1 item up to $5.50 off", "flat", 5.50),
}

# ── Baker notification recipient ──────────────────────────────────
BAKERY_NOTIFY_EMAIL = os.environ.get("BAKERY_NOTIFY_EMAIL")

csrf = CSRFProtect(app)
db   = SQLAlchemy(app)
mail = Mail(app)


# ════════════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════════════

class Order(db.Model):
    __tablename__ = "orders"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    email       = db.Column(db.String(200), nullable=False)
    phone       = db.Column(db.String(40))
    items       = db.Column(db.Text)
    total       = db.Column(db.Float, default=0.0)
    notes       = db.Column(db.Text)
    pickup_slot = db.Column(db.String(60))
    promo_code  = db.Column(db.String(30))
    status      = db.Column(db.String(30), default="pending")
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Order #{self.id} {self.name} [{self.status}]>"


class Subscriber(db.Model):
    __tablename__ = "subscribers"
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"
    id         = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80))
    last_name  = db.Column(db.String(80))
    email      = db.Column(db.String(200))
    phone      = db.Column(db.String(40))
    message    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MenuItem(db.Model):
    __tablename__ = "menu_items"
    id         = db.Column(db.Integer, primary_key=True)
    category   = db.Column(db.String(60), nullable=False)
    icon       = db.Column(db.String(10), default="🍞")
    name       = db.Column(db.String(120), nullable=False)
    desc       = db.Column(db.Text)
    price      = db.Column(db.Float, nullable=False)
    badge      = db.Column(db.String(40), default="")
    active     = db.Column(db.Boolean, default=True)
    sold_out   = db.Column(db.Boolean, default=False)  # daily flag, resets at midnight
    sort_order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id, "category": self.category, "icon": self.icon,
            "name": self.name, "desc": self.desc, "price": self.price,
            "badge": self.badge, "active": self.active, "sold_out": self.sold_out,
        }


class Location(db.Model):
    __tablename__ = "locations"
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), default="SwirlNSprinkle Bakery")
    address       = db.Column(db.String(200))
    city          = db.Column(db.String(80))
    zip_code      = db.Column(db.String(20))
    phone         = db.Column(db.String(40))
    email         = db.Column(db.String(200))
    hours_mon_fri = db.Column(db.String(60), default="7:00 am – 4:00 pm")
    hours_sat     = db.Column(db.String(60), default="7:00 am – 3:00 pm")
    hours_sun     = db.Column(db.String(60), default="8:00 am – 2:00 pm")
    maps_url      = db.Column(db.Text)
    lat           = db.Column(db.String(30))
    lng           = db.Column(db.String(30))


class Review(db.Model):
    __tablename__ = "reviews"
    id         = db.Column(db.Integer, primary_key=True)
    order_id   = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    name       = db.Column(db.String(120), nullable=False)
    stars      = db.Column(db.Integer, nullable=False)   # 1–5
    comment    = db.Column(db.Text)
    approved   = db.Column(db.Boolean, default=False)    # admin approves before showing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "order_id": self.order_id,
            "name": self.name, "stars": self.stars,
            "comment": self.comment, "approved": self.approved,
            "created_at": self.created_at.strftime("%d %b %Y"),
        }


def seed_defaults():
    if not MenuItem.query.first():
        defaults = [
            # Classic Cupcakes (Plain)
            MenuItem(category="classic_cupcakes", icon="🧁", name="Vanilla Cupcake",         desc="Light, fluffy, and perfect with tea/coffee.", price=25.00),
            MenuItem(category="classic_cupcakes", icon="🧁", name="Chocolate Cupcake",        desc="Light, fluffy, and perfect with tea/coffee.", price=25.00),
            MenuItem(category="classic_cupcakes", icon="🧁", name="Red Velvet Cupcake",       desc="Light, fluffy, and perfect with tea/coffee.", price=25.00),
            MenuItem(category="classic_cupcakes", icon="🧁", name="Tutti Frutti Cupcake",     desc="Light, fluffy, and perfect with tea/coffee.", price=25.00),

            # White Topping Cupcakes
            MenuItem(category="topping_cupcakes", icon="🍦", name="Vanilla Topping Cupcake",      desc="Classic base with smooth creamy frosting.", price=35.00),
            MenuItem(category="topping_cupcakes", icon="🍦", name="Chocolate Topping Cupcake",     desc="Classic base with smooth creamy frosting.", price=35.00),
            MenuItem(category="topping_cupcakes", icon="🍦", name="Red Velvet Topping Cupcake",    desc="Classic base with smooth creamy frosting.", price=35.00),
            MenuItem(category="topping_cupcakes", icon="🍦", name="Tutti Frutti Topping Cupcake",  desc="Classic base with smooth creamy frosting.", price=35.00),

            # Signature & Fusion Treats
            MenuItem(category="signature", icon="👑", name="Red Velvet Cheese Cream", desc="Rich, indulgent, and extra special.", price=45.00, badge="Signature"),
            MenuItem(category="signature", icon="👑", name="Milk Rich Cake",          desc="Rich, indulgent, and extra special.", price=70.00),
            MenuItem(category="signature", icon="👑", name="Rasmalai Rich Cake",      desc="Rich, indulgent, and extra special.", price=70.00),
            MenuItem(category="signature", icon="👑", name="Gulab Jamun Rich Cake",   desc="Rich, indulgent, and extra special.", price=70.00),
        ]
        db.session.add_all(defaults)

    if not Location.query.first():
        db.session.add(Location(
            name="SwirlNSprinkle Bakery",
            address="The Mpire Township",
            city="fursungi , pune",
            phone="+91 93599 92760",
            email="whoishsay000@gmail.com",
            maps_url="https://maps.google.com/?q=500+Terry+Francine+St+San+Francisco"
        ))

    db.session.commit()


with app.app_context():
    db.create_all()
    seed_defaults()


# ════════════════════════════════════════════════════════════════════
# EMAIL HELPERS
# ════════════════════════════════════════════════════════════════════

EMAIL_BASE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;padding:0;background:#faf3e8;font-family:'Helvetica Neue',Arial,sans-serif;color:#1e140a;}}
  .wrap{{max-width:580px;margin:40px auto;background:#fefcf9;border-top:4px solid #c0622a;}}
  .header{{background:#1e140a;padding:32px 40px;}}
  .header-brand{{font-size:32px;color:#f5ead8;letter-spacing:-.01em;font-weight:700;}}
  .header-sub{{font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:rgba(245,234,216,.5);margin-top:4px;}}
  .body{{padding:40px;}}
  h2{{font-size:22px;color:#1e140a;margin:0 0 16px;font-weight:600;}}
  p{{font-size:14px;line-height:1.9;color:#5c3a1e;margin:0 0 14px;}}
  .highlight{{background:#faf3e8;border-left:3px solid #c0622a;padding:16px 20px;margin:20px 0;}}
  .highlight p{{margin:0;}}
  .item-row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #ecdec8;font-size:14px;}}
  .item-row:last-child{{border-bottom:none;}}
  .total-row{{display:flex;justify-content:space-between;padding:12px 0 0;font-weight:700;font-size:15px;color:#c0622a;}}
  .btn{{display:inline-block;background:#c0622a;color:#fefcf9 !important;padding:12px 28px;font-size:12px;letter-spacing:.14em;text-transform:uppercase;font-weight:600;text-decoration:none;margin-top:24px;}}
  .footer{{background:#2d1c0d;padding:24px 40px;font-size:11px;color:rgba(245,234,216,.4);line-height:1.8;}}
  .divider{{height:1px;background:#ecdec8;margin:24px 0;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div class="header-brand">SwirlNSprinkle</div>
    <div class="header-sub">Artisanal Bakery &amp; Bakehouse · Est. 2026</div>
  </div>
  <div class="body">
    {body}
  </div>
  <div class="footer">
    The Mpire Township  , fursungi , pune;·&nbsp; whoishsay000@gmail.com<br>
    Open daily 7 am – 4 pm &nbsp;·&nbsp; &copy; {year} SwirlNSprinkle Bakery. All rights reserved.
  </div>
</div>
</body>
</html>
"""


def _render_email(body_html: str) -> str:
    return EMAIL_BASE.format(body=body_html, year=datetime.utcnow().year)


def send_order_confirmation(order):
    items_html = ""
    for part in order.items.split(", "):
        name, _, qty = part.rpartition(" x")
        items_html += f'<div class="item-row"><span>{name} × {qty}</span></div>'

    pickup_line = (f"<p>Pickup window: <strong>{order.pickup_slot}</strong></p>"
                   if order.pickup_slot else "")
    promo_line  = (f"<p>Promo applied: <strong>{order.promo_code}</strong></p>"
                   if order.promo_code else "")

    # Customer confirmation
    customer_body = f"""
    <h2>Order Confirmed 🥐</h2>
    <p>Hi {order.name}, thank you for your order! Here's a summary:</p>
    <div class="highlight">
      {items_html}
      <div class="total-row"><span>Total</span><span>${order.total:.2f}</span></div>
    </div>
    {pickup_line}
    {promo_line}
    <p>Your order is for <strong>in-store collection</strong>. We'll be in touch when it's ready.</p>
    <div class="divider"></div>
    <p style="font-size:12px;color:#9d7a5a;">
      Order #: <strong>{order.id}</strong>&nbsp;&nbsp;|&nbsp;&nbsp;
      Placed: <strong>{order.created_at.strftime('%d %b %Y, %H:%M')}</strong>
    </p>
    <p>Questions? Reply to this email or call +91 93599 92760.</p>
    <a class="btn" href="mailto:whoishsay000@gmail.com">Get in Touch</a>
    """
    try:
        mail.send(Message(
            subject=f"Your SwirlNSprinkle Order #{order.id} is Confirmed ✓",
            recipients=[order.email],
            html=_render_email(customer_body)
        ))
    except Exception as e:
        app.logger.warning(f"Order confirmation email failed: {e}")

    # Bakery staff notification
    staff_body = f"""
    <h2>New Order #{order.id} 🥐</h2>
    <p>A new order has been placed.</p>
    <div class="highlight">
      <p><strong>Customer:</strong> {order.name} &lt;{order.email}&gt;{' · ' + order.phone if order.phone else ''}</p>
      <p><strong>Pickup slot:</strong> {order.pickup_slot or 'Not specified'}</p>
      {items_html}
      <div class="total-row"><span>Total</span><span>${order.total:.2f}</span></div>
    </div>
    {'<p><strong>Notes:</strong> ' + order.notes + '</p>' if order.notes else ''}
    {'<p><strong>Promo:</strong> ' + order.promo_code + '</p>' if order.promo_code else ''}
    <p style="font-size:12px;color:#9d7a5a;">
      Placed: <strong>{order.created_at.strftime('%d %b %Y, %H:%M UTC')}</strong>
    </p>
    <a class="btn" href="https://SwirlNSprinklebakery.com/admin">View in Admin →</a>
    """
    try:
        mail.send(Message(
            subject=f"[SwirlNSprinkle] New Order #{order.id} — {order.name} (${order.total:.2f})",
            recipients=[BAKERY_NOTIFY_EMAIL],
            html=_render_email(staff_body)
        ))
    except Exception as e:
        app.logger.warning(f"Staff notification email failed: {e}")


def send_contact_reply(contact_msg):
    body = f"""
    <h2>We Received Your Message</h2>
    <p>Hi {contact_msg.first_name}, thank you for reaching out to SwirlNSprinkle Bakery.
    We've received your message and will be in touch within <strong>24 hours</strong>.</p>
    <div class="highlight">
      <p><strong>Your message:</strong></p>
      <p style="font-style:italic;color:#9d7a5a;">&ldquo;{contact_msg.message[:300]}{'…' if len(contact_msg.message)>300 else ''}&rdquo;</p>
    </div>
    <p>In the meantime, why not browse our menu or place an order online?</p>
    <a class="btn" href="https://SwirlNSprinklebakery.com/menu">Explore the Menu</a>
    """
    try:
        mail.send(Message(
            subject="We got your message — SwirlNSprinkle Bakery",
            recipients=[contact_msg.email],
            html=_render_email(body)
        ))
    except Exception as e:
        app.logger.warning(f"Contact email failed: {e}")


def send_welcome_email(email):
    body = """
    <h2>Welcome to the Neighborhood 🥐</h2>
    <p>You're officially on our list! We'll let you know about:</p>
    <div class="highlight">
      <p>✦ &nbsp; Seasonal pastry drops &amp; limited-edition bakes</p>
      <p>◈ &nbsp; Upcoming workshops and events</p>
      <p>❧ &nbsp; Our weekly bread schedule &amp; specials</p>
    </div>
    <p>Expect warm news from us — never spam, always something delicious.</p>
    <a class="btn" href="https://SwirlNSprinklebakery.com/order">Order Online</a>
    """
    try:
        mail.send(Message(
            subject="Welcome to SwirlNSprinkle Bakery — you're in! 🥐",
            recipients=[email],
            html=_render_email(body)
        ))
    except Exception as e:
        app.logger.warning(f"Welcome email failed: {e}")


# ════════════════════════════════════════════════════════════════════
# RATE LIMITING  (in-memory; swap for Redis/Flask-Limiter in prod)
# ════════════════════════════════════════════════════════════════════

_rate_store: dict = {}


def _is_rate_limited(key: str, max_calls: int, window_secs: int) -> bool:
    now    = datetime.utcnow()
    cutoff = now - timedelta(seconds=window_secs)
    ts     = [t for t in _rate_store.get(key, []) if t > cutoff]
    _rate_store[key] = ts
    if len(ts) >= max_calls:
        return True
    ts.append(now)
    _rate_store[key] = ts
    return False


def _client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()


# ════════════════════════════════════════════════════════════════════
# DAILY SOLD-OUT RESET
# ════════════════════════════════════════════════════════════════════

_last_soldout_reset: date | None = None


@app.before_request
def auto_reset_soldout():
    global _last_soldout_reset
    today = date.today()
    if _last_soldout_reset != today:
        try:
            MenuItem.query.update({"sold_out": False})
            db.session.commit()
            _last_soldout_reset = today
        except Exception:
            db.session.rollback()


# ════════════════════════════════════════════════════════════════════
# CONTEXT PROCESSOR
# ════════════════════════════════════════════════════════════════════

@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


# ════════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    reviews = (Review.query
               .filter_by(approved=True)
               .order_by(Review.created_at.desc())
               .limit(9).all())
    return render_template("home.html", reviews=reviews)


@app.route("/menu")
def menu():
    items = MenuItem.query.filter_by(active=True).order_by(MenuItem.category, MenuItem.sort_order, MenuItem.id).all()
    grouped = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    return render_template("menu.html", grouped=grouped)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    location = Location.query.first()
    if request.method == "POST":
        if _is_rate_limited(f"contact:{_client_ip()}", max_calls=5, window_secs=3600):
            flash("Too many submissions — please try again later.", "danger")
            return redirect(url_for("contact"))
        msg = ContactMessage(
            first_name=request.form.get("first_name", "").strip(),
            last_name =request.form.get("last_name",  "").strip(),
            email     =request.form.get("email",      "").strip(),
            phone     =request.form.get("phone",      "").strip(),
            message   =request.form.get("message",    "").strip(),
        )
        db.session.add(msg)
        db.session.commit()
        send_contact_reply(msg)
        flash("Thanks for reaching out! We'll be in touch within 24 hours.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html", location=location)


@app.route("/order", methods=["GET", "POST"])
def order():
    if request.method == "POST":
        if _is_rate_limited(f"order:{_client_ip()}", max_calls=10, window_secs=3600):
            flash("Too many orders submitted — please try again in a little while.", "danger")
            return redirect(url_for("order"))

        # Promo code validation
        raw_promo      = request.form.get("promo_code", "").strip().upper()
        promo_discount = 0.0
        promo_applied  = None
        if raw_promo:
            if raw_promo in PROMO_CODES:
                _, dtype, val = PROMO_CODES[raw_promo]
                promo_applied  = raw_promo
                promo_discount = val
            else:
                flash(f'Promo code "{raw_promo}" is not valid.', "warning")

        submitted_total = float(request.form.get("total", 0) or 0)
        final_total     = max(0.0, submitted_total - promo_discount)

        new_order = Order(
            name        = request.form.get("name",  "").strip(),
            email       = request.form.get("email", "").strip(),
            phone       = request.form.get("phone", "").strip(),
            items       = request.form.get("items", "").strip(),
            total       = final_total,
            notes       = request.form.get("notes", "").strip(),
            pickup_slot = request.form.get("pickup_slot", "").strip() or None,
            promo_code  = promo_applied,
        )
        db.session.add(new_order)
        db.session.commit()
        send_order_confirmation(new_order)
        return redirect(url_for("order_confirmation", order_id=new_order.id))

    items = MenuItem.query.filter_by(active=True).order_by(MenuItem.category, MenuItem.id).all()
    grouped = {}
    for item in items:
        grouped.setdefault(item.category, []).append(item)
    return render_template("order.html", grouped=grouped, pickup_slots=PICKUP_SLOTS)


@app.route("/order/confirmation/<int:order_id>")
def order_confirmation(order_id):
    o = Order.query.get_or_404(order_id)
    already_reviewed = Review.query.filter_by(order_id=order_id).first() is not None
    return render_template("order_confirmation.html", order=o, already_reviewed=already_reviewed)


@app.route("/review/submit", methods=["POST"])
def review_submit():
    order_id = request.form.get("order_id", type=int)
    stars    = request.form.get("stars",    type=int)
    name     = request.form.get("name",     "").strip()
    comment  = request.form.get("comment",  "").strip()

    if not order_id or not stars or not (1 <= stars <= 5) or not name:
        flash("Please complete the rating before submitting.", "warning")
        return redirect(url_for("order_confirmation", order_id=order_id or 0))

    # One review per order
    if Review.query.filter_by(order_id=order_id).first():
        flash("You've already left a review for this order — thanks! 🥐", "info")
        return redirect(url_for("order_confirmation", order_id=order_id))

    if _is_rate_limited(f"review:{_client_ip()}", max_calls=5, window_secs=3600):
        flash("Too many submissions — please try again later.", "danger")
        return redirect(url_for("order_confirmation", order_id=order_id))

    db.session.add(Review(order_id=order_id, name=name, stars=stars, comment=comment))
    db.session.commit()
    flash("Thank you for your review! It'll appear on our site once approved. 🌟", "success")
    return redirect(url_for("order_confirmation", order_id=order_id))



@app.route("/subscribe", methods=["POST"])
def subscribe():
    if _is_rate_limited(f"subscribe:{_client_ip()}", max_calls=3, window_secs=600):
        flash("Too many attempts — please try again in a few minutes.", "danger")
        return redirect(url_for("index") + "#newsletter")
    email = request.form.get("email", "").strip()
    if email:
        is_new = not Subscriber.query.filter_by(email=email).first()
        if is_new:
            db.session.add(Subscriber(email=email))
            db.session.commit()
            send_welcome_email(email)
        flash("You're on the list — welcome to the neighborhood! 🥐", "success")
    else:
        flash("Please enter a valid email address.", "danger")
    return redirect(url_for("index") + "#newsletter")


# ── Legal pages ───────────────────────────────────────────────────
@app.route("/privacy")
def privacy():
    return render_template("legal.html", page="Privacy Policy",
        content="""We respect your privacy. We collect only information you provide
        (name, email, phone, order details) to process orders, respond to enquiries,
        and send newsletters you have opted into. We never sell or share your data with
        third parties for marketing purposes. You may request deletion at any time by
        emailing whoishsay000@gmail.com. Cookies are used only for session management
        and are not used for tracking or advertising.""")


@app.route("/terms")
def terms():
    return render_template("legal.html", page="Terms & Conditions",
        content="""By using this website and placing orders you agree to the following.
        Orders are for in-store collection only — we do not offer delivery. Same-day
        orders must be placed before 2:00 pm. We reserve the right to cancel if items
        sell out; you will be notified promptly. Prices are in USD and may change
        without notice. Promo codes are non-transferable and cannot be combined.
        SwirlNSprinkle Bakery is not liable for allergic reactions where allergen information
        has been communicated. These terms are governed by California law.""")


@app.route("/accessibility")
def accessibility():
    return render_template("legal.html", page="Accessibility",
        content="""SwirlNSprinkle Bakery is committed to accessibility for all visitors. We
        strive to meet WCAG 2.1 Level AA standards. If you encounter any barriers,
        please contact us at whoishsay000@gmail.com or call +91 93599 92760 and we
        will assist you promptly. We welcome all feedback to improve the experience.""")


# ════════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ════════════════════════════════════════════════════════════════════

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        ip          = _client_ip()
        lockout_key = f"admin_lockout:{ip}"
        now         = datetime.utcnow()
        cutoff      = now - timedelta(seconds=ADMIN_LOCKOUT_SECS)
        attempts    = [t for t in _rate_store.get(lockout_key, []) if t > cutoff]
        _rate_store[lockout_key] = attempts

        if len(attempts) >= ADMIN_MAX_ATTEMPTS:
            mins = int((attempts[0] + timedelta(seconds=ADMIN_LOCKOUT_SECS) - now).total_seconds() // 60) + 1
            error = f"Too many failed attempts. Try again in ~{mins} minute(s)."
        elif request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            _rate_store[lockout_key]   = []
            return redirect(url_for("admin_dashboard"))
        else:
            attempts.append(now)
            _rate_store[lockout_key] = attempts
            left  = ADMIN_MAX_ATTEMPTS - len(attempts)
            error = f"Incorrect password. {left} attempt(s) remaining."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    today        = date.today()
    today_orders = Order.query.filter(
        db.func.date(Order.created_at) == today
    ).order_by(Order.created_at.desc()).all()

    today_revenue = sum(o.total for o in today_orders)
    today_count   = len(today_orders)
    all_orders    = Order.query.all()
    total_rev     = sum(o.total for o in all_orders)
    total_orders  = len(all_orders)
    subscribers   = Subscriber.query.count()
    contacts      = ContactMessage.query.count()
    recent_msgs   = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()
    location      = Location.query.first()
    menu_items    = MenuItem.query.order_by(MenuItem.category, MenuItem.id).all()

    pending_reviews = Review.query.filter_by(approved=False).order_by(Review.created_at.desc()).all()
    all_reviews     = Review.query.filter_by(approved=True).order_by(Review.created_at.desc()).all()

    return render_template("admin.html",
        today_orders=today_orders,
        today_revenue=today_revenue,
        today_count=today_count,
        total_rev=total_rev,
        total_orders=total_orders,
        subscribers=subscribers,
        contacts=contacts,
        recent_msgs=recent_msgs,
        location=location,
        today=today,
        menu_items=menu_items,
        pending_reviews=pending_reviews,
        all_reviews=all_reviews,
    )


# ── Menu CRUD ─────────────────────────────────────────────────────

@app.route("/admin/menu/items", methods=["GET"])
@admin_required
def admin_menu_items():
    items = MenuItem.query.order_by(MenuItem.category, MenuItem.id).all()
    return jsonify([i.to_dict() for i in items])


@app.route("/admin/menu/add", methods=["POST"])
@admin_required
def admin_menu_add():
    data = request.get_json() or request.form
    item = MenuItem(
        category=data.get("category", "pastries"),
        icon    =data.get("icon", "🍞"),
        name    =data.get("name", "").strip(),
        desc    =data.get("desc", "").strip(),
        price   =float(data.get("price", 0)),
        badge   =data.get("badge", "").strip(),
        active  =bool(data.get("active", True)),
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"ok": True, "id": item.id})


@app.route("/admin/menu/edit/<int:item_id>", methods=["POST"])
@admin_required
def admin_menu_edit(item_id):
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json() or request.form
    item.category = data.get("category", item.category)
    item.icon     = data.get("icon",     item.icon)
    item.name     = data.get("name",     item.name).strip()
    item.desc     = data.get("desc",     item.desc).strip()
    item.price    = float(data.get("price", item.price))
    item.badge    = data.get("badge",    item.badge).strip()
    item.active   = data.get("active") in (True, "true", "True", 1, "1", "on")
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/menu/delete/<int:item_id>", methods=["POST"])
@admin_required
def admin_menu_delete(item_id):
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/admin/menu/soldout/<int:item_id>", methods=["POST"])
@admin_required
def admin_menu_soldout(item_id):
    item = MenuItem.query.get_or_404(item_id)
    item.sold_out = not item.sold_out
    db.session.commit()
    state = "sold out" if item.sold_out else "available"
    flash(f'"{item.name}" marked as {state}.', "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu/reset-soldout", methods=["POST"])
@admin_required
def admin_reset_soldout():
    MenuItem.query.update({"sold_out": False})
    db.session.commit()
    flash("All sold-out flags reset.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Location update ───────────────────────────────────────────────

@app.route("/admin/location/update", methods=["POST"])
@admin_required
def admin_location_update():
    loc = Location.query.first() or Location()
    for field in ("name", "address", "city", "zip_code", "phone", "email",
                  "hours_mon_fri", "hours_sat", "hours_sun", "maps_url", "lat", "lng"):
        val = request.form.get(field, "").strip()
        if val:
            setattr(loc, field, val)
    db.session.add(loc)
    db.session.commit()
    flash("Location updated successfully.", "success")
    return redirect(url_for("admin_dashboard") + "#location")


# ── Order status update ───────────────────────────────────────────

@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    o = Order.query.get_or_404(order_id)
    o.status = request.form.get("status", o.status)
    db.session.commit()
    flash(f"Order #{o.id} marked as {o.status}.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/review/<int:review_id>/approve", methods=["POST"])
@admin_required
def admin_review_approve(review_id):
    r = Review.query.get_or_404(review_id)
    r.approved = True
    db.session.commit()
    flash(f"Review by {r.name} approved and is now live.", "success")
    return redirect(url_for("admin_dashboard") + "#reviews")


@app.route("/admin/review/<int:review_id>/delete", methods=["POST"])
@admin_required
def admin_review_delete(review_id):
    r = Review.query.get_or_404(review_id)
    db.session.delete(r)
    db.session.commit()
    flash("Review deleted.", "success")
    return redirect(url_for("admin_dashboard") + "#reviews")


# ── Promo validation AJAX ─────────────────────────────────────────

@app.route("/api/validate-promo", methods=["POST"])
def validate_promo():
    csrf.protect()
    code = (request.get_json() or {}).get("code", "").strip().upper()
    if code in PROMO_CODES:
        desc, dtype, val = PROMO_CODES[code]
        return jsonify({"valid": True, "code": code, "description": desc,
                        "type": dtype, "value": val})
    return jsonify({"valid": False})


if __name__ == "__main__":
    app.run(debug=False)