# PROJECT PLAN --- AI Data Analyst System

## 1. Project Name and One-Sentence Problem

### Project Name

AI Data Analyst System

### Problem

Business users often have useful CSV data but cannot easily answer
questions from it because they do not know Pandas or data-analysis code.

The system will allow a user to upload a CSV file, ask questions in
natural language, and receive a clear answer based only on the uploaded
data.

### Realistic Example

A business user uploads an orders CSV file and asks:

> "Which product has the highest total quantity sold?"

Instead of writing Pandas code manually, the user asks the question
directly and the system performs the required analysis.

---

## 2. Target User and Goal

### Target User

The target user is a business user, manager, employee, or other
non-technical user who works with CSV data but does not know how to
write Python or Pandas queries.

### User Goal

In one visit, the user should be able to:

1. Upload a CSV file.

2. Inspect a basic preview of the dataset.

3. Ask a natural-language question about the data.

4. Receive a clear answer, supporting number/table, and a chart when
requested or useful.

---

## 3. Scope

### The System WILL

1. Upload and read valid CSV files.

2. Display basic dataset information such as row count, column count,
column names, inferred data types, and the first five rows.

3. Accept natural-language questions about the uploaded dataset.

4. Check whether the requested analysis can be answered from the
current data.

5. Build an analysis plan using approved data-analysis tools.

6. Perform approved Pandas operations such as filtering, grouping,
aggregation, sorting, column selection, limiting results, and chart
creation.

7. Ask for clarification when a question is ambiguous.

8. Return a clear plain-English result with a supporting number or
small table.

9. Clearly identify filters that were applied.

10. Generate a chart when the user explicitly requests one or when a
visualization is appropriate.

### The System WILL NOT

1. Answer questions that require information not present in the
uploaded dataset.

2. Execute unrestricted AI-generated Python code.

3. Invent missing columns, values, or facts.

4. Modify the user's original uploaded CSV file.

5. Perform unsupported advanced tasks such as forecasting unless a
dedicated approved tool is added later.

### Out-of-Scope Example

User question:

> "Predict next year's sales."

If forecasting is not part of the approved tool set, the system should
explain that this request is outside the current scope instead of
generating a prediction.

---

## 4. Input Contract

The system accepts two main user inputs:

1. A CSV file.

2. A natural-language question about the uploaded data.

### A. CSV File

- **Required:** Yes

- **Type:** `.csv`

- **Example:** `orders.csv`

The uploaded file must:

- Be a readable CSV file.

- Contain at least one usable row.

- Have valid column names.

- Not contain duplicate column names.

The application itself is not limited to the sample Orders dataset. It
will inspect the actual schema of each uploaded CSV dynamically.

#### If No File Is Uploaded

The system will ask the user to upload a CSV file before analysis can
begin.

#### If the File Is Unsupported or Unreadable

The system will reject the file, display a useful error message, and
stop the analysis.

#### If the Dataset Is Empty

The system will reject the dataset and explain that there are no usable
rows to analyze.

### B. Natural-Language Question

- **Required:** Yes

- **Type:** Text

- **Example:** `Which product has the highest total quantity
sold?`

#### If the Question Is Empty

The system will ask the user to enter a question.

#### If the Question Is Ambiguous

The Agent will ask a specific clarification question instead of
guessing.

Example:

User:

> "What is the best product?"

Agent:

> "Do you mean the product with the highest revenue, highest quantity
sold, or highest number of orders?"

#### If the Question Refers to Missing Data

The system will explain that the requested information is not available
in the current dataset.

---

## 5. Output Contract

The system will return a clear result based only on the uploaded dataset
and the user's question.

Depending on the request, the output may include:

- A short plain-English answer.

- A numeric result.

- A small supporting table.

- A chart.

- A clarification question.

- An error or limitation message.

The system will also clearly identify any filters used in the analysis.

### Example Output

User question:

> "Which product has the highest total quantity sold?"

Example answer:

> "Laptop has the highest total quantity sold with 120 units."

Supporting table:

| Product | Total Quantity |

|---|---:|

| Laptop | 120 |

