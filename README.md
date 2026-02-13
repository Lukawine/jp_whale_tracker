The Streamlit frontend has been successfully replaced with a Bootstrap-based Flask frontend, replicating the core functionalities.

**To run the application:**

1.  Make sure your Python virtual environment is activated.
2.  Run the Flask application:
    ```bash
    python app.py
    ```
3.  Open your web browser and go to `http://127.0.0.1:5000/`.

**You should now be able to:**

*   See a table of announcements with "Security Code", "Company Name", "Title", "Date", "URL", "Grade", "Reason", and "Actions" columns.
*   Use the "Search Announcements" form to filter announcements by date range and stock codes.
*   Click "Trigger Scrape" to manually initiate the scraping process.
*   Click "Manage Stocks" to open a modal where you can view, add, and delete stock codes.
*   For each announcement, use the action buttons:
    *   **Download:** To download the announcement content. Once downloaded, the "View File" button will become active.
    *   **Analyze:** To get an AI analysis of the announcement, displayed in a modal.
    *   **View File:** To open the downloaded announcement file in a new tab.

Please test these functionalities and let me know if you encounter any issues or have further requests.