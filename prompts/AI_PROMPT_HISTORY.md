# AI Prompts Used During Project Development :

# About this document :

While building the Inventory Reconciliation Pipeline, I used ChatGPT as a helping tool whenever I got stuck, needed ideas, or wanted to improve something in the project.

I didn't build everything in one go. I worked on it step by step, starting with the basic pipeline and then adding validation, transformations, reconciliation, testing, SQL analysis, and the dashboard.

Below are some of the main prompts and requests I used during the development process. I've written them in a simple way to reflect how I approached each stage.

---

# 1. Planning the project

Prompt 1:

I want to build a Data Engineering project based on inventory reconciliation. I have around 72 hours to complete it. Can you help me plan the entire project from scratch? I want it to look like a real-world project and cover the important concepts that companies expect from a Data Engineer. Please break it down into steps so I can follow them one by one.

Prompt 2:

Can you help me design the architecture for this project? The pipeline should handle inventory receipts, issues, transfers, and adjustments. I also want to include data validation, transformation, daily inventory balances, reconciliation, SQL analysis, and a dashboard. Explain how all these parts should connect.

# 2. Generating the inventory data

Prompt 3:

I need sample inventory data to work with. Can you write Python code to generate a large CSV file with inventory events? Include product IDs, location IDs, dates, movement types, quantities, and other necessary fields. Also generate separate product and location reference files.

Prompt 4:

I also want to demonstrate how my pipeline handles bad data. Can you add a few intentionally incorrect records to the generated dataset, such as missing values, invalid movement types, and incorrect references? Keep most of the records valid.

# 3. Building the ingestion process

Prompt 5:

Now let's start building the ingestion part. I want to load the CSV inventory events into DuckDB. Can you help me create the ingestion module with batch processing, pipeline run IDs, source file tracking, and proper error handling?

Prompt 6:

One important thing I want to handle is duplicate records. If I run the same file again, it should not insert the same records twice. Can you help me implement this using deterministic IDs and make sure rerunning the ingestion is safe?

# 4. Data validation

Prompt 7:

Next, I want to validate the inventory records before processing them further. Please help me check required fields, quantities, movement types, product IDs, and location IDs. Valid records should continue through the pipeline, while invalid records should be stored separately with the reason why they were rejected.

Prompt 8:

I noticed that duplicate records can create problems when the pipeline is run again. Can you review the validation logic and make sure records that were already accepted are not incorrectly treated as new rejected records?

# 5. Transforming inventory events into movements

Prompt 9:

I want to convert the validated inventory events into standardized inventory movements. Can you help me write the transformation logic for receipts, issues, adjustments, and transfers? For transfers, I need one outgoing movement from the source location and one incoming movement at the destination location.

Prompt 10:

Can you help me write a separate script to verify whether the transfers are correct? I want to check that every transfer has matching outgoing and incoming records and that the overall inventory impact is zero.

# 6. Calculating daily inventory balances

Prompt 11:

Now I need to calculate daily inventory balances for every product and location. Can you write a Python module that calculates opening stock, receipts, issues, transfers, adjustments, net movement, and closing stock for each day? Also include a flag to identify negative inventory.

Prompt 12:

I want to handle backdated corrections as well. For example, if an inventory adjustment is added for a previous date, all the balances after that date should be recalculated correctly. Can you help me implement this without creating duplicate balance records or changing balances before the correction date?

# 7. Testing and reconciliation

Prompt 13:

I want to verify that my calculated inventory balances are actually correct. Can you create a reconciliation script that compares the original movement totals with the calculated balance totals? It should check receipts, issues, transfers, and adjustments, and report any arithmetic errors or duplicate balance records.

Prompt 14:

Can you help me create an idempotency test? I want to run ingestion twice using the same input file and confirm that the second run does not insert additional records. Please use a separate test database so my actual database is not affected.

Prompt 15:

I also want to test the backdated correction functionality. Can you create a test that uses a copy of my database, inserts a historical adjustment, recalculates the balances, and verifies that the later balances are updated while earlier balances remain unchanged?

