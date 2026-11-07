FROM python:3.12

# جلوگیری از تولید pyc و بافر خروجی
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# تنظیم میرور داخلی PyPI لیارا
ENV PIP_INDEX_URL=https://package-mirror.liara.ir/repository/pypi/simple
ENV PIP_TRUSTED_HOST=package-mirror.liara.ir

# به‌روزرسانی پکیج‌ها و نصب ابزارهای پایه
RUN apt-get update && apt-get install -y \
    locales \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# تنظیم زبان فارسی
RUN echo "fa_IR.UTF-8 UTF-8" > /etc/locale.gen && locale-gen

ENV LANG=fa_IR.UTF-8
ENV LC_ALL=fa_IR.UTF-8

COPY requirements.txt .

RUN pip install --upgrade pip setuptools

RUN pip install --no-cache-dir -r requirements.txt

# CMD ["gunicorn", "--config", "gunicorn-cfg.py", "core.wsgi"]
