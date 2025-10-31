# Req 2: Use docker based setup
# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main application file into the container at /app
COPY app.py .

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define environment variable
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Run app.py when the container launches
# Use "0.0.0.0" to make it accessible from outside the container
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
