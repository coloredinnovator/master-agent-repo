FROM python:3.11-slim

WORKDIR /app

# Install dependencies using standard pip
# We are converting the inline uv script dependencies to requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set the port environment variable to 8080 (Cloud Run default)
ENV PORT=8080

# Command to run the application using Uvicorn
CMD ["uvicorn", "mission_zero:app", "--host", "0.0.0.0", "--port", "8080"]
