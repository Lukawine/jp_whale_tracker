# JP Whale Tracker

## Overview

JP Whale Tracker is a web application designed to track and analyze significant announcements from Japanese companies, particularly those that might be considered "whale" activity in the stock market. It allows users to search for announcements based on date ranges and stock codes, trigger scraping for new data, manage a list of followed stocks, download announcement files, and perform basic analysis.

## Features

*   **Search Announcements:**
    *   Search for announcements by date range (start and end dates).
    *   Filter announcements by specific stock codes (comma-separated).
    *   View search results in a sortable table.
    *   Table includes: Grade, Security Code, Company Name, Title, Date, URL, Reason and Actions.
*   **Trigger Scraping:**
    *   Initiate a scraping process to fetch the latest announcements.
*   **Manage Stocks:**
    *   Add and remove stock codes from a managed list.
*   **Download Announcements:**
    *   Download announcement files for local analysis.
*   **Analyze Announcements:**
    *   Perform basic analysis on downloaded announcement files.
*   **View Files:**
    *   View the downloaded announcement files.

## Technologies Used

*   **Frontend:** HTML, CSS, JavaScript, Bootstrap
*   **Backend:** (Assumed) Python (Flask or similar)
*   **Data Storage:** (Assumed) Database (e.g., SQLite, PostgreSQL)

## Setup Instructions

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    ```

2.  **Set up the backend:**

    *   Install the necessary Python packages.
    *   Configure the database.
    *   Set up the API endpoints ( `/api/search`, `/api/trigger_scrape`, `/api/stocks`, `/api/download`, `/api/analyze`, `/api/get_file`).

3.  **Run the application:**
    *   bash    python app.py 
    *   Open your web browser and go to `http://127.0.0.1:5000/`.
    *   Open the `index.html` file in your browser.

## Usage

1.  **Searching for Announcements:**
    *   Enter the desired start and end dates in the "Start Date" and "End Date" fields.
    *   Enter the stock codes you want to search for, separated by commas, in the "Stock Codes" field.
    *   Click the "Search" button.

2.  **Triggering a Scrape:**
    *   Click the "Trigger Scrape" button to initiate the scraping process.

3.  **Managing Stocks:**
    *   Click the "Manage Stocks" button to open the stock management modal.
    *   Add new stock codes in the "Add New Codes" field and click "Add Codes".
    *   Delete existing stock codes by clicking the "Delete" button next to the code.

4.  **Download/Analyze/View Announcements:**
    *   Use the corresponding buttons in the search results table to download, analyze, and view announcement files.