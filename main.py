import os
import sqlite3
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Ensure ADMIN_ID is set in .env
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", 0)) 

# Define connection states (Expanded for new admin menus and features)
(
    REGISTER_PHONE, REGISTER_NAME, REGISTER_DEVICE, 
    ASK_DISCOUNT, 
    ASK_TARGET, ASK_AMOUNT, 
    ASK_TOPUP, 
    ADMIN_ADD_SERVICE, ADMIN_ADD_DISCOUNT, ADMIN_CHARGE_USER, ADMIN_DEDUCT_CREDIT, ADMIN_BROADCAST, ADMIN_MESSAGE_USER, 
    SUPPORT_MESSAGE, ADMIN_ADD_SERVICE_CONTENT_TO_USER,
    
    # New Admin States for button-based actions
    ADMIN_SET_SERVICE_PRICE, ADMIN_REMOVE_DISCOUNT,
    ADMIN_SET_PRICE_AMOUNT, ADMIN_CHARGE_AMOUNT, ADMIN_DEDUCT_AMOUNT,
    ADMIN_MESSAGE_USER_INPUT, ADMIN_VIEW_SUPPORT_MESSAGES
) = range(23)

# Define constants for navigation callbacks
ADMIN_MAIN_MENU = "admin_main_menu"
ADMIN_USER_MGMT_MENU = "admin_user_mgmt_menu"
ADMIN_SERVICE_MGMT_MENU = "admin_service_mgmt_menu"
ADMIN_DISCOUNT_MGMT_MENU = "admin_discount_mgmt_menu"
ADMIN_MESSAGE_MGMT_MENU = "admin_message_mgmt_menu"
ADMIN_STATS_MENU = "admin_stats_menu"
ADMIN_PURCHASE_REQ_MENU = "admin_purchase_req_menu"

