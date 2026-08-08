# Financial Report Intelligence — Product & Technical Specification

> מסמך מקור לפיתוח המוצר באמצעות Claude Code  
> גרסה: 1.0  
> תאריך: 2026-08-08  
> שוק ראשון: ישראל  
> פלטפורמות יעד: Web תחילה, iPhone לאחר התייצבות ה-Core  
> שם עבודה פנימי: **Report Intelligence**

---

## 0. הוראות עבודה ל-Claude Code

קרא את המסמך כולו לפני כתיבת קוד. המסמך הוא ה-source of truth הראשוני של הפרויקט: הוא מתאר את מטרת המוצר, הלוגיקה הפיננסית, הארכיטקטורה, מודל הנתונים, מגבלות ההסקה, חוויית המשתמש ושלבי הביצוע.

עקרונות עבודה:

1. אל תנסה לבנות את כל המערכת בבת אחת. התקדם לפי שלבי הביצוע וקריטריוני הקבלה בסוף המסמך.
2. התחל ב-vertical slice אמיתי: מקור MAGNA → נתונים → normalization → database → metric engine → API → מסך Web אחד.
3. אל תכניס AI למקום שבו ניתן לבצע חישוב דטרמיניסטי.
4. כל מספר, חישוב, signal או insight חייב להיות traceable למקור ולגרסת נוסחה/כלל.
5. נתון חסר הוא `null`. לעולם אין להפוך נתון חסר ל-0 או להעריך אותו ללא מקור מפורש.
6. אין להסיק סיבתיות ממספרים בלבד. מספרים יכולים ליצור signal או pattern; `cause` דורש evidence מפורש מהדוח או ניסוח זהיר כהשערה/נקודה לבדיקה.
7. שמור על ארכיטקטורה פשוטה. אין microservices, Kafka, event mesh או תשתית enterprise ב-MVP.
8. אין לקודד ספים פיננסיים עמוק בלוגיקה העסקית. Rules ו-thresholds צריכים להיות versioned/configurable.
9. לפני שינוי מהותי במודל הפיננסי, שמור תאימות לנתונים שכבר נותחו או צור version חדש.
10. אל תוסיף פיצ'רים שאינם תורמים ישירות להבנת דוחות עד שה-Core מוכח.

אם קיימת אי-בהירות שמסכנת נכונות פיננסית — העדף לעצור את אותו חישוב ולהחזיר `null`/warning על פני ניחוש.

---

# 1. חזון המוצר

המוצר אינו עוד אתר מניות ואינו reader של PDF עם chatbot.

המטרה היא להפוך דוח כספי ציבורי ארוך ומורכב לחוויה שמאפשרת למשקיע להבין במהירות:

1. **מה קרה?**
2. **מה השתנה ביחס לתקופה המקבילה?**
3. **מה חריג או מעניין?**
4. **אילו מספרים קשורים אחד לשני?**
5. **למה זה קרה, אם החברה מספקת הסבר?**
6. **מה המשמעות הפיננסית של השינוי?**
7. **האם מדובר באירוע חד-פעמי או במגמה?**
8. **מה כדאי לעקוב אחריו בדוח הבא?**
9. **מאיפה בדיוק הגיע כל מספר/הסבר?**

הבטחת הערך המרכזית:

> **אנחנו לא רק מראים את הדוח. אנחנו מתרגמים אותו לסיפור פיננסי שניתן לבדוק: מה קרה, מה חריג, איך הדברים קשורים, למה זה קרה ומה צריך לבדוק בהמשך.**

---

# 2. הבעיה שהמוצר פותר

המצב הקיים למשקיע הישראלי מפוצל:

- MAGNA/MAYA מספקים מקור רשמי ודוחות, אך המשתמש נדרש לקרוא ולנתח.
- אתרי שוק הון מציגים טבלאות, יחסים וחדשות, אך לרוב אינם בונים קשר סיבתי/חשבונאי עמוק בין המספרים.
- AI כללי מסוגל לסכם מסמך, אך עלול לערבב עובדות, חישובים והסקות ואינו בהכרח מספק audit trail אמין.
- משקיע מתחיל מוצף במונחים; משקיע מתקדם מבזבז זמן על איסוף וחיבור ידני.

המוצר צריך ליצור שכבת **understanding** מעל שכבת ה-data.

---

# 3. מה המוצר אינו

ב-MVP ובשלבים הראשונים המוצר **אינו**:

- ברוקר ואינו מבצע מסחר.
- מערכת המלצות Buy/Sell/Hold.
- אתר חדשות.
- מערכת ניתוח טכני.
- TradingView חלופי.
- תיק השקעות מלא.
- מערכת real-time quotes.
- מנוע לחיזוי מחיר מניה.
- מערכת שמאשימה חברה במניפולציה/תרמית על בסיס מודל סטטיסטי.

דוח טוב אינו בהכרח מניה טובה, ומניה טובה אינה בהכרח זולה. יש להפריד בין **איכות/מצב הדוח** לבין **valuation** והחלטת השקעה.

---

# 4. עקרונות מוצר מחייבים

## 4.1 Numbers first, AI second

כל מה שניתן לחשב בקוד — יחושב בקוד.

AI מיועד בעיקר ל:

- איתור הסבר טקסטואלי רלוונטי.
- קישור הסבר ל-signal מספרי.
- ניסוח הסבר נגיש.
- סיכום evidence שכבר נמצא.
- שאלות חופשיות על חומר מקור, עם citations.

AI אינו מחשב ratios, אינו משלים מספרים ואינו מחליט לבדו אם חברה "טובה".

## 4.2 Traceability

לכל אובייקט אנליטי צריך להיות מסלול אחורה:

`Insight → Pattern/Signal → Metric → Fact → Filing → Source location`

## 4.3 Separation of certainty

המערכת תבדיל מפורשות בין ארבע דרגות:

- `FACT` — נתון שהופיע במקור.
- `CALCULATED` — תוצאה של נוסחה דטרמיניסטית.
- `PATTERN` — צירוף של כמה signals שמצדיק תשומת לב.
- `EXPLAINED` — נמצא בדוח הסבר מפורש שמקושר ל-pattern/metric.

אין להציג `PATTERN` כאילו הוא `EXPLAINED`.

## 4.4 Missing means unknown

`null != 0`.

היעדר נתון אינו אינדיקציה חיובית או שלילית.

## 4.5 Report memory

המערכת צריכה "לזכור" מה היה חשוב ברבעון הקודם ולבדוק אותו ברבעון הבא. זהו חלק מה-moat של המוצר.

---

# 5. חוויית ההבנה: מודל ששת השלבים

לכל דוח:

1. **WHAT** — מה קרה במספרים?
2. **CHANGE** — איך זה השתנה YoY/לאורך זמן?
3. **SIGNAL** — מה חריג?
4. **CONNECTION** — אילו signals מתחברים לאותו סיפור?
5. **WHY** — מה ההנהלה/הביאורים אומרים על הסיבה?
6. **WATCH** — מה צריך לבדוק בדוח הבא?

דוגמה:

