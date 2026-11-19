from app.core.config import settings
from app.core.security import hash_password
from app.database.connection import engine, SessionLocal
from app.database.base import Base
from app import models
from app.models import Product, Policy, User

Base.metadata.create_all(bind=engine)

products = [
    ("Inspiron 15 3530", "Dell", "Intel Core i5-1334U", 16, 512, 15.6, 8.0, 1.65, "Windows 11", 56990, "IN_STOCK", "Everyday productivity laptop."),
    ("Vostro 3520", "Dell", "Intel Core i5-1235U", 16, 512, 15.6, 7.0, 1.66, "Windows 11", 52990, "IN_STOCK", "Business-focused laptop."),
    ("IdeaPad Slim 3", "Lenovo", "AMD Ryzen 5 7520U", 16, 512, 15.6, 8.5, 1.62, "Windows 11", 48990, "IN_STOCK", "Portable laptop for students."),
    ("IdeaPad Slim 5", "Lenovo", "AMD Ryzen 7 7730U", 16, 512, 14.0, 9.0, 1.46, "Windows 11", 62990, "IN_STOCK", "Lightweight productivity laptop."),
    ("LOQ 15", "Lenovo", "Intel Core i5-12450HX", 16, 512, 15.6, 5.0, 2.4, "Windows 11", 69990, "IN_STOCK", "Entry gaming laptop."),
    ("Pavilion 14", "HP", "Intel Core i5-1335U", 16, 512, 14.0, 8.0, 1.41, "Windows 11", 58990, "IN_STOCK", "Compact everyday laptop."),
    ("15s-fq", "HP", "Intel Core i3-1215U", 8, 512, 15.6, 7.0, 1.69, "Windows 11", 36990, "IN_STOCK", "Affordable student laptop."),
    ("Victus 15", "HP", "AMD Ryzen 5 8645HS", 16, 512, 15.6, 6.0, 2.29, "Windows 11", 74990, "IN_STOCK", "Gaming and performance laptop."),
    ("Vivobook 15", "ASUS", "Intel Core i5-1335U", 16, 512, 15.6, 8.0, 1.7, "Windows 11", 54990, "IN_STOCK", "General-purpose laptop."),
    ("Zenbook 14", "ASUS", "Intel Core Ultra 5 125H", 16, 512, 14.0, 12.0, 1.2, "Windows 11", 89990, "IN_STOCK", "Premium lightweight laptop."),
    ("Aspire 5", "Acer", "Intel Core i5-1235U", 16, 512, 15.6, 7.5, 1.77, "Windows 11", 49990, "IN_STOCK", "Balanced productivity laptop."),
    ("Swift Go 14", "Acer", "Intel Core Ultra 5 125H", 16, 512, 14.0, 10.0, 1.32, "Windows 11", 76990, "IN_STOCK", "Thin and lightweight laptop."),
    ("MacBook Air M2", "Apple", "Apple M2", 8, 256, 13.6, 15.0, 1.24, "macOS", 89990, "IN_STOCK", "Fanless laptop with long battery life."),
    ("MacBook Air M3", "Apple", "Apple M3", 16, 512, 13.6, 15.0, 1.24, "macOS", 124990, "IN_STOCK", "Premium portable laptop."),
    ("Aspire Lite", "Acer", "AMD Ryzen 5 5500U", 16, 512, 15.6, 7.0, 1.59, "Windows 11", 42990, "IN_STOCK", "Budget-friendly productivity laptop."),
    ("ThinkBook 14", "Lenovo", "Intel Core i5-1335U", 16, 512, 14.0, 8.0, 1.4, "Windows 11", 64990, "IN_STOCK", "Business productivity laptop."),
    ("ExpertBook B1", "ASUS", "Intel Core i5-1235U", 16, 512, 15.6, 9.0, 1.69, "Windows 11", 57990, "IN_STOCK", "Business laptop with practical features."),
    ("TravelMate P2", "Acer", "Intel Core i5-1235U", 8, 512, 15.6, 8.0, 1.7, "Windows 11", 45990, "OUT_OF_STOCK", "Business laptop."),
    ("VivoBook Go 15", "ASUS", "AMD Ryzen 5 7520U", 8, 512, 15.6, 7.0, 1.63, "Windows 11", 39990, "IN_STOCK", "Entry-level everyday laptop."),
    ("ThinkPad E14", "Lenovo", "AMD Ryzen 5 7530U", 16, 512, 14.0, 9.0, 1.41, "Windows 11", 67990, "IN_STOCK", "Business laptop with durable design."),
    ("Inspiron 14", "Dell", "Intel Core i5-1335U", 16, 512, 14.0, 9.0, 1.55, "Windows 11", 61990, "IN_STOCK", "Compact Dell productivity laptop."),
    ("Aspire 3", "Acer", "Intel Core i3-1215U", 8, 256, 15.6, 6.0, 1.78, "Windows 11", 31990, "IN_STOCK", "Entry-level laptop for basic tasks."),
    ("Pavilion Plus 14", "HP", "AMD Ryzen 7 7840U", 16, 1_000, 14.0, 9.0, 1.44, "Windows 11", 89990, "IN_STOCK", "High-performance compact laptop."),
    ("TUF Gaming F15", "ASUS", "Intel Core i5-12500H", 16, 512, 15.6, 5.0, 2.2, "Windows 11", 79990, "IN_STOCK", "Gaming laptop with dedicated graphics."),
    ("Swift 3", "Acer", "AMD Ryzen 7 5700U", 16, 512, 14.0, 10.0, 1.2, "Windows 11", 69990, "IN_STOCK", "Portable laptop for productivity."),
]

