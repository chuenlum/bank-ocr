# Bank Statement AI Digitizer

## Project Goal
The **Bank Statement AI Digitizer** is a Streamlit application designed to streamline the process of extracting transaction data from phone photos of bank statements. By leveraging **Azure OpenAI (GPT-4.1 mini)** and advanced image processing techniques with **OpenCV** and **Pillow**, this tool converts raw images into structured CSV data, ready for analysis.

## Local Setup

### Prerequisites
- **Python 3.10+**: Ensure you have a compatible version of Python installed.
- **uv**: This project uses `uv` for fast dependency management.
- **Poppler**: Required for PDF processing capabilities (if extended in the future).
    - *Linux (Ubuntu/Debian)*: `sudo apt-get install poppler-utils`
    - *macOS*: `brew install poppler`
    - *Windows*: Download and add to PATH.

### Installation
1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd bank-ocr
    ```

2.  **Install dependencies**:
    ```bash
    uv sync
    ```
    *Alternatively, if using pip directly:*
    ```bash
    pip install opencv-python-headless streamlit openai pandas python-dotenv pillow numpy
    ```

## Configuration

1.  **Environment Variables**:
    Create a `.env` file in the root directory by copying the example:
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**:
    Open the `.env` file and populate the following variables with your Azure OpenAI credentials:
    ```ini
    AZURE_OPENAI_ENDPOINT="https://your-resource-name.openai.azure.com/"
    AZURE_OPENAI_API_KEY="your-api-key"
    AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4-mini" # Or your specific deployment name
    ```

## Usage

1.  **Run the Application**:
    ```bash
    uv run streamlit run app.py
    ```

2.  **Upload Images**:
    - Open the app in your browser (usually `http://localhost:8501`).
    - Use the file uploader to select one or more JPG/PNG images of your bank statements.

3.  **Process**:
    - Click the **"Process"** button.
    - The app will clean the images (fix rotation, remove shadows) and send them to the AI for extraction.

4.  **Download Results**:
    - Once processing is complete, review the extracted data in the table.
    - Click **"Download CSV"** to save the transactions to your computer.

## Future Plans

-   **Google Sheets Integration**: Automatically append extracted transactions to a specific Google Sheet.
-   **Database Storage**: Save historical data to a local SQLite or PostgreSQL database.
-   **File Storage**: Organize and archive uploaded images and generated CSVs.
-   **Chatbot Assistant**: Add a chat interface to query your transaction history (e.g., "How much did I spend on groceries last month?").