```text
Revenue +12% YoY
        |
        +-- DSO +15 days
        |
        +-- Gross Margin -1.4pp
                 |
                 +--> Pattern: Growth quality requires attention
                               |
                               +--> Evidence search in filing
                               |
                               +--> Cause if explicitly supported
```

---

# 6. מהו "דוח טוב"?

אין ציון אוניברסלי יחיד. המערכת תציג תמונה רב-ממדית.

## 6.1 ממדי הליבה

1. **Growth** — האם העסק גדל ומה איכות הצמיחה?
2. **Profitability** — האם margins והרווחיות משתפרים?
3. **Earnings Quality** — האם הרווח מתורגם למזומן?
4. **Working Capital / Cash** — האם לקוחות, מלאי וספקים מתנהגים באופן בריא?
5. **Balance Sheet & Solvency** — מזומן, חוב, נזילות ויכולת שירות חוב.
6. **Shareholder Quality** — דילול, FCF, הקצאת הון כאשר הנתונים זמינים.

לא להציג בהכרח ציון 0–100. עדיף תיאור ממדי:

```text
Growth              🟢 strong
Profitability       🟢 improving
Earnings Quality    🔴 weak
Working Capital     🟡 watch
Financial Strength  🟢 stable
Shareholder Quality 🟢 stable
```

Summary אפשרי:

> "דוח חזק תפעולית, אך איכות המזומן נחלשה ודורשת מעקב."

## 6.2 Context של חברה

פירוש מדד תלוי ב:

- sector
- industry
- business model
- lifecycle/stage
- history של החברה
- בעתיד: peer median

Company stages אפשריים:

- `growth`
- `mature`
- `turnaround`
- `cyclical`
- `distressed`
- `income_oriented`

ב-MVP ניתן לקבוע stage ידנית ל-5–10 החברות הראשונות. אין צורך לבנות classifier אוטומטי.

---

# 7. שוק ראשון ומקורות נתונים

## 7.1 ישראל

המקור הראשון הוא מערכת MAGNA/XBRL של רשות ניירות ערך.

למערכת קיים API ציבורי מתועד:

- Base: `https://xbrl.magna.isa.gov.il/api`
- `GET /init` — רשימת entities, branches ו-XBRL tags.
- `POST /search` — יצירת שאילתה.
- הורדת תוצאות: `https://xbrl.magna.isa.gov.il/public/search/{filename}.json` או `.csv`.

מפרט רשמי:  
`https://xbrl.magna.isa.gov.il/he/assets/magna-xbrl-api.pdf`

אין להניח שכל חברה ישראלית או כל field זמין ב-iXBRL. ה-ingestion חייב להתמודד עם coverage חלקי.

## 7.2 מסמכים מלאים

לצורך Evidence/Why נצטרך גם מסמכי דיווח מלאים מ-MAGNA/MAYA כאשר ניתן להשתמש בהם בהתאם לתנאים.

## 7.3 נתוני מסחר

מחירי מניות ו-market data אינם נדרשים ל-MVP של ניתוח דוחות. TASE מספקת data services/API, אך לפני שימוש מסחרי יש לבדוק רישוי ועלויות בנפרד.

## 7.4 תנאי שימוש

API ציבורי אינו כשלעצמו הוכחה לזכות redistribution מסחרי בלתי מוגבל. לפני השקה מסחרית יש לבצע review של תנאי השימוש והרישוי של MAGNA/MAYA/TASE. הארכיטקטורה צריכה לאפשר החלפת provider בלי שינוי ב-Financial Core.

---

# 8. ארכיטקטורה טכנית עליונה

```text
MAGNA / XBRL / Filings
          |
          v
Ingestion & Raw Archive
          |
          v
Normalization
          |
          v
Financial Fact Store (PostgreSQL)
          |
          v
Metric Engine (deterministic)
          |
          v
Signal Engine
          |
          v
Pattern Engine
          |
          +--------------------+
          |                    |
          v                    v
Evidence/Why Engine       Analysis Snapshot
          |                    |
          +----------+---------+
                     v
                  FastAPI
                 /       \
          Next.js Web   Expo iPhone
```

---

# 9. Stack מומלץ

## Repository

Monorepo אחד.

## Web

- Next.js
- TypeScript
- App Router
- Responsive first

## Mobile

- Expo + React Native
- לא לבנות במקביל ל-Web ב-MVP, אך לשמור API/client משותף.

## Backend

- Python
- FastAPI
- Pydantic schemas

## Database / Auth / Storage

- PostgreSQL
- Supabase בתחילת הדרך
- Supabase Storage למסמכים/artefacts כאשר מתאים
- pgvector רק כאשר Evidence/RAG באמת דורש semantic retrieval

## Financial computation

- Python pure domain modules
- calculations ניתנים לבדיקה ללא FastAPI/DB

## Background processing

בשלב ראשון jobs פשוטים/cron/background worker קטן. אין צורך ב-Celery/Redis עד שיש עומס שמצדיק זאת.

---

# 10. מבנה Monorepo מוצע

```text
financial-report-intelligence/
|
|-- apps/
|   |-- web/                 # Next.js
|   `-- mobile/              # Expo; ניתן ליצור רק בשלב mobile
|
|-- services/
|   `-- api/                 # FastAPI
|
|-- packages/
|   |-- api-client/          # generated/shared TypeScript client
|   |-- contracts/           # shared API contracts where useful
|   |-- design-tokens/
|   `-- config/
|
|-- financial_core/
|   |-- metrics/
|   |-- signals/
|   |-- patterns/
|   |-- sectors/
|   |-- validation/
|   `-- normalization/
|
|-- ingestion/
|   |-- providers/
|   |   |-- magna_xbrl/
|   |   `-- sec_edgar/       # future, do not implement now
|   |-- parsers/
|   `-- pipelines/
|
|-- database/
|   |-- migrations/
|   `-- seeds/
|
|-- tests/
|   |-- fixtures/
|   |-- golden/
|   `-- integration/
|
|-- docs/
|   |-- decisions/
|   `-- financial-methodology.md
|
|-- .env.example
|-- README.md
`-- PRODUCT_SPEC.md
```

אין חובה לשמור בדיוק על השמות, אך יש לשמור על הפרדה domain / ingestion / API / UI.

---

# 11. Canonical Financial Data Model

זו אחת ההחלטות החשובות ביותר בפרויקט.

## 11.1 Company

שדות עיקריים:

```text
id
legal_name
display_name
ticker nullable
security_number nullable
registry_id nullable
country
sector
industry
business_model nullable
company_stage nullable
reporting_currency
is_active
created_at
updated_at
```

## 11.2 Filing

```text
id
company_id
provider
provider_filing_id
report_type
fiscal_year
fiscal_quarter nullable
period_start
period_end
published_at
source_url
document_url nullable
source_format
content_hash nullable
version
is_restatement
supersedes_filing_id nullable
ingested_at
```

חשוב: restatement אינו overwrite שקט. יש לשמור lineage.

## 11.3 FinancialFact

