# ممیزی فرانت — ایرادهای ساختاری و غیرساختاری
> تاریخ: ۱۴۰۴/۰۶/۰۵ | نسخه Next 16.2.9 + React 19.2.4 | 275 فایل، 117 صفحه | بررسی: معمار + امنیت + UX + QA

## چکیده
- **ساختاری:** ۲ بحرانی (۱۱۷ صفحه بدون گروه‌بندی + ۳ مسیر screener موازی)، ۵ زیاد (TopNavbar گاد، API DRY، مسیریابی تکراری bonds/crypto)
- **غیرساختاری:** ۲ زیاد (polling 5-7 همزمان + fallback ساکت به mock)، ۴ متوسط (UX drawer، a11y nav، کیفیت fmt تکراری، امنیت CSP)
- **نتیجه:** معماری فعلی «قابل نگهداری مشروط» — تا ۳ اصلاح ساختاری (گروه‌بندی مسیرها، تجمیع API، بهینه‌سازی باندل) انجام نشود، افزودن هر فیچر جدید ریسک رگرسیون دارد.

---

## الف) ساختاری

### ۱. معماری کلی
| فایل:خط | شدت | شرح | پیامد | راهکار |
|---------|------|-----|--------|--------|
| `next.config.ts:6` `outputFileTracingRoot: ..` | زیاد | tracing به ریشه مونورپو — شکننده اگر build از ریشه اجرا شود | build در CI می‌شکند | `path.resolve(__dirname,"..")` + کامنت |
| `next.config.ts:7` `allowedDevOrigins` هاردکد IP | کم | IP خصوصی در VCS | تداخل بین دولوپرها | به `.env` منتقل |
| `next.config.ts:8-10` `optimizePackageImports` فقط ۲ مورد | متوسط | `framer-motion`, `lucide-react` جا مانده | باندل ۹۰KB اضافی | افزودن به لیست |
| `package.json:6` `next dev --webpack` | متوسط | پین به webpack در حالی که Turbopack پیش‌فرض 16.2 است | سردرگمی تیم، HMR کند | انتخاب صریح + کامنت IR/offline |
| `layout.tsx:82` `<link googleapis Material Icons>` | زیاد | تناقض با کامنت «آفلاین/IR» (خود-هاست) | فونت پشت فایروال لود نمی‌شود، FOIT | خود-هاست یا حذف |
| `providers.tsx:34` `new QueryClient()` بدون defaults | متوسط | هر `useQuery` مجبور به تکرار `retry:1, staleTime` | ناسازگاری کش | `defaultOptions: {queries:{retry:1}}` در Provider |
| `middleware.ts:32` `PROTECTED_ROUTES` فقط ۴ مورد | **بحرانی** | ۱۱۷ صفحه ولی فقط `/admin,/settings/security,/profile,/watchlist` گارد — `/sync,/portfolio,/signals/register` باز | کاربر لاگین‌نکرده UI محافظت‌شده را می‌بیند | allowlist معکوس (public routes) یا تولید از `nav-config` |
| `layout.tsx:53 + hooks/useTheme.ts:34` | متوسط | منطق THEME_SCRIPT تکراری (۲ منبع) | drift نگهداری | استخراج ثابت مشترک |

### ۲. مدیریت State
| `lib/api.ts + auth-context.tsx` dual source `_memoryAuth` vs `AuthState` | زیاد | دو منبع حقیقت برای توکن — همگام‌سازی دستی | race در `hydrateSession` | یک store واحد |
| `auth-context:278 hasRole` | متوسط | `indexOf` برای نقش ناشناس → `ROLE_HIERARCHY.length` → مقایسه اشتباه | RBAC برای نقش سفارشی می‌شکند | Map صریح |
| `hooks/useWebSocket.ts:31 WS_URL` یکبار در load | زیاد | URL در HMR/SSR ثابت، `symbols` جدید پس از باز بودن سوکت ارسال نمی‌شود | watchlist جدید آپدیت نمی‌گیرد | `symbols` را به deps یا `subscribe()` اضافه |
| `useMarketData:200` 5 polling همزمان (30s/120s/180s) | متوسط | ۵ درخواست همزمان روی داشبورد | باتری/دیتا/لود سرور | تجمیع به `market-dashboard` واحد |