# Connect to database
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# Create database tables (Updated services table to include price, added support_messages and purchase_requests)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    credit INTEGER DEFAULT 0,
    discount_used INTEGER DEFAULT 0,
    is_approved INTEGER DEFAULT 0,
    phone_number TEXT,
    full_name TEXT,
    device_type TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    value INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS services (
    type TEXT PRIMARY KEY,
    content TEXT,         
    is_file INTEGER DEFAULT 0,
    price INTEGER DEFAULT 0 
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    message TEXT,
    timestamp TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS purchase_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    description TEXT,
    timestamp TEXT,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")
conn.commit()

# --- Inline Keyboards ---

# Main user keyboard
def get_main_inline_keyboard(is_admin):
    keyboard = [
        [
            InlineKeyboardButton("📃 دریافت برنامه", callback_data="get_app"), 
            InlineKeyboardButton("🎁 فعال‌سازی کد تخفیف", callback_data="activate_discount")
        ],
        [
            InlineKeyboardButton("🏦 اعتبار من", callback_data="my_credit"), 
            InlineKeyboardButton("🔁 انتقال اعتبار", callback_data="transfer_credit")
        ],
        [
            InlineKeyboardButton("🌐 دریافت سرویس‌ها", callback_data="get_service"), 
            InlineKeyboardButton("💳 افزایش اعتبار", callback_data="topup")
        ],
        [
            InlineKeyboardButton("ℹ️ وضعیت من", callback_data="my_status"),
            InlineKeyboardButton("✉️ پیام به پشتیبانی", callback_data="support_message")
        ]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("🎛 پنل مدیریت", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

# Admin Keyboards
def get_admin_main_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data=ADMIN_USER_MGMT_MENU), 
         InlineKeyboardButton("🛰 مدیریت سرویس‌ها", callback_data=ADMIN_SERVICE_MGMT_MENU)],
        [InlineKeyboardButton("📊 آمار ربات", callback_data=ADMIN_STATS_MENU),
         InlineKeyboardButton("🎁 کدهای تخفیف", callback_data=ADMIN_DISCOUNT_MGMT_MENU)],
        [InlineKeyboardButton("💳 درخواست‌های خرید", callback_data=ADMIN_PURCHASE_REQ_MENU)],
        [InlineKeyboardButton("📢 پیام‌ها و پشتیبانی", callback_data=ADMIN_MESSAGE_MGMT_MENU)],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_user_mgmt_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧾 تأیید/رد کاربران", callback_data="admin_approve_reject")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_user_list")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_service_mgmt_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ افزودن سرویس", callback_data="admin_add_service_type")],
        [InlineKeyboardButton("💰 تعیین قیمت سرویس", callback_data="admin_set_price_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_discount_mgmt_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="admin_add_discount_menu")],
        [InlineKeyboardButton("❌ حذف کد تخفیف", callback_data="admin_remove_discount_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_message_mgmt_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton("✉️ پیام‌های پشتیبانی", callback_data="admin_view_support_messages_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- User Commands and Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text("خوش آمدید.", reply_markup=ReplyKeyboardRemove())
    cursor.execute("SELECT full_name FROM users WHERE id=?", (user.id,))
    user_info = cursor.fetchone()

    if not user_info or user_info[0] is None:
        cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user.id, user.username))
        conn.commit()
        return await ask_phone_number(update, context)

    await update.message.reply_text(
        "سلام! به ربات VPN خوش اومدی 👋\n\nلطفاً یک گزینه را انتخاب کنید:", 
        reply_markup=get_main_inline_keyboard(user.id == ADMIN_ID)
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Updated about text as requested by the user
    about_text = """
🔰 درباره تیم ویرا:
👋 ما تیم ویرا هستیم. 
🚀 ارائه‌دهنده سرویس‌های امن و پایدار VPN برای ارتباط آزاد.
📞 پشتیبانی 24/7
🔒 امنیت بالا
⚡️ سرعت عالی

تیم ویرا با هدف ایجاد دسترسی کامل افراد به اینترنت آزاد و بدون محدودیت شروع به کار کرد و این تیم زیر مجموعه (تیم پیوند) می‌باشد.

💬 برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.
"""
    await update.message.reply_text(about_text)

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT credit FROM users WHERE id=?", (update.effective_user.id,))
    user_credit = cursor.fetchone()
    if user_credit:
        await update.message.reply_text(f"🔢 امتیاز (اعتبار) شما: {user_credit[0]} تومان")
    else:
        await update.message.reply_text("❌ اطلاعات شما یافت نشد. لطفاً /start را بزنید.")

async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cursor.execute("SELECT credit, discount_used, is_approved, phone_number, full_name, device_type FROM users WHERE id=?", (user.id,))
    user_data = cursor.fetchone()
    
    if user_data:
        credit, discount_used, approved, phone_number, full_name, device_type = user_data
        await update.message.reply_text(f"""👤 @{user.username}
🆔 {user.id}
📝 نام: {full_name or 'نامشخص'}
📞 شماره تلفن: {phone_number or 'نامشخص'}
💻 دستگاه: {device_type or 'نامشخص'}
💳 اعتبار: {credit} تومان
🎁 کد تخفیف: {"استفاده شده" if discount_used else "فعال نشده"}
✅ وضعیت تأیید: {"تأیید شده" if approved else "در انتظار تأیید"}
""")
    else:
        await update.message.reply_text("❌ کاربر یافت نشد. لطفاً دوباره /start را بزنید.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "عملیات لغو شد.", reply_markup=get_main_inline_keyboard(update.effective_user.id == ADMIN_ID)
    )
    return ConversationHandler.END

# --- Registration Flow ---

async def ask_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("ارسال شماره تلفن", request_contact=True)]]
    await update.message.reply_text(
        "لطفاً برای ثبت‌نام، شماره تلفن خود را ارسال کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return REGISTER_PHONE

async def register_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact and contact.user_id == user_id:
        phone_number = contact.phone_number
        cursor.execute("UPDATE users SET phone_number=? WHERE id=?", (phone_number, user_id))
        conn.commit()
        await update.message.reply_text("شماره تلفن شما با موفقیت ثبت شد. حالا لطفا نام و نام خانوادگی خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return REGISTER_NAME

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    cursor.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user_id))
    conn.commit()
    
    device_keyboard = [
        [InlineKeyboardButton("📱 اندروید", callback_data="register_device_android")],
        [InlineKeyboardButton("🍏 آیفون", callback_data="register_device_iphone")],
        [InlineKeyboardButton("🖥 ویندوز", callback_data="register_device_windows")]
    ]
    await update.message.reply_text("نام شما ثبت شد. حالا نوع دستگاه خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(device_keyboard))
    return REGISTER_DEVICE

async def register_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    device_map = {
        "register_device_android": "اندروید", "register_device_iphone": "آیفون", "register_device_windows": "ویندوز"
    }
    device_type = device_map.get(data)
    
    if device_type:
        cursor.execute("UPDATE users SET device_type=?, is_approved=1 WHERE id=?", (device_type, user.id))
        conn.commit()

        # Admin notification
        cursor.execute("SELECT phone_number, full_name FROM users WHERE id=?", (user.id,))
        registered_user = cursor.fetchone()
        if registered_user:
            phone_number, full_name = registered_user
            await context.bot.send_message(
                ADMIN_ID, 
                f"🎉 کاربر جدید ثبت‌نام کرد:\nنام: {full_name}\nنام کاربری: @{user.username}\nID: {user.id}\nشماره تلفن: {phone_number}\nدستگاه: {device_type}"
            )
        
        await query.edit_message_text(
            f"ثبت‌نام شما با موفقیت انجام شد ({device_type}). می‌توانید از دکمه‌های زیر استفاده کنید.",
            reply_markup=get_main_inline_keyboard(user.id == ADMIN_ID)
        )
        return ConversationHandler.END
    return REGISTER_DEVICE

# --- User Actions Handlers ---

# Handles all user inline button presses and general callbacks
async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    data = query.data
    
    # Handle "back" from conversations
    if data in ["cancel_transfer", "cancel_topup", "cancel_support"]:
        await query.edit_message_text("عملیات لغو شد.", reply_markup=get_main_inline_keyboard(user_id == ADMIN_ID))
        return ConversationHandler.END
    
    # Handle main menu navigation and actions
    if data == "main_menu":
        await query.edit_message_text("منوی اصلی:", reply_markup=get_main_inline_keyboard(user_id == ADMIN_ID))
        return ConversationHandler.END
    
    elif data == "get_app":
        return await get_app(update, context)
    elif data == "activate_discount":
        await query.edit_message_text("🎁 لطفاً کد تخفیف را وارد کنید:")
        return ASK_DISCOUNT
    elif data == "my_credit":
        cursor.execute("SELECT credit FROM users WHERE id=?", (user_id,))
        credit = cursor.fetchone()
        if credit:
            await query.edit_message_text(f"💳 اعتبار شما: {credit[0]} تومان", reply_markup=get_main_inline_keyboard(user_id == ADMIN_ID))
        else:
            await query.edit_message_text("❌ کاربر یافت نشد. لطفاً دوباره /start را بزنید.")
        return ConversationHandler.END
    elif data == "transfer_credit":
        await query.edit_message_text("🔁 لطفاً ID عددی دریافت‌کننده را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_transfer")]]))
        return ASK_TARGET
    elif data == "my_status":
        return await myinfo(query, context) # Reuse myinfo function for status
    elif data == "get_service":
        return await get_service(update, context)
    elif data == "topup":
        await query.edit_message_text("💳 مقدار و توضیحات پرداخت خود را وارد کنید:\nمثال: 100000 - کارت به کارت به 6274xxxxxxxxxxxx", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_topup")]]))
        return ASK_TOPUP
    elif data == "support_message":
        await query.edit_message_text("✉️ لطفاً پیام خود را برای پشتیبانی ارسال کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_support")]]))
        return SUPPORT_MESSAGE
    elif data == "admin_panel":
        return await admin(update, context)

