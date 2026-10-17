# خانه‌یاب — Intent-Aware Home Search

یک MVP فول‌استک برای جست‌وجو، رتبه‌بندی و مقایسه‌ی آگهی‌های مسکن در شهرهای مختلف ایران. تمام داده‌ها و قیمت‌ها ساختگی‌اند و از وب‌سایت‌های املاک چیزی crawl نمی‌شود.

## اجرا با Docker Compose

نیازمندی: Docker Engine و Docker Compose plugin.

```bash
cp .env.example .env  # optional; leave blank to run without AI
# from this directory
docker compose up --build
```

سپس برنامه در [http://localhost:8081](http://localhost:8081) در دسترس است. وضعیت backend: [http://localhost:8081/api/health](http://localhost:8081/api/health) و مستندات API: [http://localhost:8081/docs](http://localhost:8081/docs).

پایگاه داده در volume دائمی `khoneyab_data` نگه‌داری می‌شود. seed فقط وقتی اجرا می‌شود که جدول آگهی‌ها خالی باشد؛ راه‌اندازی مجدد، داده‌ها را از نو تولید نمی‌کند. برای حذف کامل دیتای آزمایشی:

```bash
docker compose down -v
```

## اجرای توسعه‌ای بدون Docker

Backend (از پوشه‌ی `backend`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (در ترمینال جدا، از پوشه‌ی `frontend`):

```bash
npm install
npm run dev
```

Vite روی `http://localhost:5173` اجرا می‌شود. در حالت توسعه می‌توان از مرورگر به endpoint مستقیم backend درخواست زد؛ برای تجربه‌ی یکپارچه، Docker Compose روش پیشنهادی است.

## AI اختیاری

هر tier را می‌توان مستقل به یک endpoint سازگار با OpenAI Chat Completions وصل کرد. آدرس باید base URL باشد، مثلاً `http://host.docker.internal:8080/v1`، نه لزوماً URL کامل `chat/completions`.

- `AI_CHEAP_BASE_URL`, `AI_CHEAP_MODEL`, `AI_CHEAP_API_KEY`: تفسیر پرس‌وجوی طبیعی
- `AI_STANDARD_BASE_URL`, `AI_STANDARD_MODEL`, `AI_STANDARD_API_KEY`: اصلاح جست‌وجو در پیام‌های بعدی
- `AI_PREMIUM_BASE_URL`, `AI_PREMIUM_MODEL`, `AI_PREMIUM_API_KEY`: خلاصه‌ی متنی مقایسه، فقط در صورت درخواست کاربر

در Linux، برای دسترسی کانتینر backend به سرویسی روی میزبان، در صورت نیاز به سرویس backend این بخش را در compose اضافه کن:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

کلیدها فقط سمت backend استفاده می‌شوند. اگر endpoint/model تنظیم نشده باشد یا درخواست AI شکست بخورد، parser قاعده‌محور و قالب‌های توضیحی همچنان کار می‌کنند.

## قابلیت‌های MVP

- خرید و اجاره در ۱۰ شهر ایرانی با محله‌های متعدد
- جست‌وجوی فارسی، استخراج معیارهای رایج بدون LLM، فیلترهای معمول و مرتب‌سازی
- رتبه‌بندی شفاف بر اساس ترجیحات، دلیل تطبیق و ترجیحات برآورده‌نشده
- نتایج نزدیک در بخشی جداگانه، فقط اگر نتیجه‌ی سخت‌گیرانه‌ای پیدا نشود؛ شهر و نوع معامله هرگز بی‌صدا تغییر نمی‌کنند
- گروه‌بندی ۲۵ آگهی تکراری تعبیه‌شده در بین ۱۸۵ آگهی مصنوعی
- جزئیات هر ملک، نقشه‌ی Leaflet/OpenStreetMap با موقعیت تقریبی، مقایسه‌ی ۲ تا ۳ ملک
- علاقه‌مندی‌ها و جست‌وجوهای ذخیره‌شده در `localStorage` مرورگر
- SQLite پایدار و داده‌های ساختگی تکرارپذیر

## تست‌ها

```bash
cd backend
pip install -r requirements-dev.txt
PYTHONPATH=. pytest -q
```

## محدودیت‌های عمدی

- داده‌ها، قیمت‌ها، تاریخ‌ها و موقعیت‌ها برای دمو ساخته شده‌اند؛ نباید به‌عنوان اطلاعات واقعی بازار تفسیر شوند.
- نقشه از کاشی‌های OpenStreetMap استفاده می‌کند و برای نمایش tileها به اتصال اینترنت مرورگر نیاز دارد. فهرست نتایج بدون نقشه هم در دسترس است.
- ذخیره‌ها مختص مرورگر فعلی‌اند و با حساب کاربری یا دستگاه دیگر همگام نمی‌شوند.
- جست‌وجو و رتبه‌بندی هسته‌ی اپ deterministic است؛ LLM فیلتر نهایی، امتیاز یا واقعیت‌های آگهی را تعیین نمی‌کند.
