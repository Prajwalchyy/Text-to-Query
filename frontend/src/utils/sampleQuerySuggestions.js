/**
 * Dynamic Dataset-Aware Prompt Generator
 * 
 * Inspects any active dataset (SQL, NoSQL, CSV, Excel - including user-uploaded datasets)
 * and generates diverse, grounded, natural language analytical prompts based on:
 * - Table / Collection entities
 * - Detected Date & Time columns (Timelines & Temporal trends)
 * - Detected Numeric Metric columns (Aggregations, Rankings, Medians, Extremes)
 * - Detected Categorical Dimension columns (Distributions, Group By, Filters)
 * - Foreign Keys & Inferred Relationships (Multi-Table Joins & Cross-Entity Analytics)
 * 
 * Combines hand-crafted domain showcase prompts for default datasets with dynamic
 * schema-synthesized templates for instant (0ms), token-free, query-safe prompt discovery.
 */

// -----------------------------------------------------------------------------
// 1. Handcrafted Domain Showcase Seeds (Pre-Packaged Datasets)
// -----------------------------------------------------------------------------
const SEED_PROMPTS = {
  chinook: [
    {
      title: "Top-Selling Artists",
      prompt: "Show the top 5 artists with the most tracks in the catalog.",
      tag: "Aggregation"
    },
    {
      title: "High-Value Customers",
      prompt: "Find all customers who have spent more than $40 in total across all invoices.",
      tag: "Filter & Join"
    },
    {
      title: "Genre Revenue",
      prompt: "Show total sales revenue grouped by track genre in descending order.",
      tag: "Analytics"
    },
    {
      title: "Catalog Extremes",
      prompt: "List the 10 longest songs along with their album title and duration in minutes.",
      tag: "Sorting"
    },
    {
      title: "Geographic Sales",
      prompt: "Which billing countries generated the highest total invoice sales?",
      tag: "Geo-Analytics"
    },
    {
      title: "Customer Preferences",
      prompt: "Find customers who bought tracks from more than 3 distinct music genres.",
      tag: "Complex Join"
    }
  ],
  ecommerce_store: [
    {
      title: "Orders by Status",
      prompt: "Find all orders with status 'shipped' and total amount over $100.",
      tag: "MQL Filter"
    },
    {
      title: "Product Categories",
      prompt: "Count total products grouped by category name.",
      tag: "Group By"
    },
    {
      title: "Frequent Shoppers",
      prompt: "List customers who have placed more than 3 orders.",
      tag: "Aggregation"
    },
    {
      title: "Order Metrics",
      prompt: "What is the average order value across all completed orders?",
      tag: "Summary"
    },
    {
      title: "Low Stock Inventory",
      prompt: "Find products with stock quantity below 20 that belong to active categories.",
      tag: "Inventory"
    },
    {
      title: "Customer Geography",
      prompt: "Break down customer count by city and show total registered accounts.",
      tag: "Distribution"
    }
  ],
  sales_performance: [
    {
      title: "Top Sales Reps",
      prompt: "Calculate total sales revenue and units sold by sales representative.",
      tag: "Aggregation"
    },
    {
      title: "Regional Deal Size",
      prompt: "Find the top 3 sales regions ordered by total deal value.",
      tag: "Ranking"
    },
    {
      title: "Quota Attainment",
      prompt: "Filter and display all rows where actual revenue exceeded the sales target.",
      tag: "Performance"
    },
    {
      title: "Statistical Summary",
      prompt: "Display summary statistics (mean, min, max, total) for deal revenue and units.",
      tag: "Statistics"
    },
    {
      title: "Product Performance",
      prompt: "Which product line had the highest average deal margin?",
      tag: "Breakdown"
    }
  ],
  financial_budget: [
    {
      title: "Budget Variance",
      prompt: "Calculate total budget vs actual variance by department.",
      tag: "Formulas"
    },
    {
      title: "Top Expense Drivers",
      prompt: "Show the top 5 expense categories ordered by total amount.",
      tag: "Ranking"
    },
    {
      title: "Over-Budget Alerts",
      prompt: "Filter and display all line items where actual expenses exceeded the allocated budget.",
      tag: "Filtering"
    },
    {
      title: "Monthly Burn Rate",
      prompt: "Calculate average monthly expenses across all active operating cost centers.",
      tag: "Summary"
    },
    {
      title: "Department Comparison",
      prompt: "Compare quarterly budget allocations across all departments side-by-side.",
      tag: "Comparison"
    }
  ]
};

// -----------------------------------------------------------------------------
// 2. Column Classification & Formatting Helpers
// -----------------------------------------------------------------------------

function splitCamelOrSnake(str) {
  if (!str) return '';
  return str
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim();
}