# --- User Side Functionality ---

async def get_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # We send the Inline keyboard for app selection
    await query.edit_message_text(
        "لطفاً دستگاه خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 اندروید", callback_data="app_android"), InlineKeyboardButton("🍏 آیفون", callback_data="app_iphone")],
            [InlineKeyboardButton("🖥 ویندوز", callback_data="app_windows"), InlineKeyboardButton("❓ راهنمای اتصال", callback_data="app_guide")],
            [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
        ])
    )

async def send_app_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    selected_option = query.data
    
    # NOTE: Placeholder paths for images, assuming they exist in a local directory
    BASE_IMAGE_PATH = "./Image/" 

    links = {
        "app_android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
        "app_iphone": "https://apps.apple.com/app/openvpn-connect/id590379981",
        "app_windows": "https://openvpn.net/client-connect-vpn-for-windows/",
        "app_guide": {
            "type": "guide_photos",
            "files": [
                f"{BASE_IMAGE_PATH}photo1.jpg", f"{BASE_IMAGE_PATH}photo2.jpg", f"{BASE_IMAGE_PATH}photo3.jpg", 
                f"{BASE_IMAGE_PATH}photo4.jpg", f"{BASE_IMAGE_PATH}photo5.jpg", f"{BASE_IMAGE_PATH}photo6.jpg", 
                f"{BASE_IMAGE_PATH}photo7.jpg", f"{BASE_IMAGE_PATH}photo8.jpg", f"{BASE_IMAGE_PATH}photo9.jpg", 
                f"{BASE_IMAGE_PATH}photo10.jpg",
            ],
            "captions": [
                "1. برنامه OpenVPN را از استور نصب کنید...", "2. روی تب file کلیک کنید ...", "3. روی browse کلیک کنید ...",
                "4. پوشه ای که فایل دریافتی را ذخیره کرده اید بروید.", "5. فایل دریافتی را انتخاب و وارد برنامه کنید.", 
                "6. روی ok کلیک کنید.", "7. username و password دریافتی را درقسمت مشخص شده وارد کنید.",
                "8. درخواست اتصال را تایید کنید.", "9.اگر به متصل نشد روی دکمه کنار فایل کلیک کنید و منتظر بمانید .",
                "10.پس از اتصال موفقیت‌آمیز، وضعیت را سبز ببینید...",
            ],
            "additional_note": "نکته : در دستگاه های آیفون(ios) و برخی دستگاه های با اندروید قدیمی لازم است تا ابتدا فایل را باز کرده و با زدن دکمه share و انتخاب نام برنامه آن را وارد برنامه کنید و باقی مراحل را طی کنید.\nدر صورت وجود مشکل با پشتیبانی تماس بگیرید"
        }
    }

    if selected_option == "app_guide":
        guide_info = links[selected_option]
        if guide_info["type"] == "guide_photos":
            media = []
            try:
                for i, file_path in enumerate(guide_info["files"]):
                    caption = guide_info["captions"][i] if i < len(guide_info["captions"]) else f"راهنما - عکس {i+1}"
                    # We pass the file path for InputMediaPhoto to read
                    media.append(InputMediaPhoto(media=open(file_path, 'rb'), caption=caption))
            except FileNotFoundError:
                await query.message.reply_text(f"خطا: فایل راهنما پیدا نشد. مطمئن شوید فایل‌ها در مسیر `{BASE_IMAGE_PATH}` قرار دارند.")
                return
            except Exception as e:
                await query.message.reply_text(f"خطا در بارگذاری عکس: {e}")
                return
            
            if media:
                try:
                    await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
                    if "additional_note" in guide_info:
                        await query.message.reply_text(guide_info["additional_note"])
                except Exception as e:
                    await query.message.reply_text(f"خطا در ارسال گروهی تصاویر: {e}")
            else:
                await query.message.reply_text("هیچ عکسی برای راهنما یافت نشد.")
    else:
        await query.edit_message_text(links.get(selected_option, "❌ گزینه نامعتبر"))
    
    # After sending the link/guide, send the main menu inline keyboard
    await context.bot.send_message(query.from_user.id, "بازگشت به منوی اصلی:", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))


