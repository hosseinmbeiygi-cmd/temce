"use client";

import { useState } from "react";
import AppLayout from "@/components/layout/AppLayout";

type Section =
  | "intro"
  | "security"
  | "auth"
  | "order-status"
  | "order-types"
  | "order-sides"
  | "oco-status"
  | "oco-sub-status"
  | "trade"
  | "market"
  | "websocket"
  | "user-ws"
  | "wallet"
  | "margin"
  | "fapi"
  | "fapi-market"
  | "fapi-order"
  | "fapi-position"
  | "fapi-account"
  | "fapi-transfer"
  | "fapi-trades"
  | "fapi-websocket"
  | "errors"
  | "error-fapi"
  | "error-margin";

const sidebarItems: { key: Section; label: string; group?: string }[] = [
  { key: "intro", label: "مقدمه", group: "عمومی" },
  { key: "security", label: "مکانیزم‌های امنیتی", group: "عمومی" },
  { key: "auth", label: "احراز هویت", group: "عمومی" },
  { key: "order-status", label: "وضعیت سفارشات", group: "عمومی" },
  { key: "order-types", label: "نوع سفارشات", group: "عمومی" },
  { key: "order-sides", label: "جهت سفارشات", group: "عمومی" },
  { key: "oco-status", label: "وضعیت سفارش OCO", group: "عمومی" },
  { key: "oco-sub-status", label: "وضعیت سفارشات زیرمجموعه OCO", group: "عمومی" },
  { key: "trade", label: "معامله", group: "اسپات" },
  { key: "market", label: "بازار", group: "اسپات" },
  { key: "websocket", label: "وب سوکت بازار", group: "اسپات" },
  { key: "user-ws", label: "وب سوکت اطلاعات کاربر", group: "اسپات" },
  { key: "wallet", label: "کیف پول", group: "اسپات" },
  { key: "margin", label: "معامله اهرم‌دار", group: "اهرم" },
  { key: "fapi", label: "اهرم حرفه‌ای (FAPI)", group: "FAPI" },
  { key: "fapi-market", label: "بازار FAPI", group: "FAPI" },
  { key: "fapi-order", label: "سفارشات FAPI", group: "FAPI" },
  { key: "fapi-position", label: "پوزیشن FAPI", group: "FAPI" },
  { key: "fapi-account", label: "حساب FAPI", group: "FAPI" },
  { key: "fapi-transfer", label: "انتقال FAPI", group: "FAPI" },
  { key: "fapi-trades", label: "معاملات FAPI", group: "FAPI" },
  { key: "fapi-websocket", label: "وب‌سوکت FAPI", group: "FAPI" },
  { key: "errors", label: "خطاها", group: "خطاها" },
  { key: "error-fapi", label: "خطاهای FAPI", group: "خطاها" },
  { key: "error-margin", label: "خطاهای اهرم‌دار", group: "خطاها" },
];

const groups = [...new Set(sidebarItems.map((i) => i.group))];

function CodeBlock({ children, lang = "python" }: { children: string; lang?: string }) {
  return (
    <pre className="bg-surface-900 border border-surface-700 rounded-lg p-4 text-xs font-mono text-surface-300 overflow-x-auto my-3" dir="ltr">
      <code>{children}</code>
    </pre>
  );
}

