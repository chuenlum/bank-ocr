import streamlit as st
import os
import cv2
import numpy as np
import pandas as pd
import json
import base64
from PIL import Image, ImageOps
from dotenv import load_dotenv
from openai import AzureOpenAI
import io

# Load environment variables
load_dotenv()

# Initialize Azure OpenAI Client
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview"
)

def clean_image(uploaded_file):
    """
    Pre-processes the image for better OCR/AI extraction.
    """
    # Step A: Open with Pillow and fix rotation
    image = Image.open(uploaded_file)
    image = ImageOps.exif_transpose(image)

    # Step B: Convert to Numpy array for OpenCV
    img_array = np.array(image)

    # Step C: Convert to Grayscale
    # Check if image has 3 channels (RGB) or 4 (RGBA) and convert accordingly
    if len(img_array.shape) == 3:
        if img_array.shape[2] == 4:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
        else:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        # Already grayscale or single channel
        gray = img_array

    # Step D: Apply Adaptive Thresholding
    # Remove shadows/lighting issues
    processed_img = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2
    )

    # Step E: Return the processed image encoded as base64 strings
    # Encode processed image to buffer
    is_success, buffer = cv2.imencode(".jpg", processed_img)
    if not is_success:
        raise ValueError("Could not encode processed image")

    base64_image = base64.b64encode(buffer).decode("utf-8")
    return base64_image

def extract_transactions(base64_image):
    """
    Sends the image to Azure OpenAI to extract transaction data.
    """
    deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {
                "role": "system",
                "content": "You are a data entry assistant. Extract bank transactions from this image. Return ONLY raw JSON. The format must be a list of objects: [{'date': 'YYYY-MM-DD', 'description': '...', 'withdrawal': float, 'deposit': float, 'balance': float}]. Return 0 for empty numeric fields."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=4096
    )

    content = response.choices[0].message.content

    # Clean up markdown code blocks if present
    if content.startswith("```json"):
        content = content.replace("```json", "").replace("```", "")
    elif content.startswith("```"):
        content = content.replace("```", "")

    return content

# UI Setup
st.set_page_config(page_title="Bank Statement AI Digitizer", layout="wide")
st.title("Bank Statement AI Digitizer")

uploaded_files = st.file_uploader("Upload Bank Statement Photos", type=["jpg", "png", "jpeg"], accept_multiple_files=True)

if st.button("Process") and uploaded_files:
    all_transactions = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for i, uploaded_file in enumerate(uploaded_files):
        status_text.text(f"Processing file {i+1} of {len(uploaded_files)}: {uploaded_file.name}...")

        try:
            # 1. Pre-process
            base64_img = clean_image(uploaded_file)

            # 2. Extract
            json_response = extract_transactions(base64_img)

            # 3. Parse
            try:
                data = json.loads(json_response)
                # Add source file name to each record
                for record in data:
                    record['source_file'] = uploaded_file.name
                all_transactions.extend(data)
            except json.JSONDecodeError:
                st.error(f"Failed to parse JSON for {uploaded_file.name}")
                st.text_area("Raw Output", json_response, height=200)

        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {str(e)}")

        # Update progress
        progress_bar.progress((i + 1) / len(uploaded_files))

    status_text.text("Processing complete!")

    if all_transactions:
        df = pd.DataFrame(all_transactions)

        # Reorder columns if possible to put source_file first or last
        cols = ['date', 'description', 'withdrawal', 'deposit', 'balance', 'source_file']
        # Filter to only columns that exist in case AI missed some
        cols = [c for c in cols if c in df.columns]
        # Add any other columns that might have been returned
        remaining_cols = [c for c in df.columns if c not in cols]
        df = df[cols + remaining_cols]

        st.subheader("Extracted Data")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name="bank_transactions.csv",
            mime="text/csv",
        )
    else:
        st.warning("No transactions extracted.")