async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    cursor.execute("SELECT is_approved FROM users WHERE id=?", (user_id,))
    approved = cursor.fetchone()
    
    if not approved or approved[0] == 0:
        await query.edit_message_text("⛔ شما هنوز ثبت‌نام خود را تکمیل نکرده‌اید یا توسط ادمین تأیید نشده‌اید.")
        return

    # Fetch services and prices from DB
    cursor.execute("SELECT type, price FROM services")
    services = cursor.fetchall()

    keyboard = []
    for service_type, price in services:
        price_text = f" ({price:,} تومان)" if price > 0 else ""
        # The callback data should clearly indicate a service request
        keyboard.append([InlineKeyboardButton(f"{service_type}{price_text}", callback_data=f"request_service_{service_type}")])

    keyboard.append([InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")])

    await query.edit_message_text("کدام سرویس را می‌خواهید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_service_request_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if not data.startswith("request_service_"):
        await query.edit_message_text("❌ درخواست سرویس نامعتبر.")
        return
        
    service_key = data.replace("request_service_", "")

    msg_for_admin = (
        f"🌐 درخواست سرویس جدید از کاربر:\n"
        f"کاربر: @{user.username}\n"
        f"ID: {user.id}\n"
        f"نوع سرویس درخواستی: {service_key}\n\n"
        f"لطفاً سرویس مربوطه را برای این کاربر ارسال کنید."
    )
    
    # Admin inline keyboard for response
    keyboard = [
        [InlineKeyboardButton("✅ ارسال سرویس", callback_data=f"send_service_{user.id}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"reject_service_{user.id}")],
        [InlineKeyboardButton("✉️ چت با کاربر", callback_data=f"chat_user_{user.id}")]
    ]

    await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.edit_message_text("✅ درخواست شما به ادمین ارسال شد. لطفاً منتظر دریافت سرویس بمانید.")

# --- Discount related functions ---
async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    code = update.message.text.strip()

    cursor.execute("SELECT discount_used FROM users WHERE id=?", (user_id,))
    user_data = cursor.fetchone()

    if user_data and user_data[0]:
        await update.message.reply_text("⛔ شما قبلاً از کد تخفیف استفاده کرده‌اید.")
        return ConversationHandler.END

    cursor.execute("SELECT value FROM codes WHERE code=?", (code,))
    row = cursor.fetchone()
    if row:
        value = row[0]
        cursor.execute("UPDATE users SET credit = credit + ?, discount_used = 1 WHERE id=?", (value, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ {value} تومان اعتبار اضافه شد.")
    else:
        await update.message.reply_text("❌ کد تخفیف نامعتبر است.")
    
    return ConversationHandler.END

# --- Transfer Credit related functions ---
async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_id"] = int(update.message.text)
        await update.message.reply_text("چه مقدار اعتبار منتقل شود؟")
        return ASK_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ ID عددی نامعتبر است. لطفا یک ID عددی وارد کنید.")
        return ConversationHandler.END

async def do_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید مثبت باشد.")
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ مبلغ عددی نامعتبر است.")
        return ConversationHandler.END

    sender = update.effective_user.id
    receiver = context.user_data["target_id"]
    
    cursor.execute("SELECT credit FROM users WHERE id=?", (sender,))
    sender_credit = cursor.fetchone()[0] if cursor.fetchone() else 0
    
    cursor.execute("SELECT id FROM users WHERE id=?", (receiver,))
    if not cursor.fetchone():
        await update.message.reply_text("❌ ID دریافت‌کننده نامعتبر است.")
        return ConversationHandler.END

    if sender_credit < amount:
        await update.message.reply_text("❌ اعتبار شما کافی نیست.")
    else:
        cursor.execute("UPDATE users SET credit = credit - ? WHERE id=?", (amount, sender))
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id=?", (amount, receiver))
        conn.commit()
        await update.message.reply_text("✅ انتقال انجام شد.")
    return ConversationHandler.END

# --- Topup related functions (Modified to log purchase requests) ---
async def send_topup_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text
    
    try:
        # Extract amount and description (simple parsing for now)
        parts = message_text.split('-', 1)
        amount_str = parts[0].strip()
        description = parts[1].strip() if len(parts) > 1 else "بدون توضیحات"
        
        amount = int(amount_str)
        
        # Log the purchase request to the database
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO purchase_requests (user_id, amount, description, timestamp, status) VALUES (?, ?, ?, ?, ?)",
                       (user.id, amount, description, timestamp, 'pending'))
        conn.commit()
        
        # Notify admin
        msg_for_admin = (
            f"💳 درخواست افزایش اعتبار جدید:\n"
            f"کاربر: @{user.username} (ID: {user.id})\n"
            f"مبلغ: {amount:,} تومان\n"
            f"توضیحات: {description}"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin) 
        
        await update.message.reply_text("✅ درخواست شما به ادمین ارسال شد. لطفاً منتظر تأیید ادمین بمانید.")

    except ValueError:
        await update.message.reply_text("❌ فرمت ورودی اشتباه است. لطفاً مبلغ را به درستی وارد کنید. مثال: 100000 - کارت به کارت به 6274xxxxxxxxxxxx")
    
    return ConversationHandler.END

# --- Support Message related functions (Modified to log messages) ---
async def send_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    support_message = update.message.text
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Log message to database
    cursor.execute("INSERT INTO support_messages (user_id, message, timestamp) VALUES (?, ?, ?)",
                   (user.id, support_message, timestamp))
    conn.commit()

    msg_for_admin = f"✉️ پیام جدید از پشتیبانی:\nکاربر: @{user.username} (ID: {user.id})\nپیام: {support_message}"
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin) 
    await update.message.reply_text("پیام شما به پشتیبانی ارسال شد. در اسرع وقت پاسخ خواهیم داد.")
    return ConversationHandler.END

# --- Admin Panel Handlers ---

# Admin: Entry point
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID: 
        return
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🎛 پنل مدیریت:", reply_markup=get_admin_main_inline_keyboard())
    else:
        await update.message.reply_text("🎛 پنل مدیریت:", reply_markup=get_admin_main_inline_keyboard())

# Admin: Navigation Callback Router
async def admin_panel_navigation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == ADMIN_USER_MGMT_MENU:
        await query.edit_message_text("👥 مدیریت کاربران:", reply_markup=get_admin_user_mgmt_keyboard())
    elif data == ADMIN_SERVICE_MGMT_MENU:
        await query.edit_message_text("🛰 مدیریت سرویس‌ها:", reply_markup=get_admin_service_mgmt_keyboard())
    elif data == ADMIN_DISCOUNT_MGMT_MENU:
        await query.edit_message_text("🎁 مدیریت کدهای تخفیف:", reply_markup=get_admin_discount_mgmt_keyboard())
    elif data == ADMIN_MESSAGE_MGMT_MENU:
        await query.edit_message_text("📢 پیام‌ها و پشتیبانی:", reply_markup=get_admin_message_mgmt_keyboard())
    elif data == ADMIN_STATS_MENU:
        return await admin_stats(update, context)
    elif data == ADMIN_PURCHASE_REQ_MENU:
        return await admin_purchase_requests(update, context)
    
    # Specific action entry points triggered by buttons
    elif data == "admin_approve_reject":
        return await list_pending_and_approve_reject(update, context)
    elif data == "admin_user_list":
        return await admin_user_list(update, context)
    elif data == "admin_add_discount_menu":
        await query.edit_message_text("➕ کد و مقدار را وارد کن (مثال: vip50 5000):")
        return ADMIN_ADD_DISCOUNT
    elif data == "admin_remove_discount_menu":
        await query.edit_message_text("❌ کد تخفیف مورد نظر برای حذف را وارد کنید:")
        return ADMIN_REMOVE_DISCOUNT
    elif data == "admin_add_service_type":
        service_types_keyboard = [
            [InlineKeyboardButton("🔐 OpenVPN", callback_data="admin_add_openvpn"), InlineKeyboardButton("🛰 V2Ray", callback_data="admin_add_v2ray")],
            [InlineKeyboardButton("📡 Proxy تلگرام", callback_data="admin_add_proxy")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data=ADMIN_SERVICE_MGMT_MENU)]
        ]
        await query.edit_message_text("نوع سرویس را برای افزودن محتوا انتخاب کنید:", reply_markup=InlineKeyboardMarkup(service_types_keyboard))
    elif data.startswith("admin_add_"):
        service_type = data.replace("admin_add_", "")
        context.user_data["servicetype"] = service_type
        await query.edit_message_text(f"لطفاً لینک، متن سرویس ({service_type}) را وارد کنید یا **فایل مربوطه را ارسال نمایید:**")
        return ADMIN_ADD_SERVICE
    elif data == "admin_set_price_menu":
        return await admin_set_price_menu(update, context)
    elif data == "admin_broadcast_menu":
        await query.edit_message_text("📢 پیام همگانی را ارسال کنید:")
        return ADMIN_BROADCAST
    elif data == "admin_view_support_messages_menu":
        return await admin_view_support_messages(update, context)

# Admin: User List (New Feature)
async def admin_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT id, username, full_name, credit FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    
    if not users:
        await query.edit_message_text("❌ کاربری در دیتابیس وجود ندارد.")
        return

    # We will send a list of users with buttons for actions
    await query.edit_message_text("👥 لیست کاربران:")
    
    for uid, uname, name, credit in users:
        user_info = f"ID: {uid}\nنام: {name or 'نامشخص'} (@{uname or 'نامشخص'})\nاعتبار: {credit:,} تومان"
        
        # Buttons for actions on this user
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💰 شارژ", callback_data=f"admin_charge_user_{uid}"),
                InlineKeyboardButton("➖ کسر اعتبار", callback_data=f"admin_deduct_credit_{uid}")
            ],
            [
                InlineKeyboardButton("✉️ چت", callback_data=f"admin_chat_user_{uid}")
            ]
        ])
        
        await context.bot.send_message(chat_id=ADMIN_ID, text=user_info, reply_markup=keyboard)
    
    # Send back button
    await context.bot.send_message(chat_id=ADMIN_ID, text="بازگشت به مدیریت کاربران:", reply_markup=get_admin_user_mgmt_keyboard())


# Admin: Handle user-specific actions (Charge/Deduct/Chat) via buttons
async def admin_user_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if '_' not in data:
        return
    
    parts = data.split('_')
    action = parts[2]
    uid = int(parts[3])
    
    context.user_data['target_user_id'] = uid
    
    if action == "charge":
        await query.edit_message_text(f"💰 لطفاً مبلغ شارژ برای کاربر {uid} را وارد کنید:")
        return ADMIN_CHARGE_AMOUNT
    elif action == "deduct":
        await query.edit_message_text(f"➖ لطفاً مبلغ کسر اعتبار برای کاربر {uid} را وارد کنید:")
        return ADMIN_DEDUCT_AMOUNT
    elif action == "chat":
        await query.edit_message_text(f"✉️ در حال چت با کاربر {uid}. لطفاً پیام خود را ارسال کنید.")
        return ADMIN_MESSAGE_USER_INPUT

# Admin: Handle Charge Amount (ConversationHandler)
async def admin_charge_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get('target_user_id')
    
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید مثبت باشد.")
            return ConversationHandler.END
        
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id=?", (amount, uid))
        conn.commit()
        
        await update.message.reply_text(f"✅ {amount} تومان به اعتبار کاربر {uid} اضافه شد.", reply_markup=get_admin_user_mgmt_keyboard())
        try:
            await context.bot.send_message(chat_id=uid, text=f"💰 {amount} تومان به اعتبار شما اضافه شد.")
        except Exception as e:
            print(f"Error sending message to user {uid}: {e}")

    except ValueError:
        await update.message.reply_text("❌ مبلغ عددی نامعتبر است.")
    
    return ConversationHandler.END

# Admin: Handle Deduct Amount (ConversationHandler)
async def admin_deduct_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get('target_user_id')
    
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید مثبت باشد.")
            return ConversationHandler.END
        
        cursor.execute("UPDATE users SET credit = credit - ? WHERE id=?", (amount, uid))
        conn.commit()
        
        await update.message.reply_text(f"✅ {amount} تومان از اعتبار کاربر {uid} کسر شد.", reply_markup=get_admin_user_mgmt_keyboard())
        try:
            await context.bot.send_message(chat_id=uid, text=f"➖ {amount} تومان از اعتبار شما کسر شد.")
        except Exception as e:
            print(f"Error sending message to user {uid}: {e}")

    except ValueError:
        await update.message.reply_text("❌ مبلغ عددی نامعتبر است.")
    
    return ConversationHandler.END

# Admin: Handle Chat Message Input (ConversationHandler)
async def admin_message_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_uid = context.user_data.get('target_user_id')
    message = update.message.text
    
    try:
        await context.bot.send_message(chat_id=target_uid, text=f"💬 پاسخ از ادمین:\n{message}")
        await update.message.reply_text("✅ پیام شما ارسال شد.", reply_markup=get_admin_user_mgmt_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام به کاربر: {e}")
    
    return ConversationHandler.END

# Admin: List users (Approve/Reject)
async def list_pending_and_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT id, username, phone_number, full_name, device_type FROM users WHERE is_approved=0")
    users = cursor.fetchall()
    
    if not users:
        await query.edit_message_text("✅ کاربر در انتظار تأیید/رد وجود ندارد.")
        return

    # Send messages to the admin chat directly
    for uid, uname, phone, name, device in users:
        btn_approve = InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{uid}")
        btn_reject = InlineKeyboardButton("❌ رد", callback_data=f"reject_{uid}")
        btn_chat = InlineKeyboardButton("✉️ چت", callback_data=f"chat_user_{uid}")
        
        keyboard = InlineKeyboardMarkup([[btn_approve, btn_reject, btn_chat]])
        
        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"درخواست از: @{uname} | ID: {uid}\nنام: {name or 'نامشخص'}\nشماره: {phone or 'نامشخص'}\nدستگاه: {device or 'نامشخص'}", 
            reply_markup=keyboard
        )
    await query.edit_message_text("درخواست‌های کاربران در انتظار تأیید/رد به صورت پیام‌های جداگانه ارسال شدند.")

# Admin: Handle Approve/Reject/Chat callbacks (for pending users)
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if '_' not in query.data:
        return

    action, uid_str = query.data.split("_")
    uid = int(uid_str)
    
    if action == "approve":
        cursor.execute("UPDATE users SET is_approved=1 WHERE id=?", (uid,))
        conn.commit()
        await query.edit_message_text(f"✅ کاربر {uid} تأیید شد.")
        await context.bot.send_message(chat_id=uid, text="اکانت شما توسط ادمین تأیید شد. اکنون می‌توانید از خدمات استفاده کنید.", reply_markup=get_main_inline_keyboard(False))
    
    elif action == "reject":
        cursor.execute("UPDATE users SET is_approved=0 WHERE id=?", (uid,)) 
        conn.commit()
        await query.edit_message_text(f"❌ کاربر {uid} رد شد.")
        await context.bot.send_message(chat_id=uid, text="متاسفانه درخواست شما توسط ادمین رد شد. لطفاً با پشتیبانی تماس بگیرید.")

    elif action == "chat_user":
        # We start a conversation specifically for admin to message this user
        context.user_data['target_user_id'] = uid
        await query.edit_message_text(f"✉️ در حال چت با کاربر {uid}. لطفاً پیام خود را ارسال کنید.")
        return ADMIN_MESSAGE_USER_INPUT
    
    elif action == "send_service":
        return await admin_send_service_to_user(update, context)

# Admin: Add Service (ConversationHandler)
async def save_service_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s_type = context.user_data["servicetype"]
    is_file_flag = 0 
    content_to_save = None

    if update.message.document: 
        content_to_save = update.message.document.file_id 
        is_file_flag = 1
        await update.message.reply_text(f"✅ فایل شما با File ID: `{content_to_save}` ذخیره شد.", parse_mode='Markdown', reply_markup=get_admin_service_mgmt_keyboard())
    elif update.message.text: 
        content_to_save = update.message.text.strip()
        is_file_flag = 0
        await update.message.reply_text("✅ سرویس متنی/لینک ذخیره شد.", reply_markup=get_admin_service_mgmt_keyboard())
    else: 
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فایل یا متن/لینک ارسال کنید.")
        return ConversationHandler.END 

    if content_to_save:
        # We use REPLACE INTO to either insert or update existing service content
        cursor.execute("REPLACE INTO services (type, content, is_file) VALUES (?, ?, ?)", (s_type, content_to_save, is_file_flag))
        conn.commit()
    return ConversationHandler.END 

# Admin: Add Discount Code (ConversationHandler)
async def save_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        code, val = update.message.text.strip().split()
        cursor.execute("INSERT OR REPLACE INTO codes (code, value) VALUES (?, ?)", (code, int(val)))
        conn.commit()
        await update.message.reply_text("✅ کد اضافه شد.", reply_markup=get_admin_discount_mgmt_keyboard())
    except:
        await update.message.reply_text("❌ فرمت اشتباه.", reply_markup=get_admin_discount_mgmt_keyboard())
    return ConversationHandler.END

# Admin: Remove Discount Code (ConversationHandler)
async def admin_remove_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    cursor.execute("DELETE FROM codes WHERE code=?", (code,))
    if cursor.rowcount > 0:
        conn.commit()
        await update.message.reply_text(f"✅ کد تخفیف {code} با موفقیت حذف شد.", reply_markup=get_admin_discount_mgmt_keyboard())
    else:
        await update.message.reply_text("❌ کد تخفیف یافت نشد.", reply_markup=get_admin_discount_mgmt_keyboard())
    return ConversationHandler.END

# Admin: Broadcast (ConversationHandler)
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    cursor.execute("SELECT id FROM users")
    for (uid,) in cursor.fetchall():
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e: 
            print(f"Error sending broadcast to {uid}: {e}")
            continue
    await update.message.reply_text("📢 پیام ارسال شد.", reply_markup=get_admin_message_mgmt_keyboard())
    return ConversationHandler.END

# Admin: Send Service to User (triggered by admin action via inline button)
async def admin_send_service_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, uid_str = query.data.split("_")
    uid = int(uid_str)
    
    context.user_data['target_user_id'] = uid
    
    await context.bot.send_message(
        chat_id=ADMIN_ID, 
        text=f"لطفاً فایل یا متن سرویس را برای کاربر {uid} ارسال کنید:"
    )
    return ADMIN_ADD_SERVICE_CONTENT_TO_USER

async def receive_service_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_uid = context.user_data.get('target_user_id')
    
    if not target_uid:
        await update.message.reply_text("❌ خطایی رخ داد. کاربر هدف مشخص نیست. لطفاً مجدداً تلاش کنید.")
        return ConversationHandler.END
    
    if update.message.document: # Admin sent a file
        content_to_send = update.message.document.file_id
        try:
            await context.bot.send_document(chat_id=target_uid, document=content_to_send, caption="✅ فایل سرویس شما:")
            await update.message.reply_text("✅ فایل سرویس با موفقیت برای کاربر ارسال شد.", reply_markup=get_admin_user_mgmt_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال فایل به کاربر: {e}")
            
    elif update.message.text: # Admin sent a text/link
        content_to_send = update.message.text.strip()
        try:
            await context.bot.send_message(chat_id=target_uid, text=f"✅ سرویس شما:\n{content_to_send}")
            await update.message.reply_text("✅ سرویس متنی با موفقیت برای کاربر ارسال شد.", reply_markup=get_admin_user_mgmt_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال پیام به کاربر: {e}")
            
    else:
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فایل یا متن/لینک ارسال کنید.")
        return ADMIN_ADD_SERVICE_CONTENT_TO_USER
        
    return ConversationHandler.END 

# Admin: Service Price Update (Button-based selection)
async def admin_set_price_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT type FROM services")
    services = cursor.fetchall()
    
    if not services:
        await query.edit_message_text("❌ سرویسی برای تعیین قیمت وجود ندارد.")
        return
    
    keyboard = []
    for service_type, in services:
        keyboard.append([InlineKeyboardButton(service_type, callback_data=f"set_price_for_{service_type}")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=ADMIN_SERVICE_MGMT_MENU)])
    
    await query.edit_message_text("💰 لطفاً سرویس مورد نظر برای تعیین قیمت را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_set_price_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("set_price_for_", "")
    context.user_data['service_type_to_price'] = service_type
    
    await query.edit_message_text(f"لطفاً قیمت جدید (به تومان) برای سرویس '{service_type}' را وارد کنید:")
    return ADMIN_SET_PRICE_AMOUNT

async def admin_set_price_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_type = context.user_data.get('service_type_to_price')
    
    try:
        price = int(update.message.text)
        
        cursor.execute("UPDATE services SET price=? WHERE type=?", (price, service_type))
        conn.commit()
        
        await update.message.reply_text(f"✅ قیمت سرویس '{service_type}' به {price:,} تومان به‌روز شد.", reply_markup=get_admin_service_mgmt_keyboard())
    
    except ValueError:
        await update.message.reply_text("❌ مبلغ عددی نامعتبر است.")
    
    return ConversationHandler.END

# Admin: Bot Statistics
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT COUNT(id) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(id) FROM users WHERE is_approved=1")
    approved_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(id) FROM users WHERE is_approved=0")
    pending_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(credit) FROM users")
    total_credit = cursor.fetchone()[0] or 0

    stats_message = f"""📊 آمار ربات:
👥 تعداد کل کاربران: {total_users}
✅ کاربران تأیید شده: {approved_users}
⏳ کاربران در انتظار تأیید: {pending_users}
💰 مجموع اعتبار کاربران: {total_credit:,} تومان
"""
    await query.edit_message_text(stats_message, reply_markup=get_admin_main_inline_keyboard())

# Admin: Purchase Requests (Implemented)
async def admin_purchase_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT id, user_id, amount, description, timestamp, status FROM purchase_requests WHERE status='pending' ORDER BY timestamp DESC")
    requests = cursor.fetchall()
    
    if not requests:
        await query.edit_message_text("✅ درخواست خرید در حال انتظار وجود ندارد.", reply_markup=get_admin_main_inline_keyboard())
        return

    await query.edit_message_text("📝 درخواست‌های خرید در حال انتظار:")
    
    for req_id, user_id, amount, desc, timestamp, status in requests:
        # Fetch username for display
        cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
        username = cursor.fetchone()[0] if cursor.fetchone() else "نامشخص"
        
        request_info = (
            f"ID درخواست: {req_id}\n"
            f"کاربر: @{username} (ID: {user_id})\n"
            f"مبلغ: {amount:,} تومان\n"
            f"توضیحات: {desc}\n"
            f"زمان: {timestamp}"
        )
        
        # Buttons for actions on this request
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ تأیید و شارژ", callback_data=f"admin_approve_purchase_{req_id}"),
                InlineKeyboardButton("❌ رد درخواست", callback_data=f"admin_reject_purchase_{req_id}")
            ]
        ])
        
        await context.bot.send_message(chat_id=ADMIN_ID, text=request_info, reply_markup=keyboard)

    await context.bot.send_message(chat_id=ADMIN_ID, text="بازگشت به پنل مدیریت:", reply_markup=get_admin_main_inline_keyboard())