function ParamTable({ params }: { params: { name: string; required: string; type: string; desc: string }[] }) {
  return (
    <div className="overflow-x-auto my-3">
      <table className="w-full text-xs border border-surface-700 rounded-lg overflow-hidden">
        <thead>
          <tr className="bg-surface-800 text-surface-400">
            <th className="py-2 px-3 text-right font-medium">پارامتر</th>
            <th className="py-2 px-3 text-right font-medium">الزامی</th>
            <th className="py-2 px-3 text-right font-medium">نوع</th>
            <th className="py-2 px-3 text-right font-medium">توضیحات</th>
          </tr>
        </thead>
        <tbody>
          {params.map((p, i) => (
            <tr key={i} className="border-t border-surface-800 hover:bg-surface-800/50">
              <td className="py-2 px-3 font-mono text-primary-300">{p.name}</td>
              <td className="py-2 px-3">
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${p.required === "بله" ? "bg-accent-rose/20 text-accent-rose" : "bg-surface-700 text-surface-400"}`}>
                  {p.required}
                </span>
              </td>
              <td className="py-2 px-3 font-mono text-surface-400">{p.type}</td>
              <td className="py-2 px-3 text-surface-300">{p.desc}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Endpoint({ method, path, auth }: { method: string; path: string; auth: string }) {
  const colors: Record<string, string> = {
    GET: "bg-accent-emerald/20 text-accent-emerald",
    POST: "bg-primary-600/20 text-primary-400",
    PUT: "bg-yellow-500/20 text-yellow-400",
    DELETE: "bg-accent-rose/20 text-accent-rose",
  };
  return (
    <div className="flex items-center gap-3 my-2 p-3 bg-surface-800/50 rounded-lg border border-surface-700">
      <span className={`px-2 py-1 rounded text-[10px] font-bold ${colors[method] || ""}`}>{method}</span>
      <code className="text-xs font-mono text-surface-300" dir="ltr">{path}</code>
      <span className="text-[10px] text-surface-500 mr-auto">[{auth}]</span>
    </div>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-primary-600/10 border border-primary-600/20 rounded-lg p-3 text-xs text-primary-300 my-3">
      {children}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-bold text-surface-100 mt-8 mb-4 pb-2 border-b border-surface-700">{children}</h2>;
}

function SubTitle({ children }: { children: React.ReactNode }) {
  return <h3 className="text-sm font-semibold text-surface-200 mt-5 mb-2">{children}</h3>;
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-surface-300 leading-6 my-2">{children}</p>;
}

// ═══════════════════════════════════════════════════════════════════
// SECTION CONTENT COMPONENTS
// ═══════════════════════════════════════════════════════════════════

function IntroSection() {
  return (
    <>
      <SectionTitle>مقدمه</SectionTitle>
      <P>به داکیومنت API تبدیل خوش آمدید.</P>
      <P>برای استفاده از API می‌توانید از ماژول پایتونی زیر استفاده نمایید:</P>
      <CodeBlock lang="bash">Tabdeal-Python</CodeBlock>
      <P>API اهرم پیشرفته (FAPI) با پیشوند fapi در مسیرهای جداگانه در دسترس است؛ جزئیات در بخش اهرم پیشرفته (FAPI) آمده است.</P>
    </>
  );
}

function SecuritySection() {
  return (
    <>
      <SectionTitle>امنیت</SectionTitle>
      <SubTitle>مکانیزم‌های امنیتی</SubTitle>
      <ParamTable
        params={[
          { name: "TRADE", required: "—", type: "—", desc: "api-key و signature" },
          { name: "USER", required: "—", type: "—", desc: "api-key" },
          { name: "NONE", required: "—", type: "—", desc: "—" },
        ]}
      />
      <P>برای APIهایی که مکانیزم امنیتی آن‌ها از نوع TRADE باشد، نیاز است تا Headerی با نام X-MBX-APIKEY ارسال شود که مقدار آن، API Key دریافت‌شده از سایت می‌باشد. همچنین لازم است تا پارامترهای ارسالی، با کلید api-secret دریافت‌شده از سایت، رمز شده و تحت عنوان signature در پارامترها ارسال شود.</P>
      <P>برای APIهایی که مکانیزم امنیتی آن‌ها از نوع NONE باشد، نیازی به ارسال هیچ پارامتر اضافه‌ای نیست.</P>
    </>
  );
}

function AuthSection() {
  return (
    <>
      <SectionTitle>احراز هویت</SectionTitle>
      <P>در APIهایی که دارای مکانیزم امنیتی TRADE هستند، برای احراز هویت لازم است تا api-key و api-secret از سایت دریافت شده و به صورتی که در زیر توضیح داده شده، ارسال شوند.</P>
      <P>از طریق این آدرس اقدام به دریافت API Key کنید.</P>
      <P>سپس لازم هست تا api-key دریافت‌شده را به عنوان header درخواست خود به صورت زیر قرار دهید:</P>
      <CodeBlock>X-MBX-APIKEY: your_api_key</CodeBlock>
      <P>شما باید api-key خود را به جای your_api_key بگذارید.</P>
      <P>در ادامه لازم است تا پارامترهای ارسالی را با api-secret رمز کنید. برای این کار باید زمان ارسال درخواست را در فرمت timestamp به انتهای پارامترهای ارسالی اضافه کنید و کل این مجموعه را به ساختار Query String در آورده و آن را با کلید api-secret و با الگوریتم SHA256 و با مکانیزم HMAC رمز کنید. خروجی رشته‌ی رمزشده‌ی بالا را تحت عنوان signature به انتهای پارامترهای ارسالی اضافه کرده و درخواست خود را ارسال کنید.</P>
      <SubTitle>ساختار Query String</SubTitle>
      <CodeBlock>param_1=test_1&param_2=test_2&...&timestamp=1507725176595</CodeBlock>
    </>
  );
}

function OrderStatusSection() {
  return (
    <>
      <SectionTitle>وضعیت سفارشات</SectionTitle>
      <ParamTable
        params={[
          { name: "NEW", required: "—", type: "—", desc: "سفارش ایجاد شده است" },
          { name: "PARTIALLY_FILLED", required: "—", type: "—", desc: "بخشی از سفارش انجام شده است" },
          { name: "FILLED", required: "—", type: "—", desc: "سفارش به طور کامل انجام شده است" },
          { name: "CANCELED", required: "—", type: "—", desc: "سفارش لغو شده است" },
          { name: "REJECTED", required: "—", type: "—", desc: "سفارش رد شده است" },
        ]}
      />
    </>
  );
}

function OrderTypesSection() {
  return (
    <>
      <SectionTitle>نوع سفارشات</SectionTitle>
      <ParamTable
        params={[
          { name: "LIMIT", required: "—", type: "—", desc: "—" },
          { name: "MARKET", required: "—", type: "—", desc: "—" },
          { name: "STOP_LOSS_LIMIT", required: "—", type: "—", desc: "—" },
        ]}
      />
    </>
  );
}

function OrderSidesSection() {
  return (
    <>
      <SectionTitle>جهت سفارشات</SectionTitle>
      <ParamTable
        params={[
          { name: "BUY", required: "—", type: "—", desc: "—" },
          { name: "SELL", required: "—", type: "—", desc: "—" },
        ]}
      />
    </>
  );
}

function OCOStatusSection() {
  return (
    <>
      <SectionTitle>وضعیت سفارش OCO</SectionTitle>
      <ParamTable
        params={[
          { name: "EXECUTING", required: "—", type: "—", desc: "سفارش ایجاد شده یا یکی از سفارشات زیرمجموعه در حال اجراست" },
          { name: "ALL_DONE", required: "—", type: "—", desc: "سفارش تکمیل شده و سفارشات زیرمجموعه پایان یافته‌اند" },
          { name: "REJECT", required: "—", type: "—", desc: "سفارش رد و یا لغو شده است" },
        ]}
      />
    </>
  );
}

function OCOSubStatusSection() {
  return (
    <>
      <SectionTitle>وضعیت سفارشات زیرمجموعه OCO</SectionTitle>
      <ParamTable
        params={[
          { name: "RESPONSE", required: "—", type: "—", desc: "یکی از سفارشات زیرمجموعه لغو و یا رد شده است" },
          { name: "EXEC_STARTED", required: "—", type: "—", desc: "سفارشات زیرمجموعه فعال شده‌اند و یا وضعیتشان تغییر کرده است" },
          { name: "ALL_DONE", required: "—", type: "—", desc: "سفارشات زیرمجموعه تکمیل شده و پایان یافته‌اند" },
        ]}
      />
    </>
  );
}

function TradeSection() {
  return (
    <>
      <SectionTitle>معامله</SectionTitle>

      {/* ── ارسال سفارش ── */}
      <SubTitle>ارسال سفارش</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/api/v1/order" auth="TRADE" />
      <SubTitle>ارسال درخواست با کتابخانه پایتونی:</SubTitle>
      <CodeBlock>{`from tabdeal.spot import Spot
from tabdeal.enums import OrderSides, OrderTypes

client = Spot(api_key, api_secret)

order = client.new_order(
    symbol='BTCIRT',
    side=OrderSides.SELL,
    type=OrderTypes.MARKET,
    quantity="0.001"
)`}</CodeBlock>
      <SubTitle>پارامترها:</SubTitle>
      <ParamTable
        params={[
          { name: "side", required: "بله", type: "ENUM", desc: "SELL یا BUY" },
          { name: "type", required: "بله", type: "ENUM", desc: "MARKET یا LIMIT یا STOP_LOSS_LIMIT" },
          { name: "quantity", required: "بله", type: "DECIMAL", desc: "تعداد خرید یا فروش" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "newClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش که توسط کاربر تولید شده" },
          { name: "price", required: "خیر", type: "DECIMAL", desc: "قیمت خرید یا فروش" },
          { name: "stopPrice", required: "خیر", type: "DECIMAL", desc: "قیمت فعال شدن سفارش" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>با تغییر type مربوط به سفارش، ملزومات سفارش تغییر می‌کند و ممکن است پارامترهای price یا stopPrice الزامی شوند.</li>
          <li>ارسال symbol یا tabdealSymbol الزامی است. تفاوت این دو در علامت _ بین علامت ارزهاست.</li>
          <li>در صورتی که type سفارش LIMIT باشد، ارسال price الزامی است.</li>
          <li>در صورتی که type سفارش STOP_LOSS_LIMIT باشد، ارسال stopPrice الزامی است.</li>
          <li>پارامتر newClientOrderId شناسه‌ی یکتا برای سفارش است و توسط کاربر تولید می‌شود که برای هر کاربر باید یکتا باشد.</li>
        </ul>
      </Note>

      {/* ── جستجوی سفارش ── */}
      <SubTitle>جستجوی سفارش</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/order" auth="TRADE" />
      <CodeBlock>{`from tabdeal.spot import Spot

client = Spot(api_key, api_secret)

order = client.get_order(
    symbol='BTC_IRT',
    order_id=140
)`}</CodeBlock>
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "orderId", required: "خیر", type: "LONG", desc: "id سفارش" },
          { name: "origClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش که توسط کاربر تولید شده" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>ارسال symbol یا tabdealSymbol الزامی است.</li>
          <li>ارسال فقط یکی از پارامترهای orderId یا origClientOrderId الزامی است.</li>
        </ul>
      </Note>

      {/* ── سفارشات باز ── */}
      <SubTitle>سفارشات باز</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/openOrders" auth="TRADE" />
      <CodeBlock>{`from tabdeal.spot import Spot

client = Spot(api_key, api_secret)

orders = client.get_open_orders(symbol='BTCIRT')`}</CodeBlock>
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
        ]}
      />
      <Note>در صورتی که symbol یا tabdealSymbol را ارسال نکنید، سفارشات باز تمام بازارها را برمی‌گرداند.</Note>

      {/* ── سفارشات باز صفحه بندی شده ── */}
      <SubTitle>سفارشات باز صفحه بندی شده</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/paginatedOpenOrders" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "page", required: "خیر", type: "INT", desc: "صفحه مورد نظر" },
          { name: "page_size", required: "خیر", type: "INT", desc: "تعداد آیتم در هر صفحه" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>حداکثر مقدار page_size برابر با مقدار 500 می باشد.</li>
          <li>مقدار پیش‌فرض page برابر یک و page_size برابر 100 است.</li>
        </ul>
      </Note>

      {/* ── لغو سفارش ── */}
      <SubTitle>لغو سفارش</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/order" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "orderId", required: "خیر", type: "LONG", desc: "id سفارش" },
          { name: "origClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش که توسط کاربر تولید شده" },
        ]}
      />

      {/* ── تمام سفارشات ── */}
      <SubTitle>تمام سفارشات</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/allOrders" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "startTime", required: "خیر", type: "LONG", desc: "سفارشات بعد از این زمان" },
          { name: "endTime", required: "خیر", type: "LONG", desc: "سفارشات قبل از این زمان" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>پارامتر limit حداکثر 1000 می‌تواند باشد و مقدار پیش‌فرض 50 است.</li>
          <li>ارسال symbol یا tabdealSymbol الزامی نیست.</li>
        </ul>
      </Note>

      {/* ── تمام سفارشات منقضی نشده ── */}
      <SubTitle>تمام سفارشات منقضی نشده</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/nonExpiredAllOrders" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "startTime", required: "خیر", type: "LONG", desc: "سفارشات بعد از این زمان" },
          { name: "endTime", required: "خیر", type: "LONG", desc: "سفارشات قبل از این زمان" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>پارامتر startTime نباید کمتر از یک روز گذشته باشد.</li>
          <li>حداکثر مقدار limit برابر با 1000 می باشد.</li>
        </ul>
      </Note>

      {/* ── لغو تمام سفارشات باز ── */}
      <SubTitle>لغو تمام سفارشات باز</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/openOrders" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
        ]}
      />
      <Note>
        <ul className="list-disc pr-4 space-y-1">
          <li>این درخواست سفارشات OCO را نیز شامل می‌شود و آن‌ها را هم لغو می‌کند.</li>
          <li>در صورتی که در لغو یکی از سفارشات مشکلی به وجود آید، لغو سایر سفارشات انجام نمی‌شود.</li>
        </ul>
      </Note>

      {/* ── ارسال سفارش OCO ── */}
      <SubTitle>ارسال سفارش OCO</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/api/v1/order/oco" auth="TRADE" />
      <ParamTable
        params={[
          { name: "side", required: "بله", type: "ENUM", desc: "SELL یا BUY" },
          { name: "quantity", required: "بله", type: "DECIMAL", desc: "تعداد خرید یا فروش" },
          { name: "price", required: "بله", type: "DECIMAL", desc: "قیمت سفارش limit" },
          { name: "stopPrice", required: "بله", type: "DECIMAL", desc: "قیمت فعالسازی سفارش stop" },
          { name: "stopLimitPrice", required: "بله", type: "DECIMAL", desc: "قیمت سفارش stop" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "listClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش list" },
          { name: "limitClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش limit" },
          { name: "stopClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش stop" },
        ]}
      />

      {/* ── جستجوی سفارش OCO ── */}
      <SubTitle>جستجوی سفارش OCO</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/orderList" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "orderListId", required: "خیر", type: "LONG", desc: "id سفارش" },
          { name: "origClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش که توسط کاربر تولید شده" },
        ]}
      />

      {/* ── سفارشات باز OCO ── */}
      <SubTitle>سفارشات باز OCO</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/openOrderList" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
        ]}
      />

      {/* ── لغو سفارش OCO ── */}
      <SubTitle>لغو سفارش OCO</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/orderList" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "orderListId", required: "خیر", type: "LONG", desc: "id سفارش" },
          { name: "listClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش که توسط کاربر تولید شده" },
        ]}
      />

      {/* ── تمام سفارشات OCO ── */}
      <SubTitle>تمام سفارشات OCO</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/allOrderList" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "startTime", required: "خیر", type: "LONG", desc: "سفارشات بعد از این زمان" },
          { name: "endTime", required: "خیر", type: "LONG", desc: "سفارشات قبل از این زمان" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />

      {/* ── معاملات من ── */}
      <SubTitle>معاملات من</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/myTrades" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "startTime", required: "خیر", type: "LONG", desc: "معاملات بعد از این زمان" },
          { name: "endTime", required: "خیر", type: "LONG", desc: "معاملات قبل از این زمان" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
          { name: "orderId", required: "خیر", type: "INT", desc: "معاملاتی که سفارش آنها این id را دارند" },
        ]}
      />

      {/* ── اطلاعات کاربر ── */}
      <SubTitle>اطلاعات کاربر</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/account" auth="TRADE" />
      <CodeBlock>{`from tabdeal.spot import Spot

client = Spot(api_key, api_secret)

account = client.account()`}</CodeBlock>
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
        ]}
      />
    </>
  );
}

function MarketSection() {
  return (
    <>
      <SectionTitle>بازار</SectionTitle>

      <SubTitle>لیست سفارشات</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/depth" auth="NONE" />
      <CodeBlock>{`from tabdeal.spot import Spot

client = Spot()

order_book = client.depth(symbol='BTCUSDT', limit=1)`}</CodeBlock>
      <ParamTable
        params={[
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />
      <Note>پارامتر limit حداکثر 5000 می‌تواند باشد و مقدار پیش‌فرض 50 است.</Note>

      <SubTitle>لیست معاملات</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/trades" auth="NONE" />
      <ParamTable
        params={[
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />

      <SubTitle>لیست بازارها</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/exchangeInfo" auth="NONE" />
      <CodeBlock>{`from tabdeal.spot import Spot

client = Spot()

market = client.exchange_info(symbol='BTC_IRT')
markets = client.exchange_info(symbols=['BTCIRT', 'MANAUSDT'])`}</CodeBlock>
      <ParamTable
        params={[
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "symbols", required: "خیر", type: "STRING", desc: "نام بازارها" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "tabdealSymbols", required: "خیر", type: "STRING", desc: "نام بازارها با _" },
          { name: "limit", required: "خیر", type: "INT", desc: "خروجی تنها به این تعداد بازگردانده میشود" },
        ]}
      />

      <SubTitle>تست اتصال به سرور</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/ping" auth="NONE" />
      <CodeBlock>{`client = Spot()
client.ping()`}</CodeBlock>

      <SubTitle>گرفتن زمان سرور</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/time" auth="NONE" />
      <CodeBlock>{`client = Spot()
client.time()`}</CodeBlock>
    </>
  );
}

function WebsocketSection() {
  return (
    <>
      <SectionTitle>وب سوکت بازار</SectionTitle>
      <P>آدرس اتصال: <code className="text-primary-300" dir="ltr">wss://api1.tabdeal.org/stream/</code></P>
      <SubTitle>سفارشات (OrderBook)</SubTitle>
      <P>قالب topic: <code className="text-primary-300" dir="ltr">[symbol]@depth@2000ms</code></P>
      <CodeBlock>{`{
  "method": "SUBSCRIBE",
  "params": ["usdtirt@depth@2000ms"],
  "id": 1
}`}</CodeBlock>
      <CodeBlock lang="python">{`from tabdeal.websocket_client import SpotWebsocketClient

def handler(message):
    print(message)

tabdeal_ws = SpotWebsocketClient()
tabdeal_ws.market_order_book(
    symbol="bnbusdt",
    id=1,
    callback=handler,
)`}</CodeBlock>
      <Note>لیست سفارشات بازار هر 2 ثانیه یکبار توسط این topic ارسال می‌شود.</Note>
    </>
  );
}

function UserWebsocketSection() {
  return (
    <>
      <SectionTitle>وب سوکت اطلاعات کاربر</SectionTitle>
      <P>آدرس: <code className="text-primary-300" dir="ltr">wss://api1.tabdeal.org/stream/streams={"{listen_key}"}</code></P>
      <P>هر کاربر یک listenKey دارد که فقط 60 دقیقه معتبر است.</P>

      <SubTitle>دریافت listenKey</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/api/v1/userDataStream" auth="USER" />

      <SubTitle>به‌روزرسانی listenKey</SubTitle>
      <Endpoint method="PUT" path="https://api1.tabdeal.org/api/v1/userDataStream" auth="USER" />

      <SubTitle>حذف listenKey</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/userDataStream" auth="USER" />

      <SubTitle>اطلاعات دریافتی (سفارش)</SubTitle>
      <CodeBlock>{`{
  "e": "executionReport",
  "E": 1499405658658,
  "s": "ETHBTC",
  "c": "mUvoqJxFIILMdfAW5iGSOW",
  "S": "BUY",
  "o": "LIMIT",
  "f": "GTC",
  "q": "1.00000000",
  "p": "0.10264410",
  "P": "0.00000000",
  "g": -1,
  "x": "NEW",
  "X": "NEW",
  "i": 4293153,
  "l": "0.00000000",
  "z": "0.00000000",
  "L": "0.00000000",
  "n": "0",
  "N": null,
  "t": -1,
  "m": false,
  "O": 1499405658657
}`}</CodeBlock>
      <P>پارامتر x در خروجی برای نشان دادن عملیات انجام‌شده روی سفارش است.</P>
      <ParamTable
        params={[
          { name: "NEW", required: "—", type: "—", desc: "سفارش ایجاد شد" },
          { name: "CANCELED", required: "—", type: "—", desc: "سفارش لغو شد" },
          { name: "TRADE", required: "—", type: "—", desc: "روی سفارش، معامله صورت گرفت" },
          { name: "TRIGGERRED", required: "—", type: "—", desc: "سفارش STOP فعال شد" },
        ]}
      />
    </>
  );
}

function WalletSection() {
  return (
    <>
      <SectionTitle>کیف پول</SectionTitle>
      <SubTitle>لیست دارایی‌ها</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/asset/get-funding-asset" auth="TRADE" />
      <ParamTable
        params={[
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "asset", required: "خیر", type: "STRING", desc: "نماد مربوط به دارایی مورد نظر" },
        ]}
      />
    </>
  );
}

function MarginSection() {
  return (
    <>
      <SectionTitle>معامله اهرم‌دار</SectionTitle>

      <SubTitle>جابه‌جایی</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/r/api/v1/margin/isolated/transfer" auth="TRADE" />
      <CodeBlock>{`from tabdeal.isolated_margin import IsolatedMargin

client = IsolatedMargin(api_key, api_secret)

transfer = client.transfer(
    asset='BTC',
    amount="0.01",
    trans_from="ISOLATED_MARGIN",
    trans_to="SPOT",
    symbol="BTCUSDT"
)`}</CodeBlock>
      <ParamTable
        params={[
          { name: "asset", required: "بله", type: "STRING", desc: "نماد مربوط به دارایی مورد نظر" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "transFrom", required: "بله", type: "ENUM", desc: "ISOLATED_MARGIN یا SPOT" },
          { name: "transTo", required: "بله", type: "ENUM", desc: "ISOLATED_MARGIN یا SPOT" },
          { name: "amount", required: "بله", type: "DECIMAL", desc: "مقدار جابه‌جایی" },
        ]}
      />

      <SubTitle>تاریخچه جابه‌جایی</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/margin/isolated/transfer" auth="TRADE" />

      <SubTitle>سفارشات باز معامله اهرم‌دار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/margin/openOrders" auth="TRADE" />

      <SubTitle>لغو تمام سفارشات باز معامله اهرم‌دار</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/margin/openOrders" auth="TRADE" />

      <SubTitle>تمام سفارشات معامله اهرم‌دار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/margin/allOrders" auth="TRADE" />

      <SubTitle>ارسال سفارش معامله اهرم‌دار</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/api/v1/margin/order" auth="TRADE" />
      <CodeBlock>{`from tabdeal.isolated_margin import IsolatedMargin
from tabdeal.enums import OrderSides, OrderTypes

client = IsolatedMargin(api_key, api_secret)

order = client.create_margin_order(
    symbol='BTCIRT',
    side=OrderSides.BUY,
    type=OrderTypes.MARKET,
    quantity="0.001",
    borrow_quantity="4500000"
)`}</CodeBlock>
      <ParamTable
        params={[
          { name: "side", required: "بله", type: "ENUM", desc: "SELL یا BUY" },
          { name: "type", required: "بله", type: "ENUM", desc: "MARKET یا LIMIT یا STOP_LOSS_LIMIT" },
          { name: "quantity", required: "بله", type: "DECIMAL", desc: "تعداد خرید یا فروش" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته ی رمز شده" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام بازار" },
          { name: "tabdealSymbol", required: "خیر", type: "STRING", desc: "نام بازار با _" },
          { name: "newClientOrderId", required: "خیر", type: "STRING", desc: "id سفارش یکتا" },
          { name: "price", required: "خیر", type: "DECIMAL", desc: "قیمت خرید یا فروش" },
          { name: "stopPrice", required: "خیر", type: "DECIMAL", desc: "قیمت فعال شدن سفارش" },
          { name: "borrow_quantity", required: "بله", type: "DECIMAL", desc: "مقدار اعتبار دریافتی" },
        ]}
      />
      <Note>پارامتر borrow_quantity میتواند به واحد ارز اول یا دوم بازار باشد.</Note>

      <SubTitle>جستجوی سفارش معامله اهرم‌دار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/api/v1/margin/order" auth="TRADE" />

      <SubTitle>لغو سفارش معامله اهرم‌دار</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/api/v1/margin/order" auth="TRADE" />

      <SubTitle>ارزهای معامله اهرم‌دار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/allAssets" auth="TRADE" />

      <SubTitle>تاریخچه بازپرداخت</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/repay" auth="TRADE" />

      <SubTitle>تاریخچه بهره</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/interestHistory" auth="TRADE" />

      <SubTitle>اطلاعات حساب معامله اهرم‌دار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/isolated/account" auth="TRADE" />

      <SubTitle>تاریخچه لیکویید شدن‌ها</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/forceLiquidationRec" auth="TRADE" />

      <SubTitle>تاریخچه گرفتن اعتبار</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/api/v1/margin/loan" auth="TRADE" />
    </>
  );
}

function FAPISection() {
  return (
    <>
      <SectionTitle>اهرم حرفه‌ای (FAPI)</SectionTitle>
      <P>API اهرم حرفه‌ای با پیشوند fapi در دسترس است و از نظر ساختار شبیه به API فیوچر Binance می‌باشد. هر بات یا اپلیکیشنی که برای Binance نوشته‌اید، با SDK صرافی تبدیل نیز کار خواهد کرد.</P>
      <Note>در صورت غیرفعال بودن اهرم حرفه‌ای برای کاربر، خطای 1207 با پیام «Futures not active» بازگردانده می‌شود.</Note>

      <SubTitle>تست اتصال به سرور</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/ping" auth="NONE" />

      <SubTitle>زمان سرور</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/time" auth="NONE" />

      <SubTitle>اطلاعات بازارهای اهرم حرفه ای</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/exchangeInfo" auth="NONE" />
    </>
  );
}

function FAPIMarketSection() {
  return (
    <>
      <SectionTitle>بازار FAPI</SectionTitle>

      <SubTitle>اردربوک (عمق بازار)</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/depth" auth="NONE" />
      <ParamTable
        params={[
          { name: "symbol", required: "بله", type: "STRING", desc: "نام نماد" },
          { name: "limit", required: "خیر", type: "INT", desc: "تعداد سطوح (پیش‌فرض 100، حداکثر 100)" },
        ]}
      />

      <SubTitle>اردربوک تجمیع‌شده (Agg Depth)</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/aggDepth" auth="NONE" />
      <ParamTable
        params={[
          { name: "symbol", required: "بله", type: "STRING", desc: "نام نماد" },
          { name: "aggregationPrecision", required: "بله", type: "DECIMAL", desc: "گام تجمیع قیمت" },
          { name: "limitRows", required: "خیر", type: "INT", desc: "حداکثر تعداد سطر خروجی" },
        ]}
      />
    </>
  );
}

function FAPIOrderSection() {
  return (
    <>
      <SectionTitle>سفارشات FAPI</SectionTitle>

      <SubTitle>ارسال سفارش</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/fapi/v1/order" auth="TRADE" />
      <CodeBlock>{`from tabdeal.future import Future
from tabdeal.enums import OrderSides, OrderTypes

client = Future(api_key, api_secret)

order = client.new_order(
    symbol="BTCUSDT",
    side=OrderSides.BUY,
    type=OrderTypes.LIMIT,
    quantity="0.01",
    price="39500",
    time_in_force="GTC",
    reduce_only=False
)`}</CodeBlock>
      <ParamTable
        params={[
          { name: "symbol", required: "بله", type: "STRING", desc: "نام نماد" },
          { name: "side", required: "بله", type: "ENUM", desc: "BUY یا SELL" },
          { name: "type", required: "بله", type: "ENUM", desc: "LIMIT یا MARKET" },
          { name: "quantity", required: "بله", type: "DECIMAL", desc: "مقدار" },
          { name: "price", required: "خیر", type: "DECIMAL", desc: "قیمت" },
          { name: "timeInForce", required: "خیر", type: "ENUM", desc: "GTC، IOC، FOK" },
          { name: "reduceOnly", required: "خیر", type: "BOOLEAN", desc: "فقط کاهش" },
          { name: "newClientOrderId", required: "خیر", type: "STRING", desc: "شناسه یکتای سفارش" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته‌ی رمزشده" },
        ]}
      />
      <Note>فقط نوع سفارش LIMIT و MARKET پشتیبانی می‌شوند.</Note>

      <SubTitle>جستجوی سفارش</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/order" auth="TRADE" />

      <SubTitle>لغو سفارش</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/fapi/v1/order" auth="TRADE" />

      <SubTitle>سفارشات باز</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/openOrders" auth="TRADE" />

      <SubTitle>تمام سفارشات</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/allOrders" auth="TRADE" />
    </>
  );
}

function FAPIPositionSection() {
  return (
    <>
      <SectionTitle>پوزیشن FAPI</SectionTitle>

      <SubTitle>ریسک پوزیشن</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v3/positionRisk" auth="TRADE" />

      <SubTitle>اهرم (Leverage)</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/leverage" auth="TRADE" />
      <Endpoint method="POST" path="https://api1.tabdeal.org/fapi/v1/leverage" auth="TRADE" />

      <SubTitle>بستن پوزیشن</SubTitle>
      <Endpoint method="DELETE" path="https://api1.tabdeal.org/fapi/v1/position" auth="TRADE" />

      <SubTitle>تنظیم حدضرر/حدسود</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/fapi/v1/positionSlTp" auth="TRADE" />
      <ParamTable
        params={[
          { name: "positionId", required: "بله", type: "LONG", desc: "شناسه پوزیشن" },
          { name: "symbol", required: "خیر", type: "STRING", desc: "نام نماد" },
          { name: "slPrice", required: "خیر", type: "DECIMAL", desc: "قیمت حدضرر" },
          { name: "tpPrice", required: "خیر", type: "DECIMAL", desc: "قیمت حدسود" },
          { name: "workingType", required: "خیر", type: "STRING", desc: "MARK_PRICE یا CONTRACT_PRICE" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته‌ی رمزشده" },
        ]}
      />

      <SubTitle>تاریخچه پوزیشن</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/position" auth="TRADE" />
    </>
  );
}

function FAPIAccountSection() {
  return (
    <>
      <SectionTitle>حساب FAPI</SectionTitle>

      <SubTitle>حساب اهرم حرفه ای</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v3/account" auth="TRADE" />

      <SubTitle>موجودی اهرم حرفه ای</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v3/balance" auth="TRADE" />
    </>
  );
}

function FAPITransferSection() {
  return (
    <>
      <SectionTitle>انتقال FAPI</SectionTitle>

      <SubTitle>انتقال بین کیف اسپات و اهرم حرفه ای</SubTitle>
      <Endpoint method="POST" path="https://api1.tabdeal.org/fapi/v1/transfer" auth="TRADE" />
      <ParamTable
        params={[
          { name: "type", required: "بله", type: "INT", desc: "2 = از کیف اصلی به اهرم، 1 = از اهرم به کیف اصلی" },
          { name: "amount", required: "بله", type: "DECIMAL", desc: "مقدار انتقال" },
          { name: "asset", required: "بله", type: "STRING", desc: "نماد دارایی" },
          { name: "timestamp", required: "بله", type: "LONG", desc: "زمان ارسال درخواست" },
          { name: "signature", required: "بله", type: "STRING", desc: "رشته‌ی رمزشده" },
        ]}
      />

      <SubTitle>تاریخچه انتقال</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/transfer" auth="TRADE" />
    </>
  );
}

function FAPITradesSection() {
  return (
    <>
      <SectionTitle>معاملات FAPI</SectionTitle>

      <SubTitle>معاملات کاربر</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/userTrades" auth="TRADE" />

      <SubTitle>سوابق درآمد</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/income" auth="TRADE" />

      <SubTitle>سفارشات اجباری (لیکویید)</SubTitle>
      <Endpoint method="GET" path="https://api1.tabdeal.org/r/fapi/v1/forceOrders" auth="TRADE" />
    </>
  );
}

function FAPIWebsocketSection() {
  return (
    <>
      <SectionTitle>وب‌سوکت FAPI</SectionTitle>

      <SubTitle>وب‌سوکت Stream (اردربوک)</SubTitle>
      <P>آدرس: <code className="text-primary-300" dir="ltr">wss://api1.tabdeal.org/special_margin/stream/</code></P>
      <CodeBlock>{`{
  "method": "SUBSCRIBE",
  "params": ["special_margin@BTC_USDT@depth@1000ms"],
  "id": 1
}`}</CodeBlock>
      <P>قالب topic: <code className="text-primary-300" dir="ltr">special_margin@[SYMBOL]@depth@[PERIOD]</code></P>
      <P>دوره‌های مجاز: 100ms, 200ms, 1000ms, 5000ms</P>
      <Note>برای دریافت دیتای بیش از ۵۰ مارکت، وب سوکت جداگانه باز کنید.</Note>

      <SubTitle>وب‌سوکت Broadcast (معاملات لحظه‌ای)</SubTitle>
      <P>آدرس: <code className="text-primary-300" dir="ltr">wss://api1.tabdeal.org/special_margin/broadcast/</code></P>
      <P>پس از اتصال، متن ساده ارسال کنید: <code className="text-primary-300">BTC_USDT</code></P>
      <P>برای اطلاعات بازار: <code className="text-primary-300">BTC_USDT_market_information</code></P>
    </>
  );
}

function ErrorsSection() {
  return (
    <>
      <SectionTitle>خطاها</SectionTitle>
      <P>در تمامی درخواست‌ها اگر به هر دلیلی امکان پردازش درخواست وجود نداشته باشد خطایی بازگردانده می‌شود:</P>
      <CodeBlock>{`{
    "code": errorCode,
    "msg": "errorMessage"
}`}</CodeBlock>

      <SubTitle>خطای سرور</SubTitle>
      <ParamTable
        params={[
          { name: "1000", required: "—", type: "—", desc: "خطای سرور (نامشخص)" },
          { name: "1001", required: "—", type: "—", desc: "خطای سرور (نامشخص)" },
          { name: "1002", required: "—", type: "—", desc: "تراکم بالای سفارشات" },
          { name: "1003", required: "—", type: "—", desc: "ویژگی مورد نظر موجود نیست" },
        ]}
      />

      <SubTitle>خطای احراز هویت</SubTitle>
      <ParamTable
        params={[
          { name: "1100", required: "—", type: "—", desc: "signature یا timestamp یا api_key داده نشده است" },
          { name: "1101", required: "—", type: "—", desc: "timestamp نامعتبر است" },
          { name: "1102", required: "—", type: "—", desc: "receive window نامعتبر است" },
          { name: "1103", required: "—", type: "—", desc: "signature نامعتبر است" },
        ]}
      />

      <SubTitle>خطا در ارسال درخواست</SubTitle>
      <ParamTable
        params={[
          { name: "1200", required: "—", type: "—", desc: "خطای نامعلوم سمت client" },
          { name: "1201", required: "—", type: "—", desc: "پارامترهای ارسالی نامعتبر است" },
          { name: "1202", required: "—", type: "—", desc: "اطلاعات فرستاده شده فرمت json درستی ندارند" },
          { name: "1203", required: "—", type: "—", desc: "پارامترهای الزامی باید ارسال شوند" },
          { name: "1204", required: "—", type: "—", desc: "سفارش مورد نظر پیدا نشد" },
          { name: "1205", required: "—", type: "—", desc: "OCO مورد نظر پیدا نشد" },
          { name: "1206", required: "—", type: "—", desc: "بازار مورد نظر پیدا نشد" },
          { name: "1207", required: "—", type: "—", desc: "اختلاف بین startTime و endTime حداکثر باید 90 روز باشد" },
          { name: "1208", required: "—", type: "—", desc: "ارسال سفارش باید منطبق بر قوانین بازار باشد" },
          { name: "1209", required: "—", type: "—", desc: "قیمت گذاری OCO اشتباه است" },
          { name: "1210", required: "—", type: "—", desc: "timestamp باید به میلی ثانیه باشد" },
          { name: "1211", required: "—", type: "—", desc: "ساختار نمادهای ارسالی اشتباه است" },
          { name: "1212", required: "—", type: "—", desc: "ارز مورد نظر پیدا نشد" },
          { name: "1213", required: "—", type: "—", desc: "با این clientOrderId قبلا سفارش ثبت شده است" },
          { name: "1214", required: "—", type: "—", desc: "listenKey پیدا نشد" },
          { name: "1215", required: "—", type: "—", desc: "سفارش قبلا لغو شده است" },
          { name: "1216", required: "—", type: "—", desc: "تعداد درخواست‌ها از حد مجاز بیشتر شده است" },
          { name: "1217", required: "—", type: "—", desc: "اجازه ارسال درخواست به این endpoint وجود ندارد" },
          { name: "1218", required: "—", type: "—", desc: "اعتبار کافی نیست" },
        ]}
      />
    </>
  );
}

function ErrorFAPISection() {
  return (
    <>
      <SectionTitle>خطاهای FAPI</SectionTitle>
      <Note>در وب سوکت‌های fapi اگر متنی با مضمون connection closed ok دریافت نمودید، باید کانکشن وب سوکت را بسته و دوباره باز کنید. این موضوع معمولا ساعتی ۱ بار رخ خواهد داد.</Note>
      <ParamTable
        params={[
          { name: "1207", required: "—", type: "—", desc: "اهرم حرفه ای غیرفعال است" },
          { name: "1208", required: "—", type: "—", desc: "نماد یا دارایی نامعتبر است" },
          { name: "1209", required: "—", type: "—", desc: "خطای اعتبار، مقدار سفارش یا قیمت" },
          { name: "1203", required: "—", type: "—", desc: "پارامتر الزامی ارسال نشده یا نامعتبر است" },
          { name: "1204", required: "—", type: "—", desc: "سفارش مورد نظر پیدا نشد" },
          { name: "1300", required: "—", type: "—", desc: "خطای سرور (نامشخص)" },
        ]}
      />
    </>
  );
}

function ErrorMarginSection() {
  return (
    <>
      <SectionTitle>خطاهای اهرم‌دار</SectionTitle>
      <ParamTable
        params={[
          { name: "5000", required: "—", type: "—", desc: "حساب معامله تعهدی غیرفعال است" },
          { name: "5001", required: "—", type: "—", desc: "مقدار بیش از حد مجاز است" },
          { name: "5002", required: "—", type: "—", desc: "لطفا مقادیر بزرگ‌تر از صفر وارد نمایید" },
          { name: "10013", required: "—", type: "—", desc: "مقدار وارد شده از وجه تضمین بیشتر است" },
          { name: "5004", required: "—", type: "—", desc: "اعطای اعتبار به سقف رسیده است" },
          { name: "3027", required: "—", type: "—", desc: "ارز انتخاب شده، معامله تعهدی ندارد" },
          { name: "3028", required: "—", type: "—", desc: "بازار از معامله تعهدی پشتیبانی نمی‌کند" },
          { name: "5007", required: "—", type: "—", desc: "مجاز به انتقال وجه نیستید" },
          { name: "5008", required: "—", type: "—", desc: "امکان انتقال ارز به خارج اکانت نیست" },
          { name: "3006", required: "—", type: "—", desc: "به سقف دریافت اعتبار رسیده‌اید" },
          { name: "5010", required: "—", type: "—", desc: "مجاز به گرفتن اعتبار نیستید" },
          { name: "10008", required: "—", type: "—", desc: "گرفتن اعتبار بر روی این ارز ممکن نیست" },
          { name: "3015", required: "—", type: "—", desc: "مقدار بازپرداست از مقدار اعتبار بیشتر است" },
          { name: "21007", required: "—", type: "—", desc: "شما در حال لیکویید شدن هستید" },
          { name: "5014", required: "—", type: "—", desc: "مقدار واردشده بیش از حداکثر مقدار قابل جابه‌جایی است" },
          { name: "5015", required: "—", type: "—", desc: "پوزیشن باز ندارید" },
          { name: "5016", required: "—", type: "—", desc: "سفارش پر نشده و پوزیشن بازی ندارید" },
          { name: "5017", required: "—", type: "—", desc: "برای هر پوزیشن تنها یک حدضرر فعال" },
          { name: "5018", required: "—", type: "—", desc: "برای هر پوزیشن تنها یک حدضرر فعال" },
          { name: "5019", required: "—", type: "—", desc: "قیمت وارد شده معتبر نمی‌باشد" },
          { name: "5020", required: "—", type: "—", desc: "برای این پوزیشن حد ضرر/قیمت هدف فعال ندارید" },
        ]}
      />
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════

export default function TabdealApiDocsPage() {
  const [activeSection, setActiveSection] = useState<Section>("intro");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const renderSection = () => {
    switch (activeSection) {
      case "intro": return <IntroSection />;
      case "security": return <SecuritySection />;
      case "auth": return <AuthSection />;
      case "order-status": return <OrderStatusSection />;
      case "order-types": return <OrderTypesSection />;
      case "order-sides": return <OrderSidesSection />;
      case "oco-status": return <OCOStatusSection />;
      case "oco-sub-status": return <OCOSubStatusSection />;
      case "trade": return <TradeSection />;
      case "market": return <MarketSection />;
      case "websocket": return <WebsocketSection />;
      case "user-ws": return <UserWebsocketSection />;
      case "wallet": return <WalletSection />;
      case "margin": return <MarginSection />;
      case "fapi": return <FAPISection />;
      case "fapi-market": return <FAPIMarketSection />;
      case "fapi-order": return <FAPIOrderSection />;
      case "fapi-position": return <FAPIPositionSection />;
      case "fapi-account": return <FAPIAccountSection />;
      case "fapi-transfer": return <FAPITransferSection />;
      case "fapi-trades": return <FAPITradesSection />;
      case "fapi-websocket": return <FAPIWebsocketSection />;
      case "errors": return <ErrorsSection />;
      case "error-fapi": return <ErrorFAPISection />;
      case "error-margin": return <ErrorMarginSection />;
      default: return <IntroSection />;
    }
  };

  return (
    <AppLayout title="داکیومنت API تبدیل" subtitle="راهنمای کامل استفاده از API صرافی تبدیل">
      <div className="flex gap-0 -mx-4">
        {/* Sidebar */}
        <aside
          className={`${sidebarOpen ? "w-64" : "w-12"} flex-shrink-0 transition-all duration-300 overflow-hidden border-l border-surface-800 bg-surface-900/50`}
          style={{ maxHeight: "calc(100vh - 180px)" }}
        >
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="w-full p-2 text-surface-400 hover:text-surface-200 text-xs flex items-center gap-2"
          >
            <span className="material-icons text-sm">{sidebarOpen ? "menu_open" : "menu"}</span>
            {sidebarOpen && "فهرست"}
          </button>
          {sidebarOpen && (
            <nav className="overflow-y-auto pb-4" style={{ maxHeight: "calc(100vh - 220px)" }}>
              {groups.map((group) => (
                <div key={group} className="mb-2">
                  <div className="px-4 py-1 text-[10px] font-bold text-surface-500 uppercase tracking-wider">{group}</div>
                  {sidebarItems
                    .filter((i) => i.group === group)
                    .map((item) => (
                      <button
                        key={item.key}
                        onClick={() => setActiveSection(item.key)}
                        className={`w-full text-right px-4 py-2 text-xs transition-colors ${
                          activeSection === item.key
                            ? "bg-primary-600/20 text-primary-300 border-r-2 border-primary-500"
                            : "text-surface-400 hover:text-surface-200 hover:bg-surface-800/50"
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                </div>
              ))}
            </nav>
          )}
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto px-6 py-4" style={{ maxHeight: "calc(100vh - 180px)" }}>
          {renderSection()}
        </main>
      </div>
    </AppLayout>
  );
}
