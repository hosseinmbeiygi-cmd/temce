@echo off
REM ============================================
REM  اسکریپت تست دستی BrsApi (Windows)
REM ============================================

setlocal enabledelayedexpansion

set API_KEY=Bk7JvdJZBHJ9DMhzeuTfWjwqYy1wMsif
set BASE_URL=https://Api.BrsApi.ir

echo.
echo ============================================
echo   ابزار تست دستی BrsApi.ir
echo ============================================
echo.

REM نمایش منو
echo 1. تست اتصال API
echo 2. دریافت کامودیتی‌ها
echo 3. دریافت ارزهای دیجیتال
echo 4. دریافت طلا و سکه
echo 5. دریافت نرخ ارز
echo 6. دریافت تمام داده‌ها
echo.
set /p choice="انتخاب کنید (1-6): "

if "%choice%"=="1" goto test_connection
if "%choice%"=="2" goto get_commodity
if "%choice%"=="3" goto get_crypto
if "%choice%"=="4" goto get_gold
if "%choice%"=="5" goto get_currency
if "%choice%"=="6" goto get_all
goto end

:test_connection
echo.
echo در حال تست اتصال...
curl -s "%BASE_URL%/Market/Commodity.php?key=%API_KEY%" | python -m json.tool
goto end

:get_commodity
echo.
echo در حال دریافت کامودیتی‌ها...
curl -s "%BASE_URL%/Market/Commodity.php?key=%API_KEY%" > commodity.json
python -c "import json; data=json.load(open('commodity.json')); print(f'تعداد: {len(data.get(\"data\", []))}'); [print(f'  - {item.get(\"name\")}: {item.get(\"price\")}') for item in data.get('data', [])[:5]]"
goto end

:get_crypto
echo.
echo در حال دریافت ارزهای دیجیتال...
curl -s "%BASE_URL%/Market/Cryptocurrency.php?key=%API_KEY%" > crypto.json
python -c "import json; data=json.load(open('crypto.json')); print(f'تعداد: {len(data.get(\"data\", []))}'); [print(f'  - {item.get(\"name\")}: {item.get(\"price_usd\")}$') for item in data.get('data', [])[:5]]"
goto end

:get_gold
echo.
echo در حال دریافت طلا و سکه...
curl -s "%BASE_URL%/Market/Coin.php?key=%API_KEY%" > gold.json
python -c "import json; data=json.load(open('gold.json')); print(f'تعداد: {len(data.get(\"data\", []))}'); [print(f'  - {item.get(\"name\")}: {item.get(\"price\")}') for item in data.get('data', [])[:5]]"
goto end

:get_currency
echo.
echo در حال دریافت نرخ ارز...
curl -s "%BASE_URL%/Market/Currency.php?key=%API_KEY%" > currency.json
python -c "import json; data=json.load(open('currency.json')); print(f'تعداد: {len(data.get(\"data\", []))}'); [print(f'  - {item.get(\"name\")}: {item.get(\"price\")}') for item in data.get('data', [])[:5]]"
goto end

:get_all
echo.
echo در حال دریافت تمام داده‌ها...
echo 1. کامودیتی‌ها...
curl -s "%BASE_URL%/Market/Commodity.php?key=%API_KEY%" > commodity.json
echo 2. ارزهای دیجیتال...
curl -s "%BASE_URL%/Market/Cryptocurrency.php?key=%API_KEY%" > crypto.json
echo 3. طلا و سکه...
curl -s "%BASE_URL%/Market/Coin.php?key=%API_KEY%" > gold.json
echo 4. نرخ ارز...
curl -s "%BASE_URL%/Market/Currency.php?key=%API_KEY%" > currency.json
echo.
echo تمام داده‌ها دریافت شد!
dir *.json
goto end

:end
echo.
echo پایان عملیات
pause
