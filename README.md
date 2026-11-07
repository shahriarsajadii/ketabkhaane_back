# کتابخانه‌ی شخصی — Backend (Django + DRF)

مدیریت کتاب‌ها (چند نسخه، آدرس قفسه‌ی هر نسخه، عکس، یادداشت، دسته‌بندی)، ورود کاربران مجاز،
ورود دسته‌جمعی از اکسل و خروجی اکسل.

## راه‌اندازی

```bash
python -m venv venv && source venv/bin/activate      # ویندوز: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # و SECRET_KEY را عوض کن

python manage.py makemigrations --check   # باید «No changes detected» بدهد
# (مایگریشن‌های publishers/authors/books دستی نوشته شده‌اند)
python manage.py migrate
python manage.py createsuperuser                      # اولین کاربر = مدیر
python manage.py runserver
```

تست‌ها: `python manage.py test`
(فقط تست‌های اکسل بدون Django: `python -m unittest books.tests.test_excel`)

Swagger/Postman لازم نیست؛ همه‌ی اندپوینت‌ها در پایین آمده‌اند. پنل `/admin/` هم برای کارهای اضطراری فعال است.

## ساختار

```
core/        تنظیمات، ResponseHelper، MethodPermission، mixin های ویو، exception handler، احراز هویت cookie
users/       مدل User (لاگین با username) + لاگین/خروج/refresh + مدیریت کاربران (مدیر)
categories/  دسته‌بندی‌ها (مسطح)
books/       Book + BookCopy (هر نسخه یک آدرس) + عکس + اکسل
  excel.py     خواندن/نوشتن xlsx (مستقل از Django)
  services.py  sync آدرس‌ها + منطق ایمپورت
```

## مدل داده

| مدل | فیلدها |
|---|---|
| `Book` | `title`*, `authors`* (M2M), `translator`, `publisher` (FK، اختیاری)، `publish_year`, `isbn`, `note`, `image`, `categories` (M2M) |
| `Publisher` | `name` (یکتا)*, `image` |
| `Author` | `name` (یکتا)*, `description`, `image` |
| `BookCopy` | `book`, `address`* — **هر رکورد = یک نسخه‌ی فیزیکی** |
| `Category` | `title` (یکتا) |
| `User` | `username`, `name`, `is_active`, `is_staff` (=مدیر) |

\* اجباری. «تعداد» ذخیره نمی‌شود؛ همیشه برابر تعداد `BookCopy` های کتاب است (هیچ‌وقت با آدرس‌ها ناهماهنگ نمی‌شود).

## قالب پاسخ‌ها (همان پروژه‌ی نمونه)

```json
{ "is_success": true, "message": "...", "data": {...}, "pagination": {...}, "errors": {...} }
```
خطای اعتبارسنجی: `400` با `errors: { "field": ["پیام"] }`. توکن نامعتبر/منقضی: `401` با `status_code: "INVALID_TOKEN"`.

## اندپوینت‌ها (همه با پیشوند `/api`)

### Auth و کاربران
| متد | مسیر | توضیح |
|---|---|---|
| POST | `/users/login/` | `{username, password}` → cookie های HttpOnly ست می‌شود |
| POST | `/users/token/refresh/` | با cookie ی refresh، access جدید می‌سازد |
| POST | `/users/logout/` | refresh را باطل و cookie ها را پاک می‌کند |
| GET/PATCH | `/users/me/` | پروفایل خود کاربر (فقط `name`) |
| POST | `/users/me/password/` | `{old_password, new_password, confirm_password}` |
| GET/POST | `/users/` | لیست/ساخت کاربر — **فقط مدیر** (`?search=`, `?is_active=`) |
| GET/PATCH/DELETE | `/users/detail/<id>/` | **فقط مدیر** |

### دسته‌بندی‌ها
| متد | مسیر | توضیح |
|---|---|---|
| GET | `/categories/` | همه (بدون pagination) + `books_count`؛ `?title=`, `?ordering=` |
| POST | `/categories/` | `{title}` |
| DELETE | `/categories/` | حذف گروهی `{items: [1,2]}` (کتاب‌ها حذف نمی‌شوند) |
| GET/PATCH/DELETE | `/categories/detail/<id>/` | |

### کتاب‌ها
| متد | مسیر | توضیح |
|---|---|---|
| GET | `/books/` | لیست صفحه‌بندی‌شده + فیلتر |
| POST | `/books/` | ساخت (JSON) |
| DELETE | `/books/` | حذف گروهی `{items: [1,2]}` |
| GET/PATCH/DELETE | `/books/detail/<id>/` | |
| POST/DELETE | `/books/<id>/image/` | آپلود (multipart، فیلد `image`) / حذف عکس |
| POST | `/books/import/` | آپلود اکسل (multipart، فیلد `file`) |
| GET | `/books/import/template/` | فایل نمونه‌ی اکسل |
| GET | `/books/export/` | خروجی اکسل (با همان فیلترهای لیست) |

**فیلترهای لیست و خروجی:** `search` (نام/نویسنده/مترجم/ناشر/شابک/یادداشت/آدرس) · `title` · `author` ·
`translator` · `publisher` · `address` · `category=1,4` · `ordering=title|-created_at|...` · `page` · `page_size`