### ۳. مسیریابی (117 صفحه)
| `app/` flat بدون گروه‌بندی `(dashboard)` | **بحرانی** | ۱۱۷ صفحه هم‌سطح، بدون `layout.tsx` per segment | `nav-config` دستی، `AppLayout` کپی ۱۰۰ بار | معرفی `app/(dashboard)/layout.tsx` |
| `screener / screener110 / smart-screener` | **بحرانی** | ۳ مسیر برای یک دامنه با `formatPrice` تکراری | سردرگمی کاربر، سئو دوپاره | یک `/screener?view=` |
| `markets/bonds` vs `markets/stocks/bonds`, `crypto` vs `crypto-market` vs `crypto-exchange` | زیاد | URL دوگانه برای یک مفهوم | بوکمارک متفاوت | یکسان‌سازی |
| `backtest` 1621 خط + ۹ زیردایرکتوری | زیاد | ۱۰ صفحه برای یک فیچر بدون layout مشترک | هات‌اسپات کانفلیکت | گروه `(backtest)` با layout تب |
| فقط `layout.tsx` ریشه | زیاد | هر صفحه `import AppLayout` دستی | فراموشی `FloatingAssistant`, نبود `loading.tsx` | layout تو در تو |

### ۴. وابستگی کامپوننت
| `TopNavbar:496` گاد-کامپوننت | زیاد | NAV_CONFIG + SEARCH_SYMBOLS + auth + framer-motion در یک فایل | تست سخت | استخراج `SymbolSearch` hook + `MegaPanel` |
| `AppLayout -> DashboardShell -> TopNavbar -> MegaPanel` | متوسط | TickerBar دوباره `useTickerItems` → polling تکراری | درخواست دوبرابر | lift query به layout |
| `dashboard/primitives` فقط در dashboard | متوسط | `Card` موازی با `ui/Card`, `Skeleton` دوگانه | ناسازگاری دیزاین | یکسان‌سازی `ui/` |
| `Sidebar.tsx` بلااستفاده | کم | DashboardShell از Sidebar استفاده نمی‌کند | کد مرده | حذف |

### ۵. لایه API
| `lib/api.ts:166-301` ۴ تابع کپی ۳۵ خط | زیاد | DRY نقض | باگ ۴ برابر | `apiRequest<T>()` واحد |
| `lib/api.ts:185 _handle401` با `window.location.href` | زیاد | ریدایرکت سخت SPA را می‌شکند | کاربر وسط تعامل پرت می‌شود | `router.push` + toast |
| `lib/api.ts:330 extractArray<unknown>` | زیاد | `any`-adjacent، جستجوی بازگشتی کور | تایپ دروغین، ریسک شکل داده | `zod` schema |

### ۶. وابستگی‌ها و بیلد
| `package.json` heavy libs (recharts + lightweight-charts + xlsx 400KB) | متوسط | باندل ~۵۰۰KB | LCP کند | `xlsx` دینامیک `import()` |
| `react-query-devtools` در `dependencies` | متوسط | به پروداکشن می‌رود | باندل اضافی | به `devDeps` |
| `@types/parse-json, prop-types` فانتوم | زیاد | نصب بیهوده 15MB | کندی install | `depcheck` + prune |

---

## ب) غیرساختاری

