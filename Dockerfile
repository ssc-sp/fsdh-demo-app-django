# Pull base image
FROM python:3.14-trixie

# Set environment variables
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /workspaces/astervis

# Install dependencies
COPY ./requirements.txt .
RUN python -m pip install -r requirements.txt

# Run the thing
COPY . .