**ساخت کتاب:**
```json
POST /api/books/
{
  "title": "یادداشت‌های زیرزمینی",
  "author": "فئودور داستایفسکی",
  "translator": "نام مترجم",
  "count": 3,
  "addresses": ["قفسه ۲ دیوار چپ", "قفسه ۲ دیوار چپ", "قفسه ۵ کنار پنجره"],
  "categories": [1, 4],
  "publisher": "", "publish_year": 1398, "isbn": "", "note": "یادداشت من"
}
```
- `addresses` اجباری است و **برای هر نسخه یک آدرس** (به‌ترتیب).
- `count` اختیاری است؛ نباشد = تعداد آدرس‌ها (پس برای یک کتاب با یک آدرس، پیش‌فرض ۱ است). اگر بفرستی و با تعداد آدرس‌ها برابر نباشد خطا می‌گیری.
- در `PATCH`، اگر `addresses` بفرستی کل لیست آدرس‌ها جایگزین می‌شود (کم/زیاد شدن تعداد نسخه‌ها = کم/زیاد کردن آدرس‌ها).
  تغییر `count` بدون ارسال `addresses` پذیرفته نمی‌شود.
- ثبت کتاب تکراری (همان نام + نویسنده + مترجم + ناشر) رد می‌شود؛ باید تعداد/آدرس‌های همان کتاب ویرایش شود.

## اکسل

**ورود دسته‌جمعی** — `POST /api/books/import/` (فقط `.xlsx`، حداکثر ۵ مگابایت و ۲۰۰۰ ردیف). ابتدا فایل نمونه را از `/books/import/template/` بگیر.

| نام کتاب* | نویسنده* | مترجم* | تعداد | آدرس‌ها* | ناشر | سال انتشار | شابک | دسته‌بندی‌ها | یادداشت |
|---|---|---|---|---|---|---|---|---|---|

- آدرس‌ها: با `|` یا `؛` یا Alt+Enter جدا کن (برای هر نسخه یک آدرس).
  اگر تعداد > ۱ و فقط یک آدرس نوشته شود، همان آدرس برای همه‌ی نسخه‌ها ثبت می‌شود.
- دسته‌بندی‌ها: با `،` یا `,` یا `|` جدا کن؛ دسته‌های ناموجود خودکار ساخته می‌شوند.
- ارقام فارسی (۱۲۳) و حروف عربی (ي ك) پذیرفته و نرمال می‌شوند.
- **پیش‌فرض همه‌یا‌هیچ است:** اگر حتی یک ردیف خطا داشته باشد چیزی ثبت نمی‌شود و `errors.rows` شماره‌ی ردیف و دلیل هر خطا را برمی‌گرداند.
  با `?skip_invalid=true` ردیف‌های سالم ثبت و ردیف‌های خراب در `data.failed` گزارش می‌شوند.

**خروجی** — `GET /api/books/export/` همان ستون‌ها را می‌دهد، پس فایل خروجی را می‌شود دوباره ایمپورت کرد (مثلاً برای انتقال به سیستم دیگر).
متن‌ها طوری نوشته می‌شوند که اگر با `=` شروع شوند در اکسل به‌عنوان فرمول اجرا نشوند.

## نکات اتصال به Vue

- axios: `withCredentials: true` (توکن‌ها در cookie ی HttpOnly هستند؛ در localStorage نگه نداره).
- اگر پاسخی `401` با `status_code === "INVALID_TOKEN"` بود، یک‌بار `POST /users/token/refresh/` بزن و درخواست اصلی را تکرار کن؛ اگر refresh هم `401` شد، برو صفحه‌ی لاگین.
- دانلود اکسل: `axios.get(url, { responseType: "blob", withCredentials: true })`.
- ساخت کتاب با JSON است؛ عکس بعد از ساخت با `POST /books/<id>/image/` (FormData) آپلود می‌شود.
- cookie ها `SameSite=Lax` هستند؛ فرانت و بک باید زیر یک دامنه باشند (مثلاً nginx: `/` → Vue، `/api` و `/media` → Django).
  در سرور واقعی حتماً HTTPS و `AUTH_COOKIE_SECURE=True`.

## دسترسی‌ها

- همه‌ی کاربران واردشده: دسترسی کامل به کتاب‌ها و دسته‌بندی‌ها.
- مدیریت کاربران: فقط `is_staff`/superuser.
- تغییر قواعد: فقط دیکشنری‌های `consts/permissions.py` هر اپ (مثلاً `"DELETE": [IsAuthenticated, IsLibraryManager]`).


### ناشران و نویسنده‌ها (`/publishers/` و `/authors/` — ساختار یکسان)
| متد | مسیر | توضیح |
|---|---|---|
| GET | `/publishers/` | صفحه‌بندی‌شده؛ `?search=`, `?name=`, `?ordering=name\|-books_count`, `?page_size=` |
| POST | `/publishers/` | `{name}` (نویسنده: `{name, description?}`) |
| DELETE | `/publishers/` | حذف گروهی `{items: [...]}` |
| GET/PATCH/DELETE | `/publishers/detail/<id>/` | حذف ناشر کتاب‌ها را نگه می‌دارد؛ نویسنده‌ی دارای کتاب حذف نمی‌شود |
| POST/DELETE | `/publishers/<id>/image/` | multipart `image=<file>` |

فیلترهای کتاب: `?author=3,7`, `?publisher=2`, `?author_name=`, `?publisher_name=`, `?publish_year=`.