# Admin: Handle Purchase Request actions
async def admin_purchase_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action_type, action, req_id_str = query.data.split('_')
    req_id = int(req_id_str)
    
    cursor.execute("SELECT user_id, amount, status FROM purchase_requests WHERE id=?", (req_id,))
    request_data = cursor.fetchone()
    
    if not request_data:
        await query.edit_message_text("❌ درخواست یافت نشد یا قبلاً پردازش شده است.")
        return
        
    user_id, amount, status = request_data
    
    if status != 'pending':
        await query.edit_message_text(f"❌ این درخواست قبلاً {status} شده است.")
        return

    if action == "approve":
        # Charge user's credit
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id=?", (amount, user_id))
        # Update request status
        cursor.execute("UPDATE purchase_requests SET status='approved' WHERE id=?", (req_id,))
        conn.commit()
        
        await query.edit_message_text(f"✅ درخواست خرید {req_id} تأیید و کاربر {user_id} به مبلغ {amount:,} تومان شارژ شد.")
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✅ درخواست افزایش اعتبار شما به مبلغ {amount:,} تومان تأیید و اعتبار شما شارژ شد.")
        except Exception as e:
            print(f"Error notifying user {user_id} about purchase approval: {e}")

    elif action == "reject":
        cursor.execute("UPDATE purchase_requests SET status='rejected' WHERE id=?", (req_id,))
        conn.commit()
        
        await query.edit_message_text(f"❌ درخواست خرید {req_id} رد شد.")
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ متاسفانه درخواست افزایش اعتبار شما رد شد. لطفاً با پشتیبانی تماس بگیرید.")
        except Exception as e:
            print(f"Error notifying user {user_id} about purchase rejection: {e}")