### ۱. UX
| `app/page.tsx:59` `setTimeout 620ms` | متوسط | اسکلت اجباری حتی در شبکه سریع | تأخیر ۰.۶s |
| `TickerBar + LiveClock + useMarketSession` ۳ interval 1s | کم | بیداری مکرر ترد | تجمیع به یک تایمر |
| `TopNavbar drawer` بدون focus trap/aria-expanded/Esc | متوسط | کیبورد نمی‌تواند خارج شود | `focus-trap-react` + `aria-expanded` |
| `SyncStatus` fallback ساکت به mock | متوسط | کاربر داده کهنه را زنده می‌پندارد | `EmptyState` + retry |

### ۲. پرفورمنس
| polling 5-7 همزمان هر ۳۰-۱۸۰s | **زیاد** | باتری/دیتا، لود سرور | `refetchIntervalInBackground:false` + WS |
| `framer-motion` eager برای stagger 0.055s | متوسط | ۳۰KB اضافی در critical | CSS stagger |
| `<img>` به‌جای `next/image` (۴ جا) | متوسط | LCP کند | `next/image` + `remotePatterns` |
| `fund-checklist.ts` 185KB sync import | زیاد | JS اولیه سنگین | `import()` تنبل |

### ۳. دسترس‌پذیری
| `TickerBar` mask gradient بدون disable برای `prefers-reduced-motion` | کم | سرگیجه | `media (prefers-reduced-motion)` |
| `MegaPanel role=menu` با `<Link>` | متوسط | کیبورد منو را باز نمی‌کند | `Disclosure` + arrow nav |
| نبود `skipToContent` + landmark | متوسط | WCAG 2.4.1 | افزودن |
| بوردر/رینگ کنتراست پایین در `brand-950` | متوسط | فوکوس نامرئی | افزایش کنتراست |

### ۴. کیفیت کد
| `backtest:1179` کامپوننت داخل رندر | زیاد | state هر رندر ریست | استخراج + `memo` |
| ۶ پیاده‌سازی `fmt`/`faNum` پراکنده | زیاد | ناسازگاری عدد فارسی | تمرکز در `market-format.ts` |
| `console.log` بدون گارد `NODE_ENV` | متوسط | لاگ در پروداکشن | گارد |
| ۱۵ متغیر بلااستفاده (Card, depthView...) | متوسط | سردرگمی | حذف |

### ۵. امنیت
| `layout.tsx:93` `dangerouslySetInnerHTML` THEME_SCRIPT | اطلاع | استاتیک، بدون ورودی کاربر — **امن** | — |
| `middleware:32` فقط حضور کوکی چک | متوسط | فلش UI قبل از ۴۰۱ | گسترش allowlist |
| نبود CSP/HSTS | متوسط | XSS تأثیر بیشتر | `Content-Security-Policy` در middleware |
| `LONG_TIMEOUT 10m` بدون CSRF | کم | CSRF sync | `X-Requested-With` |

### ۶. i18n
| هاردکد فارسی در ۵۰ فایل، بدون `next-intl` | زیاد | افزودن انگلیسی = ویرایش ۵۰ فایل | `src/lib/i18n.ts` |
| `settings` فقط `fa` ولی سلکتور دارد | متوسط | گمراهی کاربر | حذف یا پیاده‌سازی |
| Jalali دستی vs `Intl` پراکنده | متوسط | تاریخ ناسازگار (میلادی با رقم فارسی) | تمرکز در `dates.ts` |

---

## اولویت ترمیم (ساختاری → غیرساختاری)

1. **امنیت CSP + گسترش PROTECTED_ROUTES به allowlist** (۱ روز)
2. **گروه‌بندی مسیرها `app/(dashboard)` + تجمیع ۳ screener** (۳ روز)
3. **تجمیع API به `apiRequest<T>` + zod** (۲ روز)
4. **بهینه‌سازی باندل: `optimizePackageImports` برای ۳ lib + `xlsx` تنبل** (۱ روز)
5. **پولینگ → WS یا `refetchInBackground:false`** (۱ روز)
6. **یکسان‌سازی `fmt` + `market-format.ts`** (۱ روز)
7. **a11y drawer + MegaPanel + skipLink** (۲ روز)