| Phone | 95 |

| Tablet | 82 |

Analysis summary:

`Group by Product → Sum Quantity → Sort descending → Return top
result`

If a filter was used, the output should state it clearly, for example:

> `Filter applied: Country = Palestine`

---

## 6. Workflow

### Main Workflow

1. User uploads a CSV file.

2. The system validates the file.

3. Pandas loads the dataset.

4. The system checks data quality and normalizes safe data types.

5. The system extracts the actual dataset schema.

6. The system displays row/column counts, column names, inferred data
types, and the first five rows.

7. The user enters a natural-language question.

8. The system validates the question.

9. The Agent checks whether the question can be answered from the
current dataset.

10. If the question is clear and answerable, the Agent builds an
analysis plan using approved tools.

11. The system validates the Agent's plan.

12. Approved Pandas operations are executed.

13. The result is formatted into plain English with a supporting
number/table.

14. Filters used are displayed clearly.

15. A chart is displayed if requested or appropriate.

16. The question and result are saved in the current session history.

17. The system finishes the current request.

### Workflow Diagram

```text

CSV Upload

   ↓

File Validation

   ↓

Data Quality Checks / Type Normalization

   ↓

Load with Pandas

   ↓

Extract Actual Schema

   ↓

Show Dataset Preview

   ↓

User Question

   ↓

Question Validation

   ↓

Agent Decision

   ├── Ambiguous → Ask for clarification

   ├── Missing data → Explain limitation

   ├── Unsupported request → Explain scope limitation

   └── Clear and answerable

            ↓

      Build Analysis Plan

            ↓

      Validate Plan

            ↓

      Execute Approved Tools

            ↓

      Result / Table / Chart

            ↓

      Save in Session History

            ↓

          Finish

```

### Alternative Paths

- No file uploaded → Ask the user to upload a CSV file.

- Unreadable/unsupported file → Reject the file with a useful message.

- Empty dataset → Reject it.

- Duplicate column names → Stop and ask the user to fix them.

- Ambiguous question → Ask for clarification.

- Missing required column/data → Explain that the question cannot be
answered from the current data.

- Invalid Agent plan → Reject the plan and return a safe error.

- Tool failure → Show a useful error instead of inventing a result.

---

**## 7. Agent Specification

Agent Goal

The Agent's goal is to understand the user's question about the uploaded
CSV file, determine whether the question can be answered from the
current data, build a safe analysis plan using approved tools, and
return a structured result that can be executed and explained.

Final Agent Architecture

The final implementation uses a planner → validator → executor →
explainer architecture.

The LLM is responsible for planning and decision-making only. It does
not generate or execute arbitrary Python/Pandas code.

User Question
      ↓
app.py
      ↓
agent/state.py
Create Agent State
      ↓
agent/core.py
LLM Planner
      ↓
Structured JSON Output
      ↓
agent/validators.py
Validate Agent Output + Analysis Plan
      ↓
Approved Tool Plan
      ↓
tools.py
Safe Pandas Operations
      ↓
Actual Result
      ↓
agent/explainer.py
LLM Explanation
      ↓
Answer + Supporting Result
      ↓
charting.py
Deterministic Chart Validation / Rendering
      ↓
ui.py
Streamlit Presentation

Final Project Structure

AI Data Analyst/
│
├── app.py
├── ui.py
├── data_utils.py
├── validation.py
├── tools.py
├── charting.py
│
└── agent/
    ├── __init__.py
    ├── state.py
    ├── core.py
    ├── schemas.py
    ├── validators.py
    ├── prompts.py
    └── explainer.py

Responsibility of Each File

app.py

Application entry point and workflow orchestrator.

Responsibilities:

Configure the Streamlit application.

Load custom UI styling.

Manage st.session_state.

Receive uploaded files from the UI.

Load and prepare the dataset.

Build the dataset schema.

Validate the user's question.

Create the Agent state.

Run the Agent.

Execute the approved analysis plan.

Generate the final explanation.

Render results and charts.

Save successful analyses to session history.

Handle high-level errors and status branches.