```text
id
company_id
filing_id
raw_concept
normalized_metric_id nullable
value
currency nullable
unit
scale
period_start nullable
period_end
period_kind            # instant | duration
duration_kind          # quarter | ytd | annual | ttm | null
fiscal_year
fiscal_quarter nullable
consolidation_scope    # consolidated | separate | unknown
segment nullable
geography nullable
dimensions_json nullable
source_location nullable
source_text nullable
quality_status
created_at
```

### מדוע `instant` מול `duration`?

מאזן הוא snapshot: מזומן ליום מסוים. הכנסות הן flow לתקופה. אסור להתייחס אליהם באותה צורה.

### מדוע `quarter` מול `YTD`?

בדוחות IFRS רבעוניים קיימים לעיתים נתונים מצטברים. אין להשוות H1 להכנסות Q2. אם נדרש לגזור Q2 מתוך H1-Q1, יש לעשות זאת כחישוב מפורש, עם provenance.

## 11.4 MetricDefinition

```text
id
code                  # revenue, gross_profit, dso...
display_name_he
display_name_en
category
metric_type           # reported | derived
formula_version nullable
unit_type
description_he
description_en
sector_scope
is_core
```

## 11.5 CalculatedMetric

```text
id
company_id
analysis_period_id
metric_definition_id
value nullable
unit
formula_version
inputs_json
calculated_at
quality_status
warning nullable
```

`inputs_json` צריך לאפשר audit של inputs, אך facts המקוריים צריכים להיות references אמיתיים כאשר אפשר.

## 11.6 Signal

```text
id
company_id
period_id
signal_type
severity              # info | positive | watch | warning | critical
direction             # positive | negative | neutral
rule_version
metric_refs
message_key
confidence
created_at
```

## 11.7 Pattern/Finding

```text
id
company_id
period_id
pattern_code
title
status
signal_refs
rule_version
confidence
explanation_status    # not_searched | no_evidence | supported | contradicted
created_at
```

## 11.8 Evidence

```text
id
filing_id
evidence_type         # company_statement | note | table | calculated_support
section
page nullable
source_anchor nullable
text_excerpt
source_url
embedding nullable
created_at
```

## 11.9 Cause

```text
id
finding_id
cause_code nullable
label
description
evidence_id
support_level         # explicit | strongly_supported | inferred
confidence
```

ב-MVP מומלץ לפרסם cause למשתמש רק אם `explicit` או `strongly_supported`. `inferred` יוצג כ"אפשרות לבדיקה" ולא כעובדה.

## 11.10 WatchItem

```text
id
company_id
created_from_period_id
metric_or_pattern_code
reason
baseline_value nullable
status                # open | improved | worsened | resolved | not_measurable
resolved_period_id nullable
created_at
```

## 11.11 AnalysisSnapshot

```text
id
company_id
period_id
analysis_version
metrics_version
rules_version
evidence_version
payload_json
generated_at
is_current
```

זהו ה-object שמשרת את רוב קריאות ה-UI במהירות ובעלות נמוכה.

---

# 12. Normalization Layer

אין לקשור את האפליקציה ישירות ל-XBRL tag ספציפי.

לדוגמה, כמה concepts יכולים להתמפות ל-canonical metric אחד:

```text
raw concept A ----+
raw concept B ----+--> revenue
raw concept C ----+
```

טבלת mapping מוצעת:

```text
provider
taxonomy
raw_concept
normalized_metric
company_override nullable
valid_from nullable
valid_to nullable
mapping_version
```

יש לאפשר company-specific overrides; חברות עשויות להשתמש extensions או מבנה דיווח שונה.

אין למחוק את raw concept לאחר normalization.

---

# 13. Core Metrics ל-MVP

המטרה: 15–20 מדדים חזקים, לא 100 ratios.

## 13.1 Growth

### Revenue Growth YoY

```text
(Revenue_Q_t / Revenue_Q_t-4) - 1
```

או annual מול annual כאשר מדובר בשנה.

### Gross Profit Growth YoY

אותו עיקרון.

### Operating Profit Growth YoY

יש להיזהר כאשר בסיס ההשוואה שלילי או קרוב לאפס. במקרה כזה percent growth עלול להיות מטעה; הצג absolute change ומעבר loss→profit במקום יחס אגרסיבי.

### Net Income Growth / EPS Growth

אותו כלל לגבי crossing zero.

## 13.2 Margins

```text
Gross Margin     = Gross Profit / Revenue
Operating Margin = Operating Profit / Revenue
Net Margin       = Net Income / Revenue
```

השינוי יוצג ב-percentage points:

`9.1% → 10.0% = +0.9pp`

## 13.3 Cash

### Operating Cash Flow

הצג Q/TTM בהתאם לזמינות ולהשוואה נכונה.

### Free Cash Flow

הגדרת מערכת ראשונית:

```text
FCF = Operating Cash Flow - Capital Expenditures
FCF Margin = FCF / Revenue
```

יש לתעד שזו הגדרת המערכת; FCF אינו מדד IFRS מוגדר אחיד.

### Cash Conversion

```text
Cash Conversion = OCF_TTM / Net Income_TTM
```

Valid רק כאשר Net Income TTM חיובי ומהותי. כאשר denominator קטן/שלילי — `null` או interpretation שונה, לא ratio מטעה.

### Accruals proxy

```text
(Net Income_TTM - OCF_TTM) / Average Total Assets
```

Signal בלבד; אין לתרגם אוטומטית ל"מניפולציה".

## 13.4 Working Capital

כאשר ratio משלב stock מהמאזן ו-flow מדוח רווח והפסד, השתמש ב-average opening/closing stock אם הנתונים זמינים.

עדיף actual days in period; אם אין, השתמש ב-91 וסמן methodology.

```text
DSO = Average Receivables / Revenue_Q * days_in_period
DIO = Average Inventory / COGS_Q * days_in_period
DPO = Average Payables / COGS_Q * days_in_period
CCC = DSO + DIO - DPO
```

### Receivables Growth Gap

במקום `growth_receivables / growth_revenue`, השתמש:

```text
Receivables Growth Gap = Receivables YoY Growth - Revenue YoY Growth
```

היחס הישן אינו יציב כאשר revenue growth קרוב לאפס.

### Inventory Growth Gap

```text
Inventory Growth Gap = Inventory YoY Growth - Revenue YoY Growth
```

## 13.5 Solvency

```text
Net Debt = Interest Bearing Debt - Cash & Cash Equivalents
Net Debt / EBITDA_TTM
Interest Coverage = EBIT_TTM / Interest Expense_TTM
Quick Ratio = (Current Assets - Inventory) / Current Liabilities
Short-term Debt Share = Current Debt / Total Debt
```

אין להסיק covenant breach מ-Interest Coverage ללא covenant מפורש מהדוח.

### Funding Cost Proxy

```text
Interest Expense_TTM / Average Interest Bearing Debt
```

שם המוצר: `Funding Cost Proxy`, לא "market risk pricing". הוא מושפע מתמהיל חוב, הצמדות, refinancing, leasing ועוד.

## 13.6 Efficiency / Shareholder

