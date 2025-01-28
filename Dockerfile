# Use the latest uv image with python 3.13 and alpine
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Set the working directory
WORKDIR /app

COPY uv.lock pyproject.toml process_data.py mongo.py main.py gsheet.py gdrive.py settings.py run.sh /app/

RUN uv sync --frozen --no-cache

# Install cron
#RUN apt-get update && apt-get install -y cron && apt-get clean

# Add crontab file in the cron directory
#COPY crontab /etc/cron.d/backtest-cron

# Give execution rights on the cron job
#RUN chmod 0644 /etc/cron.d/backtest-cron

# Ensure main.py can run
#RUN chmod +x /app/main.py

# Create the log file to be able to run tail
#RUN touch /var/log/cron.log
 
# Start cron and log output
#CMD ["sh", "-c", "cron && tail -f /var/log/cron.log"]
# wait 2.5 hours
CMD ["sh", "-c", "sh /app/run.sh"]