app.py should coordinate the system rather than contain the
implementation details of validation, tools, planning, or chart
rendering.

ui.py

Presentation layer.

Responsibilities:

Custom CSS.

Header.

Sidebar.

File uploader.

Dataset summary.

Question input.

Suggested questions.

Answer card.

Result table.

History display.

Empty states.

UI-level error/warning presentation.

ui.py does not perform data analysis or Agent reasoning.

data_utils.py

Dataset loading and schema utilities.

Responsibilities:

Read uploaded CSV files.

Detect duplicate column names before Pandas processing.

Handle file-reading errors.

Return the loaded DataFrame.

Extract the actual schema with get_schema(df).

Main functions:

load_csv(uploaded_file)

get_schema(df)

validation.py

Deterministic dataset and question validation.

Responsibilities:

Validate dataset quality.

Check missing values.

Detect duplicate rows.

Normalize safe numeric/date types.

Track unavailable columns.

Preserve the original dataset and work on a normalized working copy.

Validate that the question is not empty.

Main flow:

validate_dataframe()
        ↓
normalize_dataframe()
        ↓
re-check data quality
        ↓
prepare_dataframe()

prepare_dataframe() returns the prepared working DataFrame together
with errors, warnings, unavailable columns, and conversion information.

tools.py

Approved, deterministic Pandas operations.

The Agent does not write Pandas code directly. It selects from these
predefined operations:

filter_data

aggregate_data

sort_data

select_columns

limit_results

aggregate_data supports optional group_by, so a separate
group_data tool is not required.

Examples:

filter_data
aggregate_data + group_by
sort_data
limit_results

These functions receive a DataFrame and return a controlled result.

charting.py

Deterministic chart validation and rendering.

Responsibilities:

Validate whether a chart plan is structurally valid.

Validate that chart columns exist in the actual final result.

Validate data types required by the selected chart.

Validate basic chart semantics.

Render supported charts.

Supported chart types:

Bar

Line

Pie

Scatter

Chart rendering is not an unrestricted LLM-generated operation.

agent/state.py

Defines Agent state and status constants.

Example statuses:

pending
ready
needs_clarification
cannot_answer
completed
failed

create_agent_state() initializes the state used during one analysis
request.

The state contains information such as:

question

schema

unavailable columns

status

analysis plan

chart plan

message

result

answer

error

agent/core.py

Agent execution and orchestration.

Responsibilities:

Build the Agent input.

Send the planning prompt to the LLM.

Parse the LLM response.

Validate the response through agent/validators.py.

Retry when the Agent output is invalid.

Update Agent state.

Return a controlled Agent state to app.py.

The core Agent does not execute arbitrary Python code.

agent/schemas.py

Defines the allowed structure and constraints for Agent tool planning.

It contains the approved tool schemas, including:

filter_data
aggregate_data
sort_data
limit_results
select_columns

It also defines allowed operators, aggregation operations, parameter
requirements, and type expectations.

agent/validators.py

Deterministic validation of Agent output.

Responsibilities:

Parse structured JSON.

Validate the Agent status.

Validate the analysis plan.

Validate required parameters.

Validate parameter types.

Validate allowed operators and operations.

Validate referenced columns.

Validate analysis-plan type flow.

Validate the chart plan.

Reject unsafe or malformed Agent output.

The validator acts as the safety boundary between the LLM and the
execution layer.

agent/prompts.py

Contains prompts used by the Agent.

The planner prompt instructs the LLM to:

Use the actual dataset schema.

Detect ambiguity.

Detect unavailable data.

Select only approved tools.

Return structured output.

Create a chart plan only when useful or explicitly requested.

Never generate arbitrary Python code.

Retry prompts are also generated when the first Agent output fails
validation.

agent/explainer.py

Converts the actual executed result into a user-facing explanation.

Flow:

Actual Pandas Result
        ↓
Serialize Result
        ↓
LLM Explainer
        ↓
Structured JSON
        ↓
Validate summary
        ↓
Plain-English Answer

The explainer does not perform the analysis itself. It explains the
result that was already produced by the approved Pandas tools.

Final Approved Analysis Tools

The final implementation uses:

filter_data

aggregate_data

sort_data

select_columns

limit_results

A separate group_data tool was intentionally removed because grouping
is handled through the optional group_by parameter of
aggregate_data.

The Agent does not directly use create_chart, ask_for_clarification,
or return_result as executable tools. These are represented through
the structured Agent output, status values, chart plans, and application
workflow.

Example Multi-Step Analysis Plan

For:

"Which product has the highest total quantity?"

The Agent may produce:

aggregate_data
    column = Quantity
    operation = sum
    group_by = Product

→ sort_data
    column = Quantity
    ascending = false

→ limit_results
    limit = 1

The plan is validated before execution.

Agent Output States

The planner can return one of the controlled states:

ready

The question is answerable and a valid analysis plan exists.

needs_clarification

The question has multiple reasonable interpretations.

The Agent returns a clarification message and no executable analysis
plan.

cannot_answer

The requested information is unavailable or outside the supported scope.

The Agent returns an explanation and no executable analysis plan.

failed

A safe failure occurred during planning or validation.

The application displays an error instead of inventing a result.

completed

The full workflow has successfully produced the final answer.

Agent Decision Rules

Use only the actual uploaded dataset schema.

Never invent columns or values.

Detect ambiguity instead of guessing.

Detect unavailable data.

Use only approved analysis tools.

Validate every Agent plan before execution.

Never execute unrestricted AI-generated Python.

Execute the plan only after deterministic validation succeeds.

Explain only the actual executed result.

Stop after a valid result, clarification, limitation, or safe
failure.

Retry and Error Handling

If the LLM returns invalid structured output:

LLM Output
    ↓
Validation
    ↓
Invalid
    ↓
Retry Prompt
    ↓
LLM
    ↓
Validation Again

The retry process is bounded. If the output remains invalid, the Agent
returns a safe failure rather than executing an unvalidated plan.

Stop Conditions

The Agent stops the current request when:

A valid analysis result is produced.

Clarification is required.

The question cannot be answered from the dataset.

The request is outside the supported scope.

The Agent output remains invalid after the allowed retry attempts.

A safe execution or validation error prevents completion.

Tool Permissions

The Agent may:

Read the dataset schema.

Read unavailable-column information.

Read the user's question.

Select approved analysis tools.

Request a supported chart.

Ask for clarification through its structured status.

The Agent may not:

Execute arbitrary Python.

Generate executable Pandas code.

Access external data.

Invent data.

Modify the original uploaded dataset.

8. Data Preparation**

A small, non-sensitive CSV dataset will be used for development and
testing.

For the sample dataset, the project will use an Orders dataset with at
least 30 rows and at least 4 meaningful columns.

The application itself will not be limited to Orders data. It may accept
other valid CSV datasets and will inspect their actual schema
dynamically.

### Sample Dataset Columns

| Column | Type | Example |

|---|---|---|

| Order_ID | Integer/String | 1001 |

| Product | String | Laptop |

| Category | String | Electronics |

| Quantity | Integer | 3 |

| Price | Float | 750.00 |

| Country | String | Palestine |

| Status | String | Completed |

### Possible Data Problems

The uploaded dataset may contain:

- Missing values.

- Empty rows.

- Duplicate rows.

- Duplicate column names.

- Empty columns.

- Invalid numeric values.

- Incorrectly inferred data types.

- Inconsistent text values.

### Data Validation and Handling

The system will apply rule-based validation before analysis.

#### 1. File-Level Validation

- Reject unreadable or unsupported files.

- Reject empty datasets.

- Reject datasets with duplicate column names.

- Reject datasets when the overall missing-value ratio exceeds a
predefined project threshold.

#### 2. Column-Level Validation

- Detect completely empty columns.

- Detect columns with excessive missing values.

- Mark columns with insufficient valid data as unavailable for
analysis, without removing them from the original dataset.

#### 3. Duplicate Rows

- Calculate the percentage of duplicate rows.

- Warn the user when duplicates exceed a predefined warning threshold.

- Reject or require review when duplicates exceed a predefined maximum
threshold.