```text
Asset Turnover = Revenue_TTM / Average Total Assets
Dilution = change in diluted share count YoY
```

ROIC ניתן להוסיף כאשר inputs אמינים. אין להשוות ל-WACC אם WACC לא סופק/חושב ממקור מתאים. ב-MVP אין צורך ב-WACC.

---

# 14. כללי השוואה

1. Income Statement / Cash Flow: ברירת מחדל **YoY**.
2. Balance Sheet: YoY וגם QoQ כאשר רלוונטי.
3. Flow vs Stock ratio: balance sheet average.
4. Signal מרבעון יחיד: confidence נמוך אלא אם magnitude קיצוני או יש evidence מפורש.
5. Pattern חזק: רצוי לפחות שני רבעונים או כמה signals בלתי תלויים.
6. Annual, TTM, YTD ו-quarter לעולם אינם מתערבבים ללא normalization מפורש.
7. שינוי תקינה, acquisition מהותי או restatement עלול לשבור comparability; יש ליצור warning.

---

# 15. Signal Engine

Signal הוא observation מספרי, לא cause.

דוגמאות:

## SIG_REVENUE_ACCELERATION

Revenue YoY growth עולה במשך 2+ תקופות.

## SIG_MARGIN_EXPANSION

Gross/Operating Margin משתפר YoY.

## SIG_DSO_DETERIORATION

DSO עולה באופן מהותי YoY.

ניסוח תקין:

> "זמן הגבייה מלקוחות התארך."

ניסוח אסור ללא evidence:

> "החברה דוחפת סחורה ללקוחות."

## SIG_INVENTORY_BUILD

Inventory growth materially > Revenue growth וגם/או DIO עולה.

## SIG_EARNINGS_CASH_DIVERGENCE

Net Income משתפר בזמן OCF נחלש / Cash Conversion חלש.

## SIG_DEBT_BUILD

Net Debt עולה משמעותית.

## SIG_DILUTION

Diluted share count עולה באופן מהותי.

---

# 16. Pattern Engine — ה-Core differentiation

## P1 — Growth Quality Warning

Inputs אפשריים:

- Revenue ↑
- DSO ↑
- Receivables Growth Gap חיובי מהותי
- Gross Margin ↓

Output:

> "ההכנסות גדלו, אך איכות הצמיחה דורשת בדיקה: הגבייה התארכה ו/או המרווח נשחק."

אין prediction אוטומטי שההכנסות "יירדו ברבעון הבא".

## P2 — Earnings Quality Warning

- Net Income ↑
- OCF ↓/צומח פחות
- Accruals elevated
- Cash Conversion חלש

Output:

> "קיים פער בין השיפור ברווח החשבונאי לבין תזרים המזומנים."

## P3 — Inventory Pressure

- Inventory Growth Gap גבוה
- DIO ↑
- Revenue growth חלש/מתמתן

Output:

> "המלאי גדל מהר מהמכירות וזמן שהיית המלאי התארך."

לא להבטיח markdown/impairment עתידי.

## P4 — Liquidity Pressure

צירוף של:

- Quick Ratio ↓
- Cash ↓
- Short-term Debt Share ↑
- Interest Coverage ↓
- DPO ↑ במודל שבו זה חריג

Output:

> "מספר מדדי נזילות נחלשו במקביל."

## P5 — Operational Improvement

- Revenue ↑
- Operating Margin ↑
- CCC ↓/stable
- OCF ↑

Output:

> "השיפור ניכר גם בצמיחה, גם ברווחיות וגם ביצירת המזומן."

## P6 — Shareholder Quality

- Profit/FCF ↑
- dilution low/zero
- debt stable/improving
- ROIC improving כאשר קיים

Output:

> "השיפור התפעולי מתורגם לבעלי המניות ללא דילול מהותי."

### Rule representation

Patterns צריכים להיות data/config driven ככל שניתן:

```text
pattern_code
sector_scope
required_signals
optional_signals
minimum_required
minimum_periods
severity
template_key
version
```

---

# 17. Thresholds

אל תקבע threshold כאמת אוניברסלית.

כל threshold צריך לתמוך ב:

```text
metric_code
sector_scope
company_stage_scope nullable
absolute_threshold nullable
relative_threshold nullable
historical_percentile nullable
peer_percentile nullable
minimum_periods
severity
version
valid_from
```

ב-MVP אין peer dataset מספיק גדול; לכן סדר העדיפויות:

1. magnitude בסיסי שמוגדר במתודולוגיה.
2. החברה מול ההיסטוריה שלה.
3. עקביות במספר רבעונים.
4. peer/sector median רק כאשר יהיה coverage מספיק.

---

# 18. Sector Profiles

אסור לנתח את כל החברות באותו metric pack.

## General non-financial

Core metrics לעיל.

## Retail

דגשים:

- same-store sales אם מדווח
- inventory / DIO
- gross margin
- supplier terms
- store count / online אם מדווח

Working capital שלילי יכול להיות תקין ואף איכותי במודל מסוים; DPO גבוה אינו אוטומטית בעיה.

## SaaS / Software

בעתיד:

- deferred revenue
- RPO
- NRR
- ARR
- SBC
- capitalized development costs

## Real Estate

דורש pack נפרד:

- NOI
- FFO
- occupancy
- LTV
- cap rate
- debt maturity

Fair value revaluations דורשים treatment נפרד; אין להריץ את מודל General ללא התאמות.

## Banks / Insurance

לא ל-MVP הראשון.

Banks:

- NIM
- credit loss provisions
- CET1
- NPL
- efficiency ratio

מדדים כגון gross margin, inventory, CCC, EBITDA אינם מתאימים.

## Biotech pre-revenue

דורש pack נפרד:

- cash runway
- burn rate
- milestones

אין משמעות רבה ל-ROIC/gross margin כאשר אין פעילות מסחרית מתאימה.

### המלצת MVP

בחר 5–10 חברות non-financial עם iXBRL coverage סביר ומבנה חשבונאי יחסית רגיל. הימנע בשלב הראשון מבנקים, ביטוח, נדל"ן מורכב וביוטק pre-revenue.

---

# 19. Evidence / Why Engine

המטרה אינה לתת ל-LLM "לקרוא PDF ולנתח חברה". המטרה היא לתת לו משימה צרה ומבוקרת.

Pipeline:

1. Metric Engine מזהה שינוי.
2. Signal/Pattern Engine קובע מה מעניין.
3. Retriever מחפש sections רלוונטיים בדוח: management review, segment commentary, notes.
4. LLM מקבל רק context רלוונטי + facts מחושבים.
5. LLM נדרש להחזיר structured output.
6. Validator בודק citations, numeric references ו-schema.
7. Evidence נשמר.
8. Cause מקושר רק אם evidence מספיק.

### Output contract מוצע ל-AI

```json
{
  "finding_id": "...",
  "cause_found": true,
  "cause": "...",
  "support_level": "explicit",
  "evidence": [
    {
      "source_section": "...",
      "source_page": 27,
      "source_anchor": "...",
      "excerpt": "..."
    }
  ],
  "unsupported_claims": [],
  "confidence": "high"
}
```

