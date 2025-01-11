# Use the official Python 3.12 image based on Alpine
FROM python:3.12-alpine

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Install cron
RUN apk add --no-cache cronie

# Add crontab file in the cron directory
COPY crontab /etc/crontabs/root

# Give execution rights on the cron job
RUN chmod 0644 /etc/crontabs/root

# Create the log file to be able to run tail
RUN touch /var/log/cron.log

# Run the command on container startup
CMD ["crond", "-f", "-l", "2"]