# Admin: View Support Messages (Implemented)
async def admin_view_support_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT id, user_id, message, timestamp FROM support_messages ORDER BY timestamp DESC LIMIT 10")
    messages = cursor.fetchall()
    
    if not messages:
        await query.edit_message_text("✉️ پیام پشتیبانی جدیدی وجود ندارد.", reply_markup=get_admin_message_mgmt_keyboard())
        return

    await query.edit_message_text("✉️ آخرین پیام‌های پشتیبانی:")
    
    for msg_id, user_id, message, timestamp in messages:
        cursor.execute("SELECT username FROM users WHERE id=?", (user_id,))
        username = cursor.fetchone()[0] if cursor.fetchone() else "نامشخص"
        
        msg_info = (
            f"**پیام از:** @{username} (ID: {user_id})\n"
            f"**زمان:** {timestamp}\n"
            f"**پیام:** {message}"
        )
        
        # Button to chat with the user
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ پاسخ به کاربر", callback_data=f"admin_chat_user_{user_id}")]
        ])
        
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg_info, reply_markup=keyboard, parse_mode='Markdown')

    await context.bot.send_message(chat_id=ADMIN_ID, text="بازگشت به مدیریت پیام‌ها:", reply_markup=get_admin_message_mgmt_keyboard())

# --- Main setup ---