function cleanColName(name) {
  return splitCamelOrSnake(name);
}

function cleanTableName(name) {
  return splitCamelOrSnake(name);
}

/**
 * Extracts a normalized list of column objects [{ name, type, is_pk, is_fk }]
 * handling SQL, NoSQL, CSV, and Excel table schemas.
 */
function extractNormalizedColumns(table) {
  if (!table) return [];

  if (Array.isArray(table.columns) && table.columns.length > 0) {
    return table.columns.map(c => {
      if (typeof c === 'string') return { name: c, type: '', is_pk: false, is_fk: false };
      return {
        name: c.name || '',
        type: String(c.type || '').toLowerCase(),
        is_pk: Boolean(c.is_pk),
        is_fk: Boolean(c.is_fk),
        fk_to_table: c.fk_to_table || null
      };
    });
  }

  if (Array.isArray(table.columns_meta) && table.columns_meta.length > 0) {
    return table.columns_meta.map(c => ({
      name: c.name || '',
      type: String(c.type || '').toLowerCase(),
      is_pk: false,
      is_fk: false,
      fk_to_table: null
    }));
  }

  if (Array.isArray(table.cols) && table.cols.length > 0) {
    return table.cols.map(c => {
      if (typeof c !== 'string') return { name: String(c), type: '', is_pk: false, is_fk: false };
      const match = c.match(/^([^\s(]+)(?:\s*\(([^)]+)\))?/);
      return {
        name: match ? match[1] : c,
        type: match && match[2] ? match[2].toLowerCase() : '',
        is_pk: c.includes('PK'),
        is_fk: c.includes('🔗'),
        fk_to_table: null
      };
    });
  }

  return [];
}

function isIdentifier(col) {
  if (col.is_pk || col.is_fk) return true;
  const n = (col.name || '').toLowerCase();
  if (n === 'id' || n === '_id' || n === 'pk' || n === 'fk' || n === 'uuid' || n === 'guid') return true;
  if (n.endsWith('_id') || n.endsWith('id') && n.length > 2 && /^[a-z]+[A-Z][a-z]*Id$/.test(col.name)) return true;
  return false;
}

function isDateColumn(col) {
  const t = (col.type || '').toLowerCase();
  const n = (col.name || '').toLowerCase();
  if (t.includes('date') || t.includes('time') || t.includes('timestamp') || t.includes('year') || t.includes('datetime')) return true;
  if (/date|timestamp|created_at|updated_at|hire_date|birth_date|invoicedate|order_date|createdat|updatedat|hiredate|birthdate/i.test(n)) return true;
  return false;
}

function isNumericMetric(col) {
  if (isIdentifier(col)) return false;
  const t = (col.type || '').toLowerCase();
  const n = (col.name || '').toLowerCase();

  const numericTypes = ['int', 'num', 'float', 'real', 'double', 'decimal', 'money', 'bigint', 'smallint'];
  const hasNumType = numericTypes.some(nt => t.includes(nt));

  const metricWords = [
    'total', 'price', 'amount', 'cost', 'budget', 'salary', 'revenue', 'sales',
    'balance', 'quantity', 'qty', 'score', 'rate', 'rating', 'discount',
    'milliseconds', 'bytes', 'margin', 'profit', 'expense', 'units', 'variance', 'actual', 'target'
  ];
  const hasMetricWord = metricWords.some(w => n.includes(w));

  return hasNumType || hasMetricWord;
}

function isCategoricalDimension(col) {
  if (isIdentifier(col) || isDateColumn(col) || isNumericMetric(col)) return false;
  const t = (col.type || '').toLowerCase();
  const n = (col.name || '').toLowerCase();

  const textTypes = ['char', 'text', 'string', 'str', 'object', 'nvarchar', 'varchar', 'enum'];
  const hasTextType = textTypes.some(tt => t.includes(tt));

  const dimensionWords = [
    'country', 'city', 'state', 'department', 'category', 'status', 'genre',
    'role', 'type', 'region', 'segment', 'brand', 'company', 'name', 'title',
    'firstname', 'lastname', 'billingcountry', 'billingcity', 'artist', 'album',
    'priority', 'model', 'method', 'currency'
  ];
  const hasDimensionWord = dimensionWords.some(w => n.includes(w));

  return hasTextType || hasDimensionWord;
}

function isNameOrTitleCol(col) {
  const n = (col.name || '').toLowerCase();
  return /name|title|company|firstname|lastname|track|album|product/i.test(n) && !isIdentifier(col);
}

// -----------------------------------------------------------------------------
// 3. Algorithmic Candidate Pool Generator
// -----------------------------------------------------------------------------

/**
 * Dynamically synthesizes analytical questions tailored to the active dataset's schema.
 */