- Do not silently delete duplicate rows because they may represent
valid repeated records.

#### 4. Data Type Normalization

The system will attempt safe type correction before analysis.

- Columns that are mostly numeric may be converted to numeric types.

- Columns that are mostly valid dates may be converted to datetime.

- Failed conversions will become missing values and will be reported.

- A conversion will only be accepted if the valid-conversion rate
exceeds a predefined threshold.

- The system will not silently force a column into an incompatible
type.

#### 5. Missing Values After Conversion

- Recalculate missing-value ratios after type normalization.

- Continue only when enough valid data remains for the requested
analysis.

- If missing values affect the result, clearly inform the user.

Example:

> "Average Quantity = 4.0, calculated using 2 non-missing values. 1 row
had a missing Quantity value."

#### 6. Data Preservation

- Keep the original uploaded dataset unchanged.

- Perform validation and normalization on a working copy.

Conceptually:

```python

original_df = df.copy()

working_df = df.copy()

```

### Data Checks Shown to the User

The system will display or calculate:

1. Whether the CSV file can be read.

2. Whether the dataset is empty.

3. Whether duplicate column names exist.

4. Number of rows and columns.

5. Column names and inferred data types.

6. Missing-value information.

7. Duplicate-row information.

8. The first five rows.

### Initial Quality Threshold Policy

The exact thresholds will be stored as constants in the application so
they can be tested and changed easily.

Initial project values:

- Reject the dataset if more than **40% of all cells are
missing**.

- Mark a column unavailable for analysis if more than **70% of its
values are missing**.

- Warn the user if duplicate rows exceed **10%** of the
dataset.

- Reject or require review if duplicate rows exceed **50%** of
the dataset.

- Accept automatic numeric/date conversion only when at least **95%
of non-empty values** convert successfully.

These thresholds are project design rules, not requirements imposed by
the original assignment.

---

## 9. Interface Sketch

```text

+------------------------------------------------------+

|                 AI Data Analyst                      |

+------------------------------------------------------+

Upload CSV File

[ Choose File ]

Dataset Information

Rows: 50

Columns: 7

Columns:

Order_ID, Product, Category, Quantity, Price, Country...

Data Quality Summary:

Missing values: 2.1%

Duplicate rows: 0%

Unavailable columns: None

Dataset Preview:

+----------------------------------------------------+

| Order_ID | Product | Quantity | Price | Country   |

+----------------------------------------------------+

| 1001     | Laptop  | 2        | 750   | Palestine |

| ...                                                |

+----------------------------------------------------+

Ask a question about your data:

[ Which product has the highest total quantity? ]

[ Analyze ]

Result

Laptop has the highest total quantity with 120 units.

Supporting Table:

+----------------------------+

| Product | Total Quantity   |

+----------------------------+

| Laptop  | 120              |

+----------------------------+

Filter applied: None

[ Chart if requested or appropriate ]

Clarification / Error Area

Example:

"What do you mean by 'best product'?

Highest revenue, quantity, or number of orders?"

Question History

- Which product has the highest total quantity?

- Show orders from Palestine.

```

Charts must use an appropriate pair of columns and include clear axis
labels.

---

## 10. Success Tests

At least five tests will be written before implementation and then
recorded again with actual results after testing.

### T1 --- Normal Valid Request

**Input:** Valid CSV file.

**Question:**

> "How many orders are there?"

**Expected Behavior:**

The system returns the correct number of orders.

---

### T2 --- Filter Request

**Question:**

> "Show orders from Palestine."

**Expected Behavior:**

The Agent selects a filtering operation, returns only matching rows, and
clearly shows the filter that was applied.

---

### T3 --- Multi-Step Analysis

**Question:**

> "Which product has the highest total quantity?"

**Expected Behavior:**

The Agent builds a multi-step plan:

`Group by Product → Sum Quantity → Sort descending → Return top
result`

The final answer must match an independent Pandas/manual check.

---

### T4 --- Ambiguous Request

**Question:**

> "What is the best product?"

**Expected Behavior:**

The Agent asks for clarification instead of guessing.

Example:

> "Do you mean best by revenue, quantity sold, or number of orders?"

---

### T5 --- Missing Column

**Dataset columns:** Product, Quantity, Category

**Question:**

> "Which salesperson sold the most?"

**Expected Behavior:**

The system explains that Salesperson information does not exist in the
current dataset.

---

### T6 --- Invalid / Empty File

**Input:** Empty or unreadable CSV file.

**Expected Behavior:**

The application displays a useful error message and does not crash.

---

### T7 --- Chart Request

**Question:**

> "Show the top 5 products by total quantity as a bar chart."

**Expected Behavior:**

The Agent performs the required analysis and displays a bar chart using
appropriate columns with labeled axes.

---

### T8 --- Out-of-Scope Request

**Question:**

> "Predict next year's sales."

**Expected Behavior:**

If forecasting is not supported by an approved tool, the system clearly
explains that the request is outside the current scope.

---

### T9 --- Missing-Value Boundary Case

**Situation:** Overall missing-value percentage is exactly at
the configured acceptance threshold.

**Expected Behavior:**

The system follows the documented threshold rule consistently and does
not apply an unstated rule.

---

### T10 --- Invalid Data Type / Safe Conversion

**Situation:** A mostly numeric column contains a small number
of invalid text values.

**Expected Behavior:**

The system attempts safe numeric conversion, reports failed conversions,
recalculates missing values, and only continues if the configured
conversion and quality thresholds are satisfied.

---

### T11 --- Duplicate-Row Quality Case

**Situation:** Duplicate-row percentage exceeds the warning
threshold but remains below the maximum rejection threshold.

**Expected Behavior:**

The system warns the user but does not silently delete duplicates.

---

## 11. Technology Plan

### Existing Knowledge from Session 16

The project will reuse the following concepts:

- Agent goal.

- State.

- Allowed actions/tools.

- Agent decision-making.

- Clarification handling.

- Pandas operations.

- Stop conditions.

### New Tools / Techniques to Learn

#### Streamlit

**Purpose:** Build the web interface.

Used for:

- CSV upload.

- Question input.

- Buttons.

- Dataset preview.

- Result area.

- Clarification/error messages.

- Session state.

- Charts if using built-in Streamlit chart components.

Documentation:

https://docs.streamlit.io/

#### Plotly or Streamlit Charts

**Purpose:** Visualize analysis results.

Used for:

- Bar charts.

- Line charts.

- Pie charts.

- Scatter plots.

Documentation:

https://plotly.com/python/

#### Pandas

**Purpose:** Load, validate, normalize, and analyze CSV data.

Documentation:

https://pandas.pydata.org/docs/

### Technology Roles

**Streamlit:**

Handles the user interface and app reruns.

**Agent:**

Understands the user's question, checks answerability, requests
clarification when necessary, and creates a safe analysis plan using
approved tools.

**Pandas / Data Layer:**

Loads the CSV, performs validation and type normalization, and executes
the approved data-analysis operations.

**Session State:**

Keeps the current dataset and question history across normal Streamlit
reruns.

When a new CSV file is uploaded, incompatible history and previous
analysis results will be cleared.

**Plotly / Streamlit Charts:**

Displays visual results using appropriate columns and labeled axes.

---

## 12. Build Order

The system will be built in the required project order.

### Minimum Working Version

The following features must work before optional improvements are added:

1. Add CSV upload.

   - Reject unsupported or unreadable files.

   - Explain what to do when no file is uploaded.

2. Load the dataset using Pandas.

   - Show row count.

   - Show column count.

   - Show column names.

   - Show the first five rows.

   - Flag empty files.

   - Flag duplicate column names.

3. Allow the user to enter a natural-language question.

   - Pass the question together with the actual dataset schema to the
Agent.

4. Check answerability.

   - Detect ambiguous questions.

   - Detect requests for missing columns/data.

   - Ask for clarification instead of inventing an answer.

5. Build and execute an approved analysis plan.

   - Use approved tools such as filter, aggregate, sort, column
selection, and result limiting.

   - Support multiple approved steps when the request requires them.

   - Do not execute unrestricted AI-generated Python code.

