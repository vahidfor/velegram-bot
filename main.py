import os
import sqlite3
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from telegram.error import TelegramError

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# Ensure ADMIN_ID is set in .env and is an integer
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", 0))

# Define conversation states
(
    REGISTER_PHONE, REGISTER_NAME, REGISTER_DEVICE,
    ASK_DISCOUNT,
    ASK_TARGET, ASK_AMOUNT,
    ASK_TOPUP,
    ADMIN_ADD_SERVICE, ADMIN_ADD_DISCOUNT, ADMIN_BROADCAST,
    SUPPORT_MESSAGE, ADMIN_ADD_SERVICE_CONTENT_TO_USER,
    ADMIN_SET_SERVICE_PRICE, ADMIN_REMOVE_DISCOUNT,
    ADMIN_SET_PRICE_AMOUNT, ADMIN_CHARGE_AMOUNT, ADMIN_DEDUCT_AMOUNT,
    ADMIN_MESSAGE_USER_INPUT, ADMIN_VIEW_SUPPORT_MESSAGES_LIST,
    ADMIN_BROADCAST_MESSAGE_INPUT, ADMIN_BROADCAST_CONFIRMATION,
    ADMIN_APPROVE_REJECT_USER_ID, ADMIN_PROCESS_PURCHASE_REQUEST,
    ADMIN_PANEL_STATE # New state for the admin panel
) = range(26) # Increased range

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

# --- Database Setup ---
def setup_database():
    # Create users table
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
    # Create codes table for discount codes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS codes (
        code TEXT PRIMARY KEY,
        value INTEGER
    )
    """)
    # Create services table with price
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS services (
        type TEXT PRIMARY KEY,
        content TEXT,
        is_file INTEGER DEFAULT 0,
        price INTEGER DEFAULT 0
    )
    """)
    # Create support messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        timestamp TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    # Create purchase requests table
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

def get_main_inline_keyboard(user_telegram_id: int) -> InlineKeyboardMarkup:
    is_admin = (user_telegram_id == ADMIN_ID)
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

def get_admin_main_inline_keyboard() -> InlineKeyboardMarkup:
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