export function synthesizeSchemaPrompts(tables = [], relationships = []) {
  const generated = [];

  if (!Array.isArray(tables) || tables.length === 0) {
    return generated;
  }

  // Pre-analyze each table
  const analyzedTables = tables.map(t => {
    const rawCols = extractNormalizedColumns(t);
    return {
      name: t.name || 'data',
      cleanName: cleanTableName(t.name || 'data'),
      count: t.count || 0,
      columns: rawCols,
      dateCols: rawCols.filter(isDateColumn),
      metricCols: rawCols.filter(isNumericMetric),
      catCols: rawCols.filter(isCategoricalDimension),
      nameCols: rawCols.filter(isNameOrTitleCol)
    };
  });

  // ---------------------------------------------------------------------------
  // A. Multi-Table Relational Prompts (Foreign Keys & Inferred References)
  // ---------------------------------------------------------------------------
  if (Array.isArray(relationships) && relationships.length > 0) {
    relationships.forEach(rel => {
      const fromTable = rel.from_table || rel.from_collection;
      const toTable = rel.to_table || rel.to_collection;

      if (!fromTable || !toTable) return;

      const tA = analyzedTables.find(t => t.name.toLowerCase() === fromTable.toLowerCase());
      const tB = analyzedTables.find(t => t.name.toLowerCase() === toTable.toLowerCase());

      if (tA && tB) {
        const metricCol = tA.metricCols[0] || tB.metricCols[0];
        const catCol = tB.catCols[0] || tA.catCols[0];
        const nameCol = tB.nameCols[0] || tA.nameCols[0];

        if (metricCol && catCol) {
          generated.push({
            title: "Cross-Table Analysis",
            prompt: `Join ${tA.name} and ${tB.name} to calculate total ${cleanColName(metricCol.name)} grouped by ${cleanColName(catCol.name)}.`,
            tag: "Relational Join"
          });
          generated.push({
            title: "Performance by Category",
            prompt: `Which ${cleanColName(catCol.name)} generated the highest aggregate ${cleanColName(metricCol.name)} across ${tA.name} and ${tB.name}?`,
            tag: "Join & Aggregation"
          });
        } else if (metricCol && nameCol) {
          generated.push({
            title: "Top Performers Across Tables",
            prompt: `Find the top 5 ${tB.name} records ordered by total ${cleanColName(metricCol.name)} in ${tA.name}.`,
            tag: "Relational Join"
          });
        } else {
          generated.push({
            title: "Connected Records",
            prompt: `Join ${tA.name} and ${tB.name} to view matching records with related details.`,
            tag: "Relational Join"
          });
        }
      }
    });
  }

  // ---------------------------------------------------------------------------
  // B. Single-Table Analytical Prompts
  // ---------------------------------------------------------------------------
  analyzedTables.forEach(t => {
    // 1. Date & Temporal Trend Prompts
    t.dateCols.forEach(dateCol => {
      if (t.metricCols.length > 0) {
        const metric = t.metricCols[0];
        generated.push({
          title: "Monthly Trend",
          prompt: `Show the monthly trend of ${cleanColName(metric.name)} over ${cleanColName(dateCol.name)} in ${t.name}.`,
          tag: "Timeline"
        });
        generated.push({
          title: "Timeline Distribution",
          prompt: `Calculate total ${cleanColName(metric.name)} grouped by year using ${cleanColName(dateCol.name)}.`,
          tag: "Timeline"
        });
      } else {
        generated.push({
          title: "Activity Over Time",
          prompt: `Show the distribution of ${t.name} records over ${cleanColName(dateCol.name)}.`,
          tag: "Timeline"
        });
      }
    });

    // 2. Numeric Rankings & Top-N Prompts
    t.metricCols.forEach(metric => {
      if (t.nameCols.length > 0) {
        const nameCol = t.nameCols[0];
        generated.push({
          title: "Top Ranking",
          prompt: `Find the top 5 ${t.name} with the highest ${cleanColName(metric.name)}, displaying their ${cleanColName(nameCol.name)}.`,
          tag: "Ranking"
        });
        generated.push({
          title: "Lowest Values",
          prompt: `Which 5 ${t.name} records have the lowest ${cleanColName(metric.name)}?`,
          tag: "Ranking"
        });
      } else {
        generated.push({
          title: "Top Records",
          prompt: `Find the top 5 records in ${t.name} ordered by ${cleanColName(metric.name)} descending.`,
          tag: "Ranking"
        });
      }

      // Statistical Overview
      generated.push({
        title: "Statistical Summary",
        prompt: `Calculate the average, minimum, and maximum ${cleanColName(metric.name)} across all ${t.name} records.`,
        tag: "Statistics"
      });
    });

    // 3. Categorical Breakdowns & Group By Prompts
    t.catCols.forEach(catCol => {
      if (t.metricCols.length > 0) {
        const metric = t.metricCols[0];
        generated.push({
          title: "Category Breakdown",
          prompt: `Calculate average ${cleanColName(metric.name)} grouped by ${cleanColName(catCol.name)} in ${t.name}.`,
          tag: "Analytics"
        });
        generated.push({
          title: "Distribution by Dimension",
          prompt: `Show total ${cleanColName(metric.name)} broken down by ${cleanColName(catCol.name)} in descending order.`,
          tag: "Breakdown"
        });
      } else {
        generated.push({
          title: "Record Count by Category",
          prompt: `Count total ${t.name} records grouped by ${cleanColName(catCol.name)}.`,
          tag: "Group By"
        });
      }
    });

    // 4. Data Preview & Profiling
    if (t.columns.length > 0) {
      const sampleCols = t.columns.slice(0, 3).map(c => cleanColName(c.name)).join(', ');
      generated.push({
        title: "Data Preview",
        prompt: `Preview the first 10 records from ${t.name} showing ${sampleCols}.`,
        tag: "Overview"
      });
    }
  });

  return generated;
}