6. Display the result.

   - Plain-English answer.

   - Supporting number or small table.

   - Clearly identify any filters used.

7. Add at least one chart.

   - Use the validated charting layer with Streamlit and Altair.

   - Use an appropriate column pair.

   - Label axes clearly.

8. Add session behavior.

   - Keep the current dataset across normal app reruns.

   - Keep question history across normal app reruns.

   - Clear incompatible history and previous results when a new file is
loaded.

### Required Data-Quality Improvements

After the basic flow works:

1. Add rule-based missing-value checks.

2. Add duplicate-row percentage checks.

3. Add safe numeric/date type normalization.

4. Track columns that are unavailable for reliable analysis.

5. Report conversion failures and quality warnings.

6. Preserve the original uploaded dataset unchanged.

### Optional Enhancements

After all required features work correctly:

- More approved analysis tools.

- Automatic chart recommendations.

- Additional chart types.

- Export analysis results.

- Dataset quality summary/dashboard.

- More advanced date-based analysis.

- More advanced aggregation options.

---

**## 12. Final Implemented Architecture

The implementation is intentionally separated into five layers:

1. Presentation Layer

app.py
ui.py

Streamlit handles user interaction, session state, layout, and
presentation.

2. Data Layer

data_utils.py
validation.py

This layer loads CSV files, validates data quality, normalizes safe data
types, extracts schema information, and prepares a working DataFrame.

3. Agent Layer

agent/state.py
agent/core.py
agent/schemas.py
agent/validators.py
agent/prompts.py
agent/explainer.py

This layer handles LLM planning, structured output, validation, retry
logic, state management, and explanation generation.

4. Execution Layer

tools.py

Only predefined Pandas operations are executable. The LLM never executes
generated Python code.

5. Visualization Layer

charting.py

Charts are selected through a validated chart plan and rendered
deterministically from the actual result.

End-to-End Implementation Flow

CSV Upload
    ↓
data_utils.py
    ↓
validation.py
    ↓
working_df + schema + unavailable columns
    ↓
app.py
    ↓
agent/state.py
    ↓
agent/core.py
    ↓
LLM Planner
    ↓
agent/validators.py
    ↓
Approved Analysis Plan
    ↓
tools.py
    ↓
Actual Pandas Result
    ↓
agent/explainer.py
    ↓
Final Plain-English Answer
    ↓
charting.py
    ↓
ui.py
    ↓
Session History

Important Architectural Decision

The final system does not contain an executor.py layer.

Execution is handled directly through the approved functions in
tools.py, after the plan has passed deterministic validation in
agent/validators.py.

This keeps the execution boundary simple:

LLM
 ↓
Structured Plan
 ↓
Validator
 ↓
Approved Tool Functions
 ↓
Pandas Result

The LLM is therefore a planner and explainer, while deterministic Python
code remains responsible for validation and data execution.

LLM Responsibilities vs Python Responsibilities

Responsibility                           LLM                Python

Understand natural-language question       ✓
Detect ambiguity                           ✓          ✓ validation
Decide whether data is sufficient          ✓   ✓ schema validation
Build analysis plan                        ✓
Validate plan safety                                             ✓
Execute Pandas operation                                         ✓
Calculate actual result                                          ✓
Decide chart intent                        ✓
Validate chart against result                                    ✓
Render chart                                                     ✓
Explain actual result                      ✓
Maintain session state                                           ✓

This separation is the core safety principle of the implementation.

Final Design Summary**

The project will build a generic AI-powered CSV Data Analyst rather than
a system limited to one business domain. An Orders dataset will be used
as the main development and testing sample, but the Agent will inspect
the actual schema of every uploaded CSV.

The Agent will act as a planner and decision-maker, not as an
unrestricted code generator. It will create one-step or multi-step plans
using approved analysis tools. Deterministic validation will approve the
plan before the functions in tools.py execute the Pandas operations.
Streamlit will provide the user interface and session handling.

The system will prioritize safe validation, clarification instead of
guessing, transparent handling of filters and data-quality problems, and
readable answers supported by numbers, tables, and charts.