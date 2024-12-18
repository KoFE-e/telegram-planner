# Use official Python image as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on (optional, as Telegram bots don't require a public port)
# EXPOSE 8080

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Command to run the bot
CMD ["python", "main.py"]