def main():
    application = Application.builder().token(TOKEN).build()

    # --- User Commands ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("myinfo", myinfo))
    application.add_handler(CommandHandler("admin", admin))
    
    # --- User Conversation Handlers (Registration, Discount, Transfer, Topup, Support) ---
    
    # Registration Conversation Handler
    register_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_PHONE: [MessageHandler(filters.CONTACT, register_phone_number)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_DEVICE: [CallbackQueryHandler(register_device, pattern="^register_device_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True
    )
    application.add_handler(register_conv_handler)
    
    # User actions triggered by main_callback_handler
    application.add_handler(CallbackQueryHandler(main_callback_handler, pattern="^(get_app|activate_discount|my_credit|transfer_credit|my_status|get_service|topup|support_message|admin_panel|main_menu|cancel_transfer|cancel_topup|cancel_support)$"))
    
    # App selection callback handler
    application.add_handler(CallbackQueryHandler(send_app_link, pattern="^app_"))
    
    # Service request callback handler
    application.add_handler(CallbackQueryHandler(send_service_request_to_admin, pattern="^request_service_"))
    
    # Discount Conversation Handler
    discount_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ASK_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_discount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(discount_conv_handler)

    # Transfer Conversation Handler
    transfer_conv_handler = ConversationHandler(
        entry_points=[],
        states={
            ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_transfer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(transfer_conv_handler)

    # Topup Conversation Handler
    topup_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ASK_TOPUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_topup_request)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(topup_conv_handler)
    
    # Support Message Conversation Handler
    support_message_conv_handler = ConversationHandler(
        entry_points=[],
        states={ SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_support_message)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(support_message_conv_handler)

    # --- Admin Handlers ---
    
    # Admin Panel Navigation (handles admin_user_mgmt, admin_service_mgmt, etc.)
    application.add_handler(CallbackQueryHandler(admin_panel_navigation_handler, pattern="^admin_"))
    
    # Admin Approval/Rejection/Chat/Send Service Callbacks (for pending users)
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(approve_|reject_|chat_user_|send_service_)"))
    
    # Admin User List Actions (Charge/Deduct/Chat)
    application.add_handler(CallbackQueryHandler(admin_user_action_handler, pattern="^admin_(charge|deduct|chat)_user_"))

    # Admin Purchase Request Actions
    application.add_handler(CallbackQueryHandler(admin_purchase_action, pattern="^admin_(approve|reject)_purchase_"))

    # Admin Conversation Handlers
    
    # Admin Add Service (Manual addition to DB)
    admin_add_service_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_ADD_SERVICE: [MessageHandler(filters.TEXT | filters.Document & ~filters.COMMAND, save_service_admin)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_add_service_conv_handler)

    # Admin Add Discount
    admin_add_discount_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_ADD_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_discount_code)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_add_discount_conv_handler)

    # Admin Remove Discount
    admin_remove_discount_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_REMOVE_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_remove_discount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_remove_discount_conv_handler)

    # Admin Broadcast
    admin_broadcast_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_broadcast_conv_handler)

    # Admin sends service to user flow 
    admin_send_service_flow_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_send_service_to_user, pattern="^send_service_")],
        states={ ADMIN_ADD_SERVICE_CONTENT_TO_USER: [MessageHandler(filters.TEXT | filters.Document & ~filters.COMMAND, receive_service_content)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_send_service_flow_handler)

    # Admin set service price (Button-based)
    admin_set_price_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_price_select_service, pattern="^set_price_for_")],
        states={ ADMIN_SET_PRICE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_price_amount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_set_price_conv_handler)
    
    # Admin charge user amount (Button-based)
    admin_charge_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_CHARGE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_charge_amount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_charge_conv_handler)

    # Admin deduct user amount (Button-based)
    admin_deduct_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_DEDUCT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_deduct_amount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_deduct_conv_handler)

    # Admin message user input (Button-based)
    admin_message_user_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_MESSAGE_USER_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_user_input)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_message_user_conv_handler)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