def get_admin_user_mgmt_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🧾 لیست کاربران در انتظار", callback_data="admin_pending_users")],
        [InlineKeyboardButton("👥 لیست تمام کاربران", callback_data="admin_all_users")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_service_mgmt_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ افزودن سرویس", callback_data="admin_add_service_type")],
        [InlineKeyboardButton("💰 تعیین قیمت سرویس", callback_data="admin_set_price_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_discount_mgmt_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="admin_add_discount_menu")],
        [InlineKeyboardButton("❌ حذف کد تخفیف", callback_data="admin_remove_discount_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_message_mgmt_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast_menu")],
        [InlineKeyboardButton("✉️ پیام‌های پشتیبانی", callback_data="admin_view_support_messages_menu")],
        [InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- User Commands and Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END

    user = update.effective_user
    if user is None:
        await update.message.reply_text("خطا در شناسایی کاربر. لطفا دوباره تلاش کنید.")
        return ConversationHandler.END

    await update.message.reply_text("خوش آمدید.", reply_markup=ReplyKeyboardRemove())

    cursor.execute("SELECT full_name FROM users WHERE id=?", (user.id,))
    user_info = cursor.fetchone()

    if not user_info or user_info[0] is None:
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
            (user.id, user.username)
        )
        conn.commit()
        return await ask_phone_number(update, context)

    await update.message.reply_text(
        "سلام! به ربات VPN خوش اومدی 👋\n\nلطفاً یک گزینه را انتخاب کنید:",
        reply_markup=get_main_inline_keyboard(user.id))
    return ConversationHandler.END

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None:
        return
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
    if update.effective_user is None or update.message is None:
        return

    cursor.execute("SELECT credit FROM users WHERE id=?", (update.effective_user.id,))
    user_credit = cursor.fetchone()
    if user_credit:
        await update.message.reply_text(f"🔢 امتیاز (اعتبار) شما: {user_credit[0]} تومان")
    else:
        await update.message.reply_text("❌ اطلاعات شما یافت نشد. لطفاً /start را بزنید.")

async def myinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_to_edit = update.message or (update.callback_query and update.callback_query.message)
    if user is None or message_to_edit is None:
        return

    cursor.execute(
        "SELECT credit, discount_used, is_approved, phone_number, full_name, device_type FROM users WHERE id=?",
        (user.id,)
    )
    user_data = cursor.fetchone()

    if user_data:
        credit, discount_used, approved, phone_number, full_name, device_type = user_data
        response_text = f"""👤 @{user.username or 'نامشخص'}
🆔 `{user.id}`
📝 نام: {full_name or 'نامشخص'}
📞 شماره تلفن: {phone_number or 'نامشخص'}
💻 دستگاه: {device_type or 'نامشخص'}
💳 اعتبار: {credit} تومان
🎁 کد تخفیف: {"استفاده شده" if discount_used else "استفاده نشده"}
✅ وضعیت: {"تأیید شده" if approved else "در انتظار تأیید"}
"""
        reply_markup = get_main_inline_keyboard(user.id)
        if update.callback_query:
            await message_to_edit.edit_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await message_to_edit.reply_text(response_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        error_text = "❌ کاربر یافت نشد. لطفاً دوباره /start را بزنید."
        if update.callback_query:
            await message_to_edit.edit_text(error_text)
        else:
            await message_to_edit.reply_text(error_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if user is None:
        return ConversationHandler.END

    message_to_edit = update.message or (update.callback_query and update.callback_query.message)
    if message_to_edit:
        text = "عملیات لغو شد."
        reply_markup = get_main_inline_keyboard(user.id)
        if update.callback_query:
            await message_to_edit.edit_text(text, reply_markup=reply_markup)
        else:
            await message_to_edit.reply_text(text, reply_markup=reply_markup)
    return ConversationHandler.END

# --- Registration Flow ---

async def ask_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message is None:
        return ConversationHandler.END
    keyboard = [[KeyboardButton("ارسال شماره تلفن", request_contact=True)]]
    await update.message.reply_text(
        "لطفاً برای ثبت‌نام، شماره تلفن خود را با کلیک روی دکمه زیر ارسال کنید:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return REGISTER_PHONE

async def register_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    user_id = update.effective_user.id
    phone_number = None

    if update.message.contact:
        contact = update.message.contact
        if contact.user_id == user_id:
            phone_number = contact.phone_number
        else:
            await update.message.reply_text("❌ لطفاً شماره تلفن خودتان را ارسال کنید.")
            return REGISTER_PHONE
    elif update.message.text:
        phone_text = update.message.text.strip()
        if phone_text.startswith(('+98', '0098', '09')) and len(phone_text.replace('+', '').replace(' ', '')) >= 10:
            phone_number = phone_text
        else:
            await update.message.reply_text("❌ شماره تلفن وارد شده معتبر نیست. لطفاً مجدداً تلاش کنید.")
            return REGISTER_PHONE

    if phone_number:
        cursor.execute("UPDATE users SET phone_number=? WHERE id=?", (phone_number, user_id))
        conn.commit()
        await update.message.reply_text(
            "شماره تلفن شما ثبت شد. حالا لطفاً نام و نام خانوادگی خود را وارد کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return REGISTER_NAME
    else:
        await update.message.reply_text("❌ لطفاً شماره تلفن خود را از طریق دکمه ارسال کنید.")
        return REGISTER_PHONE

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None or update.message.text is None:
        return ConversationHandler.END

    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    cursor.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user_id))
    conn.commit()

    device_keyboard = [
        [InlineKeyboardButton("📱 اندروید", callback_data="register_device_android")],
        [InlineKeyboardButton("🍏 آیفون", callback_data="register_device_iphone")],
        [InlineKeyboardButton("🖥 ویندوز", callback_data="register_device_windows")]
    ]
    await update.message.reply_text(
        "نام شما ثبت شد. حالا نوع دستگاه خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(device_keyboard)
    )
    return REGISTER_DEVICE

async def register_device(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.from_user is None or query.data is None or query.message is None:
        return ConversationHandler.END

    await query.answer()
    user = query.from_user
    device_map = {
        "register_device_android": "اندروید",
        "register_device_iphone": "آیفون",
        "register_device_windows": "ویندوز"
    }
    device_type = device_map.get(query.data)

    if device_type:
        # User is set to NOT approved by default. Admin must approve.
        cursor.execute(
            "UPDATE users SET device_type=?, is_approved=0 WHERE id=?",
            (device_type, user.id)
        )
        conn.commit()

        # Admin notification with approve/reject buttons
        cursor.execute("SELECT phone_number, full_name FROM users WHERE id=?", (user.id,))
        registered_user = cursor.fetchone()
        if registered_user:
            phone_number, full_name = registered_user
            admin_message = f"""🎉 کاربر جدید ثبت‌نام کرد و در انتظار تأیید است:
نام: {full_name or 'نامشخص'}
نام کاربری: @{user.username or 'نامشخص'}
ID: `{user.id}`
شماره تلفن: {phone_number or 'نامشخص'}
دستگاه: {device_type}"""
            
            approval_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ تأیید", callback_data=f"approve_user_{user.id}"),
                    InlineKeyboardButton("❌ رد", callback_data=f"reject_user_{user.id}")
                ]
            ])
            await context.bot.send_message(
                ADMIN_ID,
                admin_message,
                reply_markup=approval_keyboard,
                parse_mode='Markdown'
            )

        await query.message.edit_text(
            f"ثبت‌نام شما با موفقیت انجام شد ({device_type}).\n"
            "درخواست شما برای ادمین ارسال شد. پس از تأیید، می‌توانید از امکانات ربات استفاده کنید.",
            reply_markup=get_main_inline_keyboard(user.id)
        )
        return ConversationHandler.END
    return REGISTER_DEVICE

# --- User Actions Handlers ---

async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.from_user is None or query.data is None or query.message is None:
        return ConversationHandler.END

    user_id = query.from_user.id
    await query.answer()

    data = query.data
    message_obj = query.message

    # Check if user is approved for certain actions
    cursor.execute("SELECT is_approved FROM users WHERE id=?", (user_id,))
    user_status = cursor.fetchone()
    is_approved = user_status and user_status[0] == 1

    if data in ["get_service", "transfer_credit", "topup"] and not is_approved and user_id != ADMIN_ID:
        await message_obj.edit_text(
            "⛔ حساب شما هنوز توسط ادمین تأیید نشده است. لطفاً منتظر بمانید.",
            reply_markup=get_main_inline_keyboard(user_id)
        )
        return ConversationHandler.END

    if data == "main_menu":
        await message_obj.edit_text("منوی اصلی:", reply_markup=get_main_inline_keyboard(user_id))
        return ConversationHandler.END
    elif data == "get_app":
        await get_app(update, context)
        return ConversationHandler.END
    elif data == "activate_discount":
        await message_obj.edit_text("🎁 لطفاً کد تخفیف را وارد کنید:")
        return ASK_DISCOUNT
    elif data == "my_credit":
        cursor.execute("SELECT credit FROM users WHERE id=?", (user_id,))
        credit_result = cursor.fetchone()
        await message_obj.edit_text(
            f"💳 اعتبار شما: {credit_result[0] if credit_result else 0} تومان",
            reply_markup=get_main_inline_keyboard(user_id)
        )
        return ConversationHandler.END
    elif data == "transfer_credit":
        await message_obj.edit_text("🔁 لطفاً ID عددی دریافت‌کننده را وارد کنید:")
        return ASK_TARGET
    elif data == "my_status":
        await myinfo(update, context)
        return ConversationHandler.END
    elif data == "get_service":
        await get_service(update, context)
        return ConversationHandler.END
    elif data == "topup":
        await message_obj.edit_text("💳 مقدار و توضیحات پرداخت خود را وارد کنید:\nمثال: 100000 - کارت به کارت")
        return ASK_TOPUP
    elif data == "support_message":
        await message_obj.edit_text("✉️ لطفاً پیام خود را برای پشتیبانی ارسال کنید:")
        return SUPPORT_MESSAGE
    
    # The 'admin_panel' callback is handled by a separate ConversationHandler
    # so it is not processed here.

    return ConversationHandler.END

# --- User Side Functionality ---

async def get_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("📱 اندروید", callback_data="app_android"),
            InlineKeyboardButton("🍏 آیفون", callback_data="app_iphone")
        ],
        [
            InlineKeyboardButton("🖥 ویندوز", callback_data="app_windows"),
            InlineKeyboardButton("❓ راهنمای اتصال", callback_data="app_guide")
        ],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    await query.message.edit_text(
        "لطفاً دستگاه خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_app_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or query.from_user is None or query.message is None:
        return
    
    await query.answer()
    selected_option = query.data
    message_obj = query.message

    links = {
        "app_android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
        "app_iphone": "https://apps.apple.com/app/openvpn-connect/id590379981",
        "app_windows": "https://openvpn.net/client-connect-vpn-for-windows/",
        "app_guide": "لینک راهنمای شما در اینجا قرار می‌گیرد یا می‌توانید مانند قبل عکس‌ها را ارسال کنید."
    }

    if selected_option in links:
        await message_obj.edit_text(links[selected_option])
    # The photo guide part can be added here if needed, similar to the original code.
    
    await context.bot.send_message(
        query.from_user.id,
        "بازگشت به منوی اصلی:",
        reply_markup=get_main_inline_keyboard(query.from_user.id)
    )

async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    await query.answer()
    
    cursor.execute("SELECT type, price FROM services")
    services = cursor.fetchall()
    keyboard = []
    if services:
        for service_type, price in services:
            price_text = f" ({price:,} تومان)" if price > 0 else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{service_type}{price_text}",
                    callback_data=f"request_service_{service_type}"
                )
            ])
    else:
        keyboard.append([InlineKeyboardButton("سرویسی برای ارائه موجود نیست", callback_data="no_service")])
    
    keyboard.append([InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")])
    await query.message.edit_text("کدام سرویس را می‌خواهید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_service_request_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.from_user is None or query.data is None or query.message is None:
        return
    
    await query.answer()
    user = query.from_user
    service_key = query.data.replace("request_service_", "")

    msg_for_admin = (f"🌐 درخواست سرویس جدید از:\n"
                     f"کاربر: @{user.username or 'نامشخص'}\n"
                     f"ID: `{user.id}`\n"
                     f"سرویس: {service_key}")
    
    # This part can be enhanced to handle service delivery automatically or manually
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin, parse_mode='Markdown')
    await query.message.edit_text("✅ درخواست شما به ادمین ارسال شد. لطفاً منتظر بمانید.")

# --- Discount related functions ---
async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None or update.message.text is None:
        return ConversationHandler.END

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
        try:
            # Use a transaction for atomicity
            cursor.execute("UPDATE users SET credit = credit + ?, discount_used = 1 WHERE id=?", (value, user_id))
            cursor.execute("DELETE FROM codes WHERE code=?", (code,))
            conn.commit()
            await update.message.reply_text(f"✅ تبریک! مبلغ {value} تومان به اعتبار شما اضافه شد.")
            await context.bot.send_message(
                ADMIN_ID,
                f"کاربر با ID `{user_id}` کد تخفیف `{code}` را با موفقیت استفاده کرد."
            )
        except sqlite3.Error as e:
            conn.rollback()
            await update.message.reply_text("خطایی در سیستم رخ داد. لطفاً بعداً تلاش کنید.")
            print(f"Database error during discount application: {e}")
    else:
        await update.message.reply_text("❌ کد تخفیف وارد شده معتبر نیست.")

    await update.message.reply_text("منوی اصلی:", reply_markup=get_main_inline_keyboard(user_id))
    return ConversationHandler.END

# --- Admin Panel ---

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.message is None or query.from_user.id != ADMIN_ID:
        return ConversationHandler.END
    
    await query.answer()
    await query.message.edit_text(
        "🎛 به پنل مدیریت خوش آمدید.",
        reply_markup=get_admin_main_inline_keyboard()
    )
    return ADMIN_PANEL_STATE

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.message is None or query.from_user.id != ADMIN_ID:
        return ConversationHandler.END

    await query.answer()
    data = query.data
    message_obj = query.message

    if data == ADMIN_USER_MGMT_MENU:
        await message_obj.edit_text("👥 مدیریت کاربران:", reply_markup=get_admin_user_mgmt_keyboard())
    elif data == ADMIN_SERVICE_MGMT_MENU:
        await message_obj.edit_text("🛰 مدیریت سرویس‌ها:", reply_markup=get_admin_service_mgmt_keyboard())
    elif data == ADMIN_DISCOUNT_MGMT_MENU:
        await message_obj.edit_text("🎁 مدیریت کدهای تخفیف:", reply_markup=get_admin_discount_mgmt_keyboard())
    elif data == ADMIN_MESSAGE_MGMT_MENU:
        await message_obj.edit_text("📢 مدیریت پیام‌ها:", reply_markup=get_admin_message_mgmt_keyboard())
    elif data == "admin_panel": # Back to admin main menu
        await message_obj.edit_text("🎛 پنل مدیریت:", reply_markup=get_admin_main_inline_keyboard())
    # Add handlers for other admin menus (stats, purchase reqs, etc.) here
    
    return ADMIN_PANEL_STATE


async def admin_process_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None or query.message is None or query.from_user.id != ADMIN_ID:
        return

    await query.answer()
    data_parts = query.data.split('_')
    action = data_parts[0]  # 'approve' or 'reject'
    user_id_to_process = int(data_parts[2])

    if action == "approve":
        cursor.execute("UPDATE users SET is_approved=1 WHERE id=?", (user_id_to_process,))
        conn.commit()
        await query.message.edit_text(f"✅ کاربر با ID `{user_id_to_process}` با موفقیت تأیید شد.")
        try:
            await context.bot.send_message(
                chat_id=user_id_to_process,
                text="🎉 حساب شما توسط ادمین تأیید شد! اکنون می‌توانید از تمام امکانات ربات استفاده کنید."
            )
        except TelegramError as e:
            await query.message.reply_text(f"⚠️ کاربر را مسدود کرده یا ربات را ترک کرده است. ({e})")

    elif action == "reject":
        # You might want to delete the user or just leave them as not approved
        # For now, we just notify the admin.
        await query.message.edit_text(f"❌ درخواست کاربر با ID `{user_id_to_process}` رد شد.")
        try:
            await context.bot.send_message(
                chat_id=user_id_to_process,
                text="متاسفانه حساب شما توسط ادمین تایید نشد."
            )
        except TelegramError:
            pass # User might have blocked the bot

# --- Main Function ---
def main() -> None:
    """Start the bot."""
    if not TOKEN:
        raise ValueError("No TELEGRAM_BOT_TOKEN found in environment variables")
        
    # First, setup the database
    setup_database()

    application = Application.builder().token(TOKEN).build()

    # Conversation handler for registration
    register_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_PHONE: [MessageHandler(filters.CONTACT | filters.TEXT & ~filters.COMMAND, register_phone_number)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_DEVICE: [CallbackQueryHandler(register_device, pattern="^register_device_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Conversation handler for user actions initiated from main menu
    user_actions_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(main_callback_handler)],
        states={
            ASK_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_discount)],
            # Add other states like ASK_TARGET, ASK_AMOUNT, ASK_TOPUP here
        },
        fallbacks=[CommandHandler("cancel", cancel), CallbackQueryHandler(cancel, pattern="^cancel_")],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )
    
    # Conversation handler for the admin panel
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin, pattern="^admin_panel$")],
        states={
            ADMIN_PANEL_STATE: [CallbackQueryHandler(admin_menu_handler)]
            # Add states for deeper admin menus here
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(register_conv)
    application.add_handler(user_actions_conv)
    application.add_handler(admin_conv)

    # Handlers that are not part of conversations
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("score", score))
    application.add_handler(CommandHandler("myinfo", myinfo))
    
    # Handler for app links
    application.add_handler(CallbackQueryHandler(send_app_link, pattern="^app_"))
    # Handler for service requests
    application.add_handler(CallbackQueryHandler(send_service_request_to_admin, pattern="^request_service_"))
    # Handler for admin approving/rejecting users directly from notification
    application.add_handler(CallbackQueryHandler(admin_process_approval, pattern="^(approve|reject)_user_"))


    print("Bot started...")
    application.run_polling()


if __name__ == "__main__":
    main()