// -----------------------------------------------------------------------------
// 4. Master Sampler & Diversity Shuffler
// -----------------------------------------------------------------------------

function shuffleArray(array) {
  const arr = [...array];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Returns a randomized, diverse selection of 3 to 4 prompts tailored to the dataset.
 * Combines seed prompts (if matching default dataset) with dynamic schema-synthesized prompts.
 * 
 * @param {Array} tables - Introspected tables/collections schema
 * @param {Array} relationships - Foreign keys / inferred relationships
 * @param {Object} currentDb - Active database metadata object
 * @param {number} sampleSize - Target number of prompts to return (default 4)
 * @returns {Array} Array of prompt objects { title, prompt, tag }
 */
export function generateDatasetPrompts(tables = [], relationships = [], currentDb = null, sampleSize = 4, _shuffleSeed = 0) {
  const dbId = (currentDb?.id || '').toLowerCase();
  
  // Step 1: Collect seed prompts if matching a pre-packaged dataset
  let seedPool = [];
  for (const [key, prompts] of Object.entries(SEED_PROMPTS)) {
    if (dbId.includes(key)) {
      seedPool = prompts;
      break;
    }
  }

  // Step 2: Dynamically synthesize schema-aware prompts
  const dynamicPool = synthesizeSchemaPrompts(tables, relationships);

  // Step 3: Combine and deduplicate on prompt text
  const combined = [...seedPool, ...dynamicPool];
  const seenTexts = new Set();
  const uniquePool = [];

  for (const item of combined) {
    if (!item || !item.prompt) continue;
    const normalized = item.prompt.toLowerCase().trim();
    if (!seenTexts.has(normalized)) {
      seenTexts.add(normalized);
      uniquePool.push(item);
    }
  }

  // Fallback if pool is empty (e.g. empty or uninspected dataset)
  if (uniquePool.length === 0) {
    return [
      {
        title: "Data Preview",
        prompt: `Count total records and preview the first 10 entries from ${currentDb?.name || 'this dataset'}.`,
        tag: "Overview"
      },
      {
        title: "Schema Inspection",
        prompt: "List all available tables, column definitions, and data types.",
        tag: "Schema"
      },
      {
        title: "Summary Statistics",
        prompt: "Show summary statistics for all numeric metrics in the dataset.",
        tag: "Statistics"
      },
      {
        title: "Category Breakdown",
        prompt: "Show distinct categories and count of records for each.",
        tag: "Analytics"
      }
    ];
  }

  // Step 4: Diverse Category Sampling
  // Strive to pick prompts with distinct tags so the user sees a rich mix
  // (e.g., 1 Relational/Join, 1 Timeline, 1 Ranking, 1 Breakdown/Analytics)
  const shuffledPool = shuffleArray(uniquePool);
  const selected = [];
  const usedTags = new Set();

  // First pass: pick one prompt per unique tag
  for (const item of shuffledPool) {
    if (!usedTags.has(item.tag)) {
      selected.push(item);
      usedTags.add(item.tag);
      if (selected.length >= sampleSize) break;
    }
  }

  // Second pass: if we still need more to reach sampleSize, fill from remaining items
  if (selected.length < sampleSize) {
    for (const item of shuffledPool) {
      if (!selected.includes(item)) {
        selected.push(item);
        if (selected.length >= sampleSize) break;
      }
    }
  }

  // Final shuffle of the selected items so display order varies
  return shuffleArray(selected);
}