אם אין evidence:

```json
{
  "cause_found": false,
  "cause": null,
  "support_level": null,
  "evidence": [],
  "confidence": "low"
}
```

UI:

> "לא נמצא בדוח הסבר מפורש לשינוי."

זו תשובה לגיטימית ולעיתים מעניינת.

---

# 20. Confidence Model

אין צורך במודל ML מורכב.

Confidence נקבע לפי evidence coverage.

### Low

- signal מרבעון יחיד בלבד; או
- data quality issue; או
- inferred ללא textual support.

### Medium

- 2+ periods; או
- כמה metrics עצמאיים מצביעים לאותו כיוון.

### High

- trend מספרי ברור +
- כמה signals +
- explanation מפורש מהחברה / note מתאים.

`confidence` אינו הסתברות סטטיסטית אלא classification מוצרי. יש לתעד זאת.

---

# 21. Data Quality Engine

לפני analysis:

## 21.1 Basic validation

- currency/unit/scale consistency
- period consistency
- duplicate facts
- missing required fields
- impossible values כאשר באמת בלתי אפשריים

## 21.2 Accounting consistency checks

כאשר הנתונים מאפשרים:

```text
Assets ≈ Liabilities + Equity
Gross Profit ≈ Revenue - COGS
```

עם tolerance מתאים rounding/scaling.

## 21.3 Comparative integrity

Warnings:

- restatement
- accounting standard change
- major acquisition/disposal
- reporting currency change
- fiscal year-end change
- consolidated ↔ separate mismatch
- YTD ↔ quarter mismatch

## 21.4 Quality states

```text
verified
usable_with_warning
incomplete
not_comparable
rejected
```

אין להפיק high-confidence analysis מ-`not_comparable`.

---

# 22. מודלים אקדמיים מתקדמים — לא Core MVP

## Piotroski F-Score

אפשר להוסיף ב-Deep Dive. זהו composite accounting signal שימושי אך אינו overall truth ואינו נועד במקור לכל universe באופן אחיד.

## Altman Z-Score

להוסיף רק בווריאנט המתאים ולחברות שהמודל מתאים להן. אין להציג כ"הסתברות פשיטת רגל" מדויקת. הצג כ-distress indicator / zone.

## Beneish M-Score

להוסיף רק כ-accounting anomaly screening.

ניסוח מותר:

> "מספר דפוסים חשבונאיים מצדיקים בדיקה נוספת."

ניסוח אסור:

> "החברה מנפחת/מזייפת דוחות."

בנקים/financial institutions דורשים exclusions בהתאם למודל.

## Q4 anomaly

אין להשתמש בנוסחה:

`Q4 - (TTM - Q1-Q3)`

כאשר TTM הוא בדיוק ארבעת הרבעונים, משום שהיא מתאפסת מתמטית. בעתיד ניתן לבנות anomaly detector שמשווה implied Q4, historical seasonality ו-Q1–Q3 run-rate.

---

# 23. Analysis Snapshot — ביצועים ועלויות

רוב החישובים אינם מתבצעים בזמן page view.

כשדוח חדש נכנס:

```text
ingest once
normalize once
calculate once
detect signals once
find evidence once
generate snapshot once
```

המשתמשים קוראים snapshot מוכן.

Benefits:

- response מהיר
- AI cost נמוך
- consistent answers
- reproducibility
- קל ל-cache

Snapshot version חייב לכלול versions של formulas/rules/evidence.

---

# 24. Caching Strategy

## Layer 1 — Database

Historical facts ו-calculated metrics הם persistent data, לא cache.

## Layer 2 — Analysis Snapshot

Precomputed JSON לכל company/report/analysis-version.

## Layer 3 — API caching

Cache public immutable/rarely-changing analysis responses. אין צורך ב-Redis ב-MVP אם Postgres + application/CDN cache מספיקים.

## Layer 4 — Web/CDN

Company report pages מתאימים ל-revalidation כאשר דוח/analysis version חדש נוצר.

## Layer 5 — AI answer cache

לשאלות חופשיות בעתיד:

cache key חייב לכלול לפחות:

```text
company_id
relevant_filing_ids
analysis_version
normalized_question_hash
model/prompt_version
```

אין להחזיר תשובה cached אם filing חדש הפך אותה ל-outdated.

---

# 25. API Design

גרסה ראשונה REST פשוטה.

## Companies

```text
GET /v1/companies
GET /v1/companies/{id}
GET /v1/companies/{id}/filings
```

## Reports/Analysis

```text
GET /v1/companies/{id}/reports/latest
GET /v1/companies/{id}/reports/{period}
GET /v1/companies/{id}/reports/{period}/metrics
GET /v1/companies/{id}/reports/{period}/findings
GET /v1/companies/{id}/reports/{period}/watch-items
```

## Historical series

```text
GET /v1/companies/{id}/series/{metric_code}
```

Response לדוגמה:

```json
{
  "company_id": "...",
  "metric": "revenue",
  "points": [
    {"period": "2025-Q2", "value": 1000000000, "currency": "ILS"},
    {"period": "2026-Q2", "value": 1120000000, "currency": "ILS"}
  ]
}
```

## Evidence

```text
GET /v1/findings/{finding_id}/evidence
```

## Admin / ingestion

לא לחשוף publicly ללא authorization:

```text
POST /v1/admin/ingestion/magna/sync
POST /v1/admin/companies/{id}/reanalyze
GET  /v1/admin/jobs/{id}
```

---

# 26. Web UX — Information Architecture

## 26.1 Home

MVP:

- search company
- recent reports
- "מה השתנה בדוחות האחרונים" בעתיד

אין צורך ב-news feed.

## 26.2 Company page

Header:

```text
Company Name
Sector
Latest report: Q2 2026
```

### Report Pulse

```text
🟢 Growth: strong
🟢 Profitability: improving
🔴 Earnings quality: weak
🟡 Working capital: watch
🟢 Financial strength: stable
```

Summary:

> "החברה המשיכה לצמוח ושיפרה את הרווחיות, אך תזרים המזומנים לא עקב אחרי הרווח וזמן הגבייה מלקוחות התארך."

### Key Metrics

עד 6–8 cards, לא 30.

```text
Revenue          +12.4%
Operating Margin 8.1 → 9.3%
Net Income       +18.2%
OCF              -14.0%
DSO              +11 days
Net Debt         +4.2%
```

### "מה מעניין בדוח?"

3–5 insight cards מדורגות לפי materiality/interest:

```text
1. הרווחיות משתפרת מהר מהמכירות
   למה? →

2. המזומן לא עקב אחרי הרווח
   למה? →

3. הגבייה מלקוחות מתארכת
   למה? →
```

### Watch Next

```text
👀 בדוח הבא:
- האם DSO חוזר לרמה ההיסטורית?
- האם OCF חוזר לצמוח עם Net Income?
```

### Historical Trends

גרפים פשוטים. המשתמש יכול לבחור:

- quarterly
- annual/TTM כאשר תקין

