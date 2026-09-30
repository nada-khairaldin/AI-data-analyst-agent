
# AI Data Analyst Agent

An AI-powered data analysis application that allows users to upload CSV files and ask questions about their data using natural language.

The system understands the user's request, checks whether it can be answered using the uploaded dataset, handles ambiguous or incomplete questions, generates a structured analysis plan, validates it, executes controlled Pandas operations, and returns clear results with supporting tables or visualizations.

---

## Overview

Many users work with CSV files but do not know how to write Pandas queries or data analysis code.

The **AI Data Analyst Agent** provides a simple interface where users can upload a dataset and ask questions such as:

- What is the total revenue?
- Which product generated the highest revenue?
- What is the average price?
- Show total revenue by country.
- What are the top 5 products by quantity sold?

Instead of generating and executing unrestricted Python code, the system converts natural-language questions into structured and validated analysis plans using a controlled set of supported operations.

---

## Key Features

- Upload and validate CSV files
- Preview dataset rows
- Display dataset dimensions and schema
- Ask questions using natural language
- Detect ambiguous or incomplete requests
- Ask for clarification instead of guessing
- Detect missing or unsupported columns
- Generate structured analysis plans
- Validate agent-generated plans before execution
- Execute controlled Pandas operations
- Return plain-language answers
- Display supporting tables
- Generate relevant data visualizations
- Maintain application state across Streamlit reruns
- Handle invalid input and execution failures gracefully
- Prevent unrestricted AI-generated Python execution

---

## Agent Workflow

The application follows an agent-based workflow:

```text
CSV Upload
    |
    v
Dataset Validation
    |
    v
Dataset Preview & Schema
    |
    v
User Question
    |
    v
Input Validation
    |
    v
Agent Decision
    |
    +-----------------------------+
    |                             |
    v                             v
Needs Clarification          Clear Request
    |                             |
    v                             v
Ask User                  Generate Analysis Plan
                                  |
                                  v
                           Validate Plan
                                  |
                     +------------+------------+
                     |                         |
                     v                         v
                Invalid Plan              Valid Plan
                     |                         |
                     v                         v
                Safe Failure            Execute Pandas
                                               |
                                               v
                                         Format Result
                                               |
                                               v
                                     Answer + Table / Chart
```

---

## Agent Responsibilities

The agent is responsible for:

- Understanding the user's question
- Checking whether the question can be answered using the current dataset
- Detecting ambiguous or incomplete requests
- Asking for clarification instead of guessing
- Selecting an approved analysis action
- Returning a structured analysis plan
- Explaining the result clearly

The agent does **not** execute unrestricted AI-generated Python code.

---

## Supported Analysis Operations

The system supports controlled data analysis operations such as:

- Filtering
- Counting
- Summation
- Average calculation
- Grouping
- Sorting
- Top-N analysis
- Basic comparisons

Only approved operations are executed.

---

## Example Questions

Examples of questions the system can answer:

```text
What is the total revenue?
```

```text
Which product generated the highest revenue?
```

```text
What is the average price?
```

```text
Show total revenue by country.
```

```text
What are the top 5 products by quantity sold?
```

The system also handles ambiguous questions such as:

```text
What is the best product?
```

Instead of guessing, the agent can ask whether "best" means:

- highest revenue
- highest quantity sold
- highest number of orders

---

## Tech Stack

- Python
- Streamlit
- Pandas
- LLM API
- Structured JSON Outputs
- Plotly / Streamlit Charts
- Session State
- Git & GitHub

---

## Project Structure

```text
ai-data-analyst-agent/
│
├── app.py
│
├── agent/
│   ├── core.py
│   ├── prompts.py
│   ├── validator.py
│   └── state.py
│
├── analysis/
│   ├── executor.py
│   └── operations.py
│
├── utils/
│   └── data_utils.py
│
├── data/
│   └── sample_data.csv
│
├── tests/
│   └── test_cases.md
│
├── PROJECT_PLAN.md
├── TEST_RESULTS.md
├── requirements.txt
├── .gitignore
└── README.md
```

> Update this section if the final project structure is different.

---

## How It Works

### 1. Upload Dataset

The user uploads a CSV file through the Streamlit interface.

The system validates the file and checks:

- whether the file can be read
- whether the file is empty
- whether column names are duplicated
- the number of rows and columns
- available column names
- dataset structure

---

### 2. Preview Dataset

After successful validation, the application displays:

- number of rows
- number of columns
- column names
- dataset schema
- first rows of the dataset

This helps the user understand what information is available before asking questions.

---

### 3. Ask a Question

The user enters a natural-language question related to the uploaded dataset.

Example:

```text
Which country generated the highest revenue?
```

---

### 4. Agent Analysis

The agent receives:

- the user's question
- dataset schema
- available columns
- supported operations

The agent then determines whether the request is:

- answerable
- ambiguous
- incomplete
- unsupported
- dependent on a missing column