# 12 FAQ entries. Deliberately NOT covered: EMI / instalments and discounts, so
# the assistant must answer "I don't have that information" for those.
policies = [
    ("Return Policy", "returns", "Eligible laptops can be returned within 7 days of delivery if they are unused, in original packaging and include all accessories. Physical damage and customer-induced damage are not eligible."),
    ("Refund Timeline", "refunds", "Once a returned laptop passes inspection, the refund is credited to the original payment method within 5 to 7 business days."),
    ("Warranty Policy", "warranty", "Laptops include the manufacturer warranty stated on the product listing. Warranty claims are handled according to the manufacturer's terms. Keep the purchase invoice for warranty service."),
    ("Warranty Claim Process", "warranty", "To make a warranty claim, contact the brand's authorised service centre with your purchase invoice and the laptop serial number. VoltKart support can share the service centre details on request."),
    ("Shipping Policy", "shipping", "Standard delivery usually takes 3 to 7 business days after order confirmation. Delivery timelines may vary by serviceable PIN code."),
    ("Shipping Charges", "shipping", "Delivery is free on all laptop orders."),
    ("Delivery Coverage", "shipping", "VoltKart delivers across India to serviceable PIN codes. International shipping is not available."),
    ("Order Tracking", "tracking", "After dispatch, a tracking link is sent by SMS and email. You can use it to follow your order until delivery."),
    ("Cancellation Policy", "cancellation", "Orders can be cancelled before they are dispatched. Once an order is dispatched, cancellation may no longer be available."),
    ("Payment Methods", "payment", "The store accepts UPI, debit cards, credit cards and net banking. Cash on delivery availability depends on the delivery location."),
    ("Invoice", "invoice", "A GST invoice is emailed after the order is dispatched. Keep it for warranty and return requests."),
    ("Damaged or Defective Delivery", "damage", "If your laptop arrives damaged or defective, contact VoltKart support within 48 hours of delivery with photos of the product and packaging so a replacement or refund can be arranged."),
]

with SessionLocal() as db:
    if db.query(Product).count() == 0:
        for row in products:
            name, brand, processor, ram, storage, display, battery, weight, os_name, price, stock, description = row
            db.add(Product(
                product_name=name, brand=brand, category="Laptop", processor=processor,
                ram=ram, storage=storage, display_size=display, battery_life=battery,
                weight=weight, operating_system=os_name, price=price, stock_status=stock,
                description=description, warranty="1 year manufacturer warranty"
            ))

    # Upsert FAQ entries by title so re-running the seed on an existing database
    # adds the new entries and refreshes edited ones.
    existing = {p.title: p for p in db.query(Policy).all()}
    for title, category, content in policies:
        row = existing.get(title)
        if row:
            row.category, row.content, row.is_active = category, content, True
        else:
            db.add(Policy(title=title, category=category, content=content, is_active=True))
        # Bootstrap the first admin from .env (admins can never self-register).
    if settings.admin_email and settings.admin_password:
        admin_email = settings.admin_email.strip().lower()
        if not db.query(User).filter(User.email == admin_email).first():
            db.add(User(
                email=admin_email, full_name="VoltKart Admin",
                password_hash=hash_password(settings.admin_password), role="ADMIN",
            ))
            print(f"Created admin user {admin_email}")
    db.commit()

print("VoltKart seed data inserted.")