### Deep Dive

Tabs:

- Income Statement
- Balance Sheet
- Cash Flow
- Working Capital
- Ratios
- Advanced (בעתיד)

### Source interaction

ליד כל insight/metric:

`מקור ↗`

אין להחביא provenance רק במסך admin.

---

# 27. Two UX Modes

## Simple

עברית בגובה העיניים:

> "לחברה לוקח יותר זמן לגבות כסף מהלקוחות."

## Pro

```text
DSO: 52 → 67 days (+15 days YoY)
Receivables Growth Gap: +13pp
```

שני המצבים משתמשים באותה אמת ובאותם calculations. רק presentation משתנה.

---

# 28. Report Memory — Feature אסטרטגי

כאשר pattern משמעותי נוצר, המערכת יכולה ליצור WatchItem.

דוגמה Q2:

```text
Inventory +27%
Revenue +8%
DIO +14 days
```

Watch:

> "בדוק ברבעון הבא האם מלאי חוזר לקצב התואם את המכירות."

Q3:

```text
Inventory +12%
Revenue +9%
DIO +4 days
```

Output:

> "הלחץ במלאי התמתן לעומת הדוח הקודם."

זה מייצר continuity ומעודד חזרה למוצר.

---

# 29. What's Changed? — בין דוחות

בכניסה לדוח חדש:

```text
מאז Q2:
🟢 Gross Margin improved
🟢 Inventory pressure eased
🔴 DSO deteriorated again
🟡 Net Debt stable
```

זו תצוגה בעלת ערך גבוה מאוד ומחיר חישובי נמוך.

---

# 30. Ranking של Insights

אין להציג כל signal.

Score פנימי לצורך sorting בלבד יכול לשקלל:

- materiality
- magnitude vs own history
- number of corroborating signals
- persistence across periods
- evidence strength
- severity

ה-score הפנימי אינו מוצג כ"ציון החברה".

---

# 31. Materiality

נדרש מנגנון פשוט כדי לא להציף.

ב-MVP:

- relative magnitude
- historical deviation
- impact on core metrics
- manual sector importance

בעתיד ניתן לשפר באמצעות peer distributions.

---

# 32. Ingestion Pipeline

## Step 1 — Discover

`GET /api/init`

Cache entities/tags; אין צורך לקרוא בכל request.

## Step 2 — Select candidate MVP companies

קריטריונים:

- non-financial
- כמה שנות/רבעוני history
- מספיק canonical fields
- preferably different but manageable industries

## Step 3 — Fetch

`POST /api/search` ואז JSON result.

## Step 4 — Raw persistence

שמור source metadata + raw payload/content hash, כדי שניתן יהיה reprocess ללא תלות בקריאה חוזרת בכל שינוי קוד.

## Step 5 — Normalize

Map XBRL concepts → canonical metrics.

## Step 6 — Validate

Periods, scales, currencies, duplicates, accounting identities.

## Step 7 — Calculate

Derived metrics.

## Step 8 — Signals/Patterns

Rules.

## Step 9 — Snapshot

ללא AI ב-first vertical slice.

## Step 10 — Evidence

נוסף לאחר שהמספרים עברו end-to-end validation.

---

# 33. Idempotency & Versioning

כל ingestion job חייב להיות idempotent.

אותו filing לא צריך ליצור duplicates.

Use:

- provider_filing_id
- content_hash
- company + period + filing type constraints במקומות מתאימים

Version separately:

- normalization mappings
- metric formulas
- signal rules
- pattern rules
- AI prompts
- analysis snapshots

לעולם אל תעדכן historical analysis בלי יכולת לדעת לפי איזו methodology הוא נוצר.

---

# 34. Testing Strategy

פיננסים דורשים tests יותר מ-UI polish.

## Unit tests

לכל formula:

- normal case
- zero denominator
- negative denominator
- missing input
- crossing zero
- scale/currency mismatch
- YTD vs quarter invalid mix

## Golden tests

שמור fixtures מדוח אמיתי שנבדק ידנית.

לדוגמה:

```text
expected revenue
expected margins
expected DSO
expected signals
```

כל שינוי engine מריץ regression.

## Integration tests

MAGNA payload fixture → normalization → DB → metrics → snapshot → API.

## Contract tests

Web/mobile לא צריכים לדעת כיצד MAGNA עובד. הם בודקים API contract בלבד.

## AI evaluation

כשמוסיפים AI:

- citation exists
- evidence actually supports cause
- no invented number
- no unsupported causality
- no investment recommendation
- `cause_found=false` works correctly

---

# 35. Security & Privacy

MVP ציבורי ברובו, אבל עדיין:

- secrets רק server-side.
- provider credentials אם יהיו — לא frontend.
- admin ingestion endpoints מוגנים.
- rate limiting על expensive endpoints.
- validation של inputs.
- DB roles/RLS לפי הצורך.
- אין לאפשר למשתמש לגרום ל-LLM לקרוא arbitrary internal data.

---

# 36. Observability

מינימום:

- structured logs
- ingestion job status
- provider failures
- parsing/normalization warnings
- metric calculation errors
- AI token/cost tracking כשנוסף AI
- snapshot generation latency
- API latency/error rate

נדרש admin view פשוט בהמשך ל-data quality, לא רק logs.

---

# 37. Cost Philosophy

עיקרון:

> **AI בזמן ingest/analysis — לפי צורך. AI בזמן page view — כמעט אפס.**

היסטוריה נשמרת כמבנה נתונים ומחושבת מראש. page views קוראים snapshots ו-series.

זה מאפשר scale טוב: 100,000 views של אותו דוח אינם 100,000 ניתוחי AI.

---

# 38. Web vs Mobile

## Web first

ה-Web הוא סביבת ה-validation הראשונה כי:

- מהיר יותר לפתח ולשנות.
- מתאים לטבלאות/גרפים/Deep Dive.
- מאפשר URLs ציבוריים לכל חברה/דוח.

## Mobile-ready architecture

ה-Mobile יצרוך בדיוק אותו FastAPI.

Shared:

- OpenAPI-generated client/types
- formatting rules
- design tokens
- API contracts

לא חייבים לשתף כל UI component בין Next.js ל-React Native.

## iPhone later

Expo/React Native לאחר שה-API, financial methodology וה-main company experience יציבים.

---

# 39. שלבי פיתוח — Roadmap מחייב

## Phase 0 — Repository & Engineering Foundation

Deliverables:

- monorepo
- Next.js app
- FastAPI app
- PostgreSQL connection
- migrations
- test infrastructure
- lint/typecheck
- `.env.example`
- README local setup
- CI בסיסי

Exit criteria:

- Web יכול לבצע health request ל-API.
- API יכול לבצע DB health check.
- tests רצים command אחד.

## Phase 1 — MAGNA spike

לא לבנות UI עשיר.

Deliverables:

- MAGNA provider client
- `/init` integration
- query/search client
- raw response persistence/fixture
- script שמציג available companies/tags
- shortlist של 5–10 candidate companies לפי coverage

Exit criteria:

- ניתן למשוך history של חברה אחת ללא פעולה ידנית.
- נשמר raw source.
- ברור אילו fields זמינים באמת.

## Phase 2 — Canonical Financial Core

Deliverables:

- Company/Filing/Fact/MetricDefinition schema
- normalization mappings v1
- period model
- restatement/version semantics
- validation

Exit criteria:

- חברה אחת עם 2+ שנות נתונים normalized.
- אין ערבוב quarter/YTD.
- provenance נשמר.

## Phase 3 — Metric Engine

Deliverables:

- core 15–20 metrics
- formula registry/versioning
- unit tests
- historical series

Exit criteria:

- תוצאות נבדקו ידנית מול לפחות דוח אחד.
- missing/zero/negative edge cases מכוסים.

## Phase 4 — Signal & Pattern Engine

Deliverables:

- Signal model
- configurable rules
- P1–P6 patterns
- confidence v1
- WatchItem בסיסי

Exit criteria:

- engine מסביר אילו metrics הפעילו כל finding.
- אין unsupported causal statements.

## Phase 5 — Web Product MVP

Deliverables:

- home/search
- company page
- Report Pulse
- key metrics
- insight cards
- historical charts
- deep dive
- watch-next
- source/provenance interaction ל-numeric data
- responsive mobile web

Exit criteria:

- משתמש יכול להבין חברה אחת end-to-end ללא צפייה ב-DB/admin.
- Lighthouse/performance סביר; page לא תלוי בחישוב AI live.

## Phase 6 — Evidence / Why

Deliverables:

- full-document ingestion לפי מקור חוקי/טכני זמין
- chunk/section model
- retrieval
- structured AI evidence extraction
- citation validator
- Cause objects
- `לא נמצא הסבר מפורש` state

Exit criteria:

- 20–30 findings נבדקו ידנית.
- אין invented citations/numbers בבדיקת gold set.

## Phase 7 — Product expansion בישראל

- 5 → 10 → יותר חברות
- sector packs נוספים
- What's Changed
- report memory
- comparison
- user accounts/watchlists רק כשיש צורך
- alerts בעת פרסום דוח בעתיד

## Phase 8 — iPhone

- Expo app
- company/report flow
- watchlist
- notifications בעתיד
- Deep Dive מותאם למסך קטן

## Phase 9 — US expansion

רק לאחר שה-engine מוכח.

Add provider:

`SEC EDGAR/XBRL → same canonical Financial Core`

לא לשנות business logic להיות provider-specific.

---

# 40. Expansion לארה"ב — Design now, implement later

Interface מוצע:

```python
class FinancialDataProvider(Protocol):
    def list_entities(...): ...
    def list_filings(...): ...
    def fetch_filing_facts(...): ...
    def fetch_document(...): ...
```

MAGNA implementation ראשונה.

SEC implementation עתידית.

ה-Financial Core לעולם לא אמור לדעת URL של MAGNA או SEC.

Canonical identifiers, currencies, period logic ו-taxonomy mapping מאפשרים expansion בלי rewrite.

---

# 41. דוגמה מלאה: איך המערכת צריכה לחשוב

נניח data דמיוני:

```text
Revenue Q2 2026:          1,120M
Revenue Q2 2025:          1,000M
Gross Profit Q2 2026:       392M
Gross Profit Q2 2025:       370M
Net Income TTM:              90M
OCF TTM:                     55M
Receivables avg Q2 2026:    205M
Receivables avg Q2 2025:    150M
```

### Step 1 — Facts

שומר את הערכים עם source.

### Step 2 — Calculations

```text
Revenue Growth = +12%
Gross Margin 2026 = 35.0%
Gross Margin 2025 = 37.0%
Gross Margin delta = -2.0pp
Cash Conversion = 0.61
DSO 2026 ≈ 16.6 days (assuming compatible quarterly flow and period-days methodology)
DSO 2025 ≈ 13.7 days
```

המספרים כאן להמחשה בלבד; implementation חייב להשתמש במודל periods/averages האמיתי.

### Step 3 — Signals

- Revenue growth positive.
- Gross margin deteriorated.
- Cash conversion weak.
- DSO increased.

### Step 4 — Pattern

Potential P1 Growth Quality Warning + P2 Earnings Quality Warning.

### Step 5 — Evidence

חיפוש בדוח להסבר margin/receivables/cash conversion.

### Step 6 — User output

```text
🟢 ההכנסות צמחו 12%
🔴 המרווח הגולמי ירד 2 נקודות אחוז
🟡 זמן הגבייה התארך
🔴 הרווח אינו מתורגם במלואו למזומן

מה מעניין?
הצמיחה נמשכה, אך שני מדדי איכות — margin וגבייה — נחלשו במקביל.
```

אם הדוח אומר שה-margin ירד עקב עליית חומרי גלם:

```text
למה המרווח ירד?
החברה מייחסת את הירידה בעיקר להתייקרות חומרי גלם.
מקור →
```

אם אין הסבר:

```text
לא נמצא בדוח הסבר מפורש לשינוי במרווח.
```

---

# 42. ניסוחים אסורים ומותרים

## DSO

אסור:

> "החברה עושה channel stuffing."

מותר:

> "זמן הגבייה התארך ב-15 ימים; כדאי לבדוק אם תנאי האשראי השתנו."

ואם יש evidence:

> "החברה מציינת שהאריכה תנאי אשראי ללקוחות מסוימים."

## Inventory

אסור:

> "מחיקת מלאי תגיע ברבעון הבא."

מותר:

> "המלאי גדל מהר מהמכירות ו-DIO התארך. אם המגמה תימשך, נדרש מעקב אחר קצב המכירה וה-margin."

## Interest coverage

אסור:

> "החברה עומדת להפר covenant."

מותר:

> "יכולת כיסוי הריבית נחלשה."

אם covenant מופיע בדוח, ניתן להשוות אליו במפורש.

## Beneish

אסור:

> "החברה מבצעת מניפולציה."

מותר:

> "מודל anomaly מצביע על מספר דפוסים שמצדיקים בדיקה נוספת."

---

# 43. Out of Scope מהמספרים בלבד

הדברים הבאים דורשים textual evidence/מקור נוסף ולא ניתנים להסקה בטוחה רק מה-ratios:

- איכות הנהלה
- סיכון משפטי
- סיכון רגולטורי
- תלות בלקוח/ספק
- עסקאות בעלי עניין
- חוות דעת המבקר
- אירועים לאחר תאריך המאזן
- הסיבה האמיתית לעלייה/ירידה במלאי
- כוונת הנהלה
- הונאה/מניפולציה כעובדה

ה-Evidence Engine בעתיד יכול להוציא חלק מהמידע הזה מהביאורים, אבל צריך לתייג אותו לפי מקור.

---

# 44. Product Tone

עברית בהירה, מקצועית, לא דרמטית.

לא:

> "אסון! החברה קורסת!"

כן:

> "שלושה מדדי נזילות נחלשו במקביל ומצדיקים תשומת לב."

לא:

> "מניה מצוינת."

כן:

> "הדוח מציג שיפור בצמיחה, במרווח ובתזרים."

מטרת המוצר היא לעזור למשתמש לחשוב, לא לחשוב במקומו.

---

# 45. Localization

Domain codes באנגלית.

UI strings localized.

לדוגמה:

```text
metric code: operating_margin
HE: מרווח תפעולי
EN: Operating Margin
```

כך expansion לארה"ב לא דורש schema migration.

Currency formatting אינו hard-coded ל-₪.

---

# 46. Data/Analysis Admin Tool — בהמשך MVP

נדרש admin פשוט שמאפשר:

- לראות filings שנקלטו
- לראות normalization failures
- unmapped XBRL concepts
- data-quality warnings
- metric calculation errors
- evidence pending/rejected
- re-run analysis version
- manual company profile/sector pack selection

בשלב מוקדם CLI/admin endpoints מספיקים; אין צורך לבנות dashboard מלא לפני ה-user product.

---

# 47. Product Analytics

כאשר יש משתמשים, למדוד:

- company page views
- report page completion
- insight card opens
- "למה?" clicks
- source clicks
- simple/pro toggle
- watch item engagement
- returning after next report

North-star candidate:

> אחוז המשתמשים שפתחו לפחות Insight/Why אחד לאחר צפייה ב-Report Pulse.

מטרה: למדוד האם אנחנו יוצרים הבנה, לא רק traffic.

---

# 48. Definition of MVP Done

MVP אינו "יש דף יפה".

MVP Done כאשר:

1. לפחות 5 חברות ישראליות נתמכות באופן אמין.
2. לכל חברה יש מספר רבעונים/שנים המאפשרים מגמות.
3. data ingestion אוטומטי ממקור ראשי עובד.
4. facts normalized עם provenance.
5. 15–20 core metrics מחושבים ונבדקים.
6. 4–6 patterns עובדים.
7. Report Pulse עובד.
8. Insight cards מציגות inputs ברורים.
9. historical series מהירות.
10. Watch Next קיים לפחות בגרסה בסיסית.
11. כל missing data מטופל כ-null.
12. אין causal claim ללא evidence.
13. web responsive ונוח גם בטלפון.
14. לפחות gold dataset אחד נבדק ידנית מקצה לקצה.

Evidence/AI Why יכול להיכלל ב-MVP מתקדם או מיד לאחר quantitative MVP, אבל הארכיטקטורה חייבת לתמוך בו מראש.

---

# 49. Definition of Product v1 Done

מעבר ל-MVP:

- 10+ חברות עם coverage טוב
- Evidence/Why engine
- source citations
- report memory
- What's Changed
- sector-specific packs ראשונים
- comparison בסיסי
- account/watchlist אם נדרש
- production monitoring
- documented financial methodology
- legal/data-license review הושלם

לא נדרש עדיין US coverage או native app כדי להחשיב v1 web כמוצר עובד.

---

# 50. Future Product Ideas — לא ליישם לפני Core

רק לאחר validation:

- Ask the Report
- Compare 2–3 peers
- earnings release alerts
- company watchlists
- management statement vs actual result tracking
- guidance tracking
- segment visualization
- "what changed since last year"
- advanced Piotroski/Altman/Beneish panel
- downloadable investor brief
- user annotations
- screeners based on quality patterns
- SEC/US coverage
- iPhone push notifications

---

# 51. Key Architectural Decisions — Decision Log

1. **Web first, mobile-ready.** Next.js + separate Expo client later.
2. **One backend truth.** Web/mobile use FastAPI; no duplicated financial logic in clients.
3. **PostgreSQL canonical store.** Historical data persists permanently.
4. **Provider abstraction.** MAGNA is provider 1, not the domain model.
5. **Deterministic financial engine.** AI never replaces formulas.
6. **Fact/Calculated/Pattern/Explained separation.** Fundamental trust requirement.
7. **No universal overall company score.** Multi-dimensional assessment.
8. **No unsupported causality.** Signals are not causes.
9. **Precompute analysis.** Keep page views cheap.
10. **Version everything analytical.** Formula/rule/prompt changes are auditable.
11. **Sector packs.** One financial model does not fit banks, SaaS, retail and real estate.
12. **MVP stays small.** 5–10 companies, 15–20 metrics, 4–6 patterns.

---

# 52. מה Claude Code צריך לעשות עכשיו

לאחר קריאת המסמך:

## Task A — Inspect environment

- בדוק repository state.
- אם אין repo/project, bootstrap בהתאם ל-Phase 0.
- תעד prerequisites.
- אל תניח credentials שאינם קיימים.

## Task B — Create implementation plan

כתוב plan לפי Phase 0–5 עם subtasks ו-acceptance criteria.

## Task C — Implement Phase 0

בנה foundation נקי, בדיקות ו-local setup.

## Task D — Implement MAGNA spike

השתמש בתיעוד הרשמי ובצע read-only integration.

אל תבנה mappings גדולים לפני שבדקת את payload האמיתי.

## Task E — Select first company from actual coverage

בחר candidate non-financial עם history טוב. תעד מדוע נבחרה. אם כמה מועמדות שקולות, הצג shortlist לפני קבלת החלטה משמעותית.

## Task F — Build first vertical slice

```text
MAGNA
→ raw data
→ canonical facts
→ 5 metrics first
→ 1–2 signals
→ snapshot
→ API
→ company page
```

אחרי שהמסלול עובד, הרחב ל-15–20 metrics ול-patterns.

## Task G — Tests before breadth

אין להוסיף 10 חברות לפני שחברה אחת עוברת golden validation.

---

# 53. Success Criterion

השאלה המרכזית אינה:

> "כמה נתונים המערכת מציגה?"

אלא:

> **"האם בתוך 30 שניות משתמש מבין מה קרה בדוח, ובתוך שתי דקות הוא מבין מה באמת מעניין ולמה?"**

אם המערכת עונה על זה תוך שמירת traceability ואמינות חשבונאית — היא מממשת את החזון.

---

# 54. מקורות ראשוניים שכדאי לשמור בתיעוד הפרויקט

### MAGNA XBRL

- Data exploration: `https://xbrl.magna.isa.gov.il/`
- API specification: `https://xbrl.magna.isa.gov.il/he/assets/magna-xbrl-api.pdf`

### TASE Data Services

- `https://www.tase.co.il/en/content/products_lobby/data_services`

### IFRS — Cash Flow context

- IAS 7 overview: `https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows.html/`

### Academic models for future Deep Dive

- Altman (1968), *Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy*, Journal of Finance.
- Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*, Journal of Accounting Research.
- Beneish (1999), *The Detection of Earnings Manipulation*, Financial Analysts Journal.

המודלים האקדמיים הם reference למודולים עתידיים, לא הרשאה להפוך statistical signal לעובדה על חברה ספציפית.

---

# 55. משפט סיכום לצוות הפיתוח

> Build a financial understanding engine, not a financial data dashboard. Preserve the raw truth, calculate deterministically, detect patterns conservatively, explain only with evidence, remember what mattered last quarter, and make every conclusion traceable back to the filing.