---

### 5. Clarification

If the request is ambiguous, the agent asks the user for clarification instead of assuming the intended meaning.

For example:

```text
What is the best product?
```

may require clarification because "best" could refer to:

- revenue
- quantity
- number of orders

---

### 6. Generate Analysis Plan

For valid and clear requests, the agent generates a structured analysis plan.

A plan may contain operations such as:

```text
Group by Country
→ Sum Revenue
→ Sort Descending
→ Return Top Result
```

---

### 7. Validate Analysis Plan

The generated plan is validated before execution.

The validator checks whether:

- requested columns exist
- requested operations are supported
- required values are present
- the output structure is valid
- the plan follows the allowed analysis rules

Invalid plans are rejected instead of being executed.

---

### 8. Execute Analysis

The validated plan is translated into controlled Pandas operations.

The LLM does not directly execute arbitrary Python code.

---

### 9. Display Result

The application displays:

- a plain-language answer
- supporting number or table
- filters or grouping used
- visualization when appropriate

---

## Example Workflow

```text
Upload CSV
   ↓
Validate Dataset
   ↓
Preview Data & Schema
   ↓
Ask:
"Which country has the highest revenue?"
   ↓
Agent checks dataset schema
   ↓
Agent creates plan:
Group by Country
→ Sum Revenue
→ Sort Descending
→ Select Top Result
   ↓
System validates plan
   ↓
Pandas executes analysis
   ↓
Result:
"Country X generated the highest revenue with $XX,XXX."
   ↓
Supporting table / chart displayed
```

---

## Validation and Error Handling

The system is designed to handle invalid or unexpected situations without crashing.

Handled cases include:

- No CSV uploaded
- Unsupported file
- Invalid or unreadable CSV
- Empty dataset
- Duplicate column names
- Empty question
- Missing columns
- Ambiguous requests
- Unsupported requests
- Invalid agent output
- Invalid analysis plan
- Execution errors
- Questions that cannot be answered from the current dataset

Instead of inventing an answer, the application returns a clear clarification, warning, or error message.

---

## State Management

The application uses Streamlit session state where needed to preserve information across reruns.

State may include:

- uploaded dataset
- current question
- clarification context
- analysis plan
- execution result
- question history
- current agent status
- error information

State is reset when necessary, especially when a new incompatible dataset is uploaded.

---

## Agent States

The agent can move through different states depending on the request.

Example states include:

```text
READY
NEEDS_CLARIFICATION
CANNOT_ANSWER
FAILED
```

These states help separate successful analysis from ambiguity, unsupported requests, and technical failures.

---

## Safety

The application does not execute unrestricted Python code generated by the language model.

Instead, the agent selects from a controlled set of approved analysis operations.

This approach:

- reduces unsafe code execution
- makes system behavior easier to validate
- improves reliability
- makes the analysis workflow easier to explain
- keeps execution under application control

---

## Testing

The project includes tests covering both normal and failure scenarios.

Test cases include:

1. Valid CSV and valid question
2. Missing input
3. Ambiguous question
4. Missing or unsupported column
5. Invalid CSV file
6. Boundary case
7. Unsupported request
8. Invalid agent output
9. Analysis plan validation failure
10. Execution error

Each test records:

- Test ID
- Input
- Expected behavior
- Actual behavior
- Pass / Fail result

Detailed test results are available in:

```text
TEST_RESULTS.md
```

---

## Example Test Scenarios

### Valid Question

**Input**

```text
What is the total revenue?
```

**Expected behavior**

The agent generates a valid analysis plan, the application calculates the result, and the total revenue is displayed.

---

### Ambiguous Question

**Input**

```text
What is the best product?
```

**Expected behavior**

The system asks the user to clarify what "best" means instead of guessing.

---

### Missing Column

**Input**

```text
Show revenue by city.
```

If the dataset does not contain a `City` column:

**Expected behavior**

The system explains that the request cannot be answered using the available dataset.

---

### Invalid File

**Input**

An unreadable or invalid CSV file.

**Expected behavior**

The application shows a helpful error message and does not continue to analysis.

---

## Data Visualization

When a visualization adds value to the result, the system can display an appropriate chart.

Examples include:

- revenue by country
- sales by product
- quantity by category
- grouped comparisons
- top-N results

Charts are generated using Plotly or Streamlit visualization tools.

---

## Design Principles

The project follows several important AI system design principles:

### Explainability

The system shows what analysis was performed rather than returning an unexplained answer.

### Validation

Agent outputs are checked before execution.

### Controlled Execution

The model selects from approved actions instead of generating unrestricted executable code.

### Clarification Over Guessing

When a request is ambiguous, the system asks the user for more information.

### Graceful Failure

The application clearly explains when a request cannot be completed.

### Separation of Concerns

The user interface, agent logic, validation, and analysis execution are separated into different components.

