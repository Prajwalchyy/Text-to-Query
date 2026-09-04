# OmniData AI — Sample Datasets Repository

This directory contains categorized, production-grade sample datasets organized for testing **Single Upload**, **Multi-File Bulk Import (with Group Folders)**, and **Merge Mode** across all supported database engines.

> 📖 **Quick Reference Guide:** For copy-paste test prompts for every dataset, see **[PROMPT_SAMPLES.md](file:///e:/ALL_CODES_HERE_NOW/Project_Prot/Text_to_sql/samples/PROMPT_SAMPLES.md)** (5 prompts per dataset across all 6 engines).

---

## 📁 Directory Architecture

```
samples/
├── 1_sqlite_db/
│   ├── single/
│   │   └── healthcare_patients.db         # Comprehensive SQLite database (Patients, Doctors, Admissions, Prescriptions)
│   └── multiple/
│       ├── northwind_ecommerce.db         # Classic Northwind SQLite (Customers, Orders, Products, Shippers)
│       └── sakila_movie_rentals.db        # Film & DVD rental SQLite (Films, Actors, Rentals, Stores)
│
├── 2_sql_scripts/
│   ├── single/
│   │   └── customer_reviews.sql           # Individual SQL table schema & data dump
│   └── multiple/
│       ├── departments.sql                # SQL Table dump: corporate departments
│       ├── employees.sql                  # SQL Table dump: staff profiles & salaries
│       ├── employee_evaluations.sql       # SQL Table dump: quarterly reviews & performance
│       └── projects.sql                   # SQL Table dump: projects & budget allocations
│
├── 3_json_nosql/
│   ├── single/
│   │   └── ecommerce_store.json           # Single document dataset with nested products, reviews, categories
│   └── multiple/
│       ├── course_reviews.json            # NoSQL collection: student ratings & review feedback
│       ├── courses.json                   # NoSQL collection: course catalog & pricing
│       ├── enrollments.json               # NoSQL collection: active student enrollments
│       └── members.json                   # NoSQL collection: registered member profiles
│
├── 4_bson_nosql/
│   ├── single/
│   │   └── iot_weather_stations.bson      # Binary MongoDB BSON: weather station telemetry (Temp, Humidity, AQI, Rain)
│   └── multiple/
│       ├── warehouse_inventory.bson       # Binary MongoDB BSON: warehouse inventory (SKUs, Quantities, Bins, Suppliers)
│       └── logistics_shipments.bson       # Binary MongoDB BSON: parcel tracking (Carriers, Route, Weight, Status)
│
├── 5_csv_spreadsheets/
│   ├── single/
│   │   └── sales_performance.csv         # CSV spreadsheet: monthly sales, reps, regions, quota metrics
│   └── multiple/
│       ├── regional_sales_q1.csv          # Q1 Regional sales records (Revenue, Units, Categories)
│       ├── regional_sales_q2.csv          # Q2 Regional sales records
│       └── regional_sales_q3.csv          # Q3 Regional sales records
│
└── 6_excel_spreadsheets/
    ├── single/
    │   └── financial_budget.xlsx          # Multi-sheet Excel workbook: Department Budgets, Expenses, CapEx
    └── multiple/
        ├── marketing_campaigns.xlsx       # Multi-sheet Excel workbook with live formulas (=D2/F2, =SUM(B2:B6))
        └── employee_headcount.xlsx        # Multi-sheet Excel workbook with live formulas (=COUNTIF, =SUMIF, =AVERAGEIF)
```

---

## 🧪 Testing Guide: Upload Modes & What to Expect

### Mode 1: Single Upload Mode (`upload_mode="single"`)
- **How to test:**
  1. Open the UI at `http://localhost:5173/`.
  2. Click **Manage Data Sources** in the top navbar.
  3. Ensure **Full Data Source(s)** is selected.
  4. Select the appropriate engine type (**SQL Database**, **NoSQL Store**, or **Spreadsheet**).
  5. Select **1 file** from any `single/` subfolder.
  6. Provide a custom name (or let the system auto-fill).
  7. Click **Save & Register**.
- **What happens behind the scenes:**
  - File is physically stored in `backend/data/{type}/single/{filename}`.
  - Tagged with `upload_mode: "single"` and displays a `Single File` badge in the database list.

---

### Mode 2: Multi-File Bulk Import (`upload_mode="multiple"`)
- **How to test:**
  1. Open **Manage Data Sources**.
  2. Ensure **Full Data Source(s)** is selected.
  3. Select the appropriate engine type.
  4. Select **all files** inside any `multiple/` folder (e.g. all 3 CSVs or both SQLite databases).
  5. Enter a **Batch / Group Name** (e.g., `2026 Quarterly Performance`).
  6. Click **Bulk Import**.
- **What happens behind the scenes:**
  - Files are physically isolated in `backend/data/{type}/multiple/{group_slug}_{timestamp}/`.
  - Each file becomes its own queryable dataset, linked by `group_id` and `group_name`.
  - In both the **Manage Data Sources** modal and the **Switch Data Source** popover, each imported dataset displays a distinct `📁 {group_name}` badge.

---

### Mode 3: Multiple Tables / Collections (Merge Mode)
- **How to test:**
  1. Open **Manage Data Sources**.
  2. Switch to **Multiple Tables (Merge)** or **Multiple Collections (Merge)**.
  3. **SQL Merge:** Select the 4 `.sql` scripts from `2_sql_scripts/multiple/`. Name it `Corporate Operations`.
     - Automatically creates a single SQLite database containing all 4 tables with their foreign key relations!
  4. **NoSQL Merge:** Select the 4 `.json` files from `3_json_nosql/multiple/`. Name it `Academy Portal`.
     - Automatically creates a single multi-collection NoSQL document database containing all 4 collections!

---

## 💡 Sample Questions to Ask for Each Dataset

| Dataset | Engine | Sample Prompt to Ask OmniData AI |
| :--- | :--- | :--- |
| `healthcare_patients.db` | SQLite | *"Show all patients admitted with a high-risk condition and their assigned doctor."* |
| `ecommerce_store.json` | NoSQL JSON | *"Find all electronics products with an average rating higher than 4.2."* |
| `iot_weather_stations.bson` | NoSQL BSON | *"Which weather station has the highest recorded temperature and what is its status?"* |
| `sales_performance.csv` | CSV / Pandas | *"Calculate the total revenue by sales rep and filter for reps with more than 10 units sold."* |
| `marketing_campaigns.xlsx` | Excel Formulas | *"Give me the Excel formula to calculate the average conversion rate across all channels."* |
| `employee_headcount.xlsx` | Excel Formulas | *"Show me an Excel formula to count how many employees work in the Engineering department."* |