Prompt 16:

Can you help me create a final verification script for the daily balances? I want it to check balance arithmetic, continuity between days, duplicate product-location-date combinations, and negative inventory positions.

# 8. SQL analysis

Prompt 17:

I want to explore the DuckDB database using SQL. Can you help me write queries to inspect the tables, understand the schema, and check how many records are available in each table?

Prompt 18:

Can you write some SQL queries to analyze inventory performance? I want to see current stock levels, product-wise inventory, location-wise inventory, receipts, issues, and inventory movement trends.

Prompt 19:

I also want to identify inventory risks. Can you help me write SQL queries to find negative stock positions, affected products, locations with inventory problems, and other useful inventory exceptions?

# 9. Building the Streamlit dashboard

Prompt 20:

I want to create a professional Streamlit dashboard for this project. Let's call it Inventory Control Tower. It should connect to my DuckDB database and display useful inventory metrics, charts, and insights. Can you help me build it step by step?

Prompt 21:

The dashboard should look professional because I want to showcase it during my project evaluation. Can you improve the design with a dark theme, better layout, KPI cards, charts, filters, and clear navigation?

Prompt 22:

I want to divide the dashboard into different sections instead of putting everything on one page. Include Executive Overview, Inventory Explorer, Warehouse Analysis, Movement Intelligence, Alerts Center, Data Quality Center, Pipeline Monitoring, and Reconciliation Center.

Prompt 23:

Can you add date filters and make sure the charts update based on the selected reporting period? I also want to show daily receipts versus issues and how negative inventory positions change over time.

# 10. Docker setup

Prompt 24:

I want to make this project easier to run on another machine. Can you help me create a Dockerfile that installs the required Python packages and starts the Streamlit dashboard when the container runs?

Prompt 25:

Can you also create a .dockerignore file? I don't want unnecessary files like my virtual environment, Git folder, cache files, and local secrets to be included in the Docker build.

# 11. README and GitHub

Prompt 26:

Help me write a proper README for this project. I want someone visiting my GitHub repository to understand the business problem, project architecture, technologies used, pipeline workflow, database tables, testing, dashboard features, and how to run the project locally.

Prompt 27:

I am preparing to upload the project to GitHub. Can you help me check the project structure, create a suitable .gitignore, and guide me through the Git commands to commit and push everything to my repository?

---

# 12. How I used AI during development

I mainly used ChatGPT as a learning and development assistant. Whenever I reached a new stage, I asked for guidance, implemented the suggested changes, and tested them locally.

Some of the areas where I used AI assistance were:

- Planning the project architecture and breaking the work into stages.
- Writing and improving Python modules.
- Understanding and fixing errors during development.
- Implementing duplicate prevention and safe reruns.
- Writing SQL queries for inventory analysis.
- Creating test scripts for idempotency and backdated corrections.
- Improving the Streamlit dashboard.
- Setting up Docker configuration and project documentation.

I did not treat generated code as automatically correct. I ran the scripts, checked the database results, and used separate verification scripts to confirm whether the expected results were achieved.

# Final verification results

The following results were observed during local project execution:

| Verification | Result |
|---|---:|
| Input inventory records | 100,003 |
| Accepted records | 100,000 |
| Rejected records | 3 |
| Inventory movement records | 114,879 |
| Daily balance records | 29,948 |
| Transfers checked | 14,879 |
| Invalid transfers | 0 |
| Balance arithmetic errors | 0 |
| Balance continuity errors | 0 |
| Duplicate balance keys | 0 |
| Idempotency test | PASS |
| Backdated correction test | PASS |
| Overall reconciliation | SUCCESS |

Negative inventory positions were also identified and displayed as inventory risks. They were not simply removed to make the results look better.

**Note:** These prompts are representative summaries of the requests I used during development, not an exact transcript of every conversation. AI assisted with the work, while implementation, execution, and local verification were carried out as part of the